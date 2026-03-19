from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import typing
from pathlib import Path
import imageio_ffmpeg

app = FastAPI(title="OneHub Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format: str # 'mp4' or 'mp3'
    resolution: str # '4K', '1080p', '720p'
    download_path: str # 다운로드 경로 추가

@app.get("/")
def read_root():
    return {"status": "ok", "message": "OneHub Backend is running."}

@app.post("/media/analyze")
def analyze_media(req: URLRequest):
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
            return {
                "status": "success", 
                "url": req.url, 
                "title": info.get('title', 'Unknown Title'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', '')
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}
import subprocess
import glob
import time
import threading
import queue

# ── 다운로드 취소 관리 ──
_cancel_event = threading.Event()
_download_path = ""

class _DownloadCanceled(BaseException):
    """yt-dlp 내부의 except Exception: 에 걸리지 않도록 BaseException을 상속합니다."""
    pass

def _cleanup_dir(download_dir):
    """다운로드 폴더 내 .part / .ytdl / .temp 잔여 파일을 삭제합니다."""
    if not download_dir:
        return
    for pattern in ['*.part', '*.ytdl', '*.temp']:
        for f in glob.glob(os.path.join(download_dir, pattern)):
            for _ in range(10):
                try:
                    os.remove(f)
                    break
                except:
                    time.sleep(0.5)

def _kill_ffmpeg():
    """ffmpeg/ffprobe 프로세스를 강제 종료합니다 (후처리 단계 중단용)."""
    CREATE_NO_WINDOW = 0x08000000
    for name in ['ffmpeg.exe', 'ffprobe.exe']:
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', name],
                capture_output=True, creationflags=CREATE_NO_WINDOW
            )
        except:
            pass

def _run_download(ydl_opts, url, result_q):
    """스레드에서 실행: yt-dlp 다운로드"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        result_q.put({"status": "success", "message": "Download completed"})
    except _DownloadCanceled:
        result_q.put({"status": "canceled", "message": "Canceled"})
    except SystemExit:
        result_q.put({"status": "canceled", "message": "Canceled"})
    except Exception as e:
        result_q.put({"status": "error", "message": str(e)})

@app.post("/media/download")
def download_media(req: DownloadRequest):
    global _download_path
    _cancel_event.clear()

    downloads_path = req.download_path if req.download_path else str(Path.home() / "Downloads")
    _download_path = downloads_path
    _cleanup_dir(downloads_path)

    def cancel_hook(d):
        """다운로드 진행 중 주기적으로 호출되는 훅. 취소 이벤트 감지 시 BaseException을 발생시킵니다."""
        if _cancel_event.is_set():
            raise _DownloadCanceled("Download canceled by user")

    ydl_opts = {
        'outtmpl': os.path.join(downloads_path, '%(title).200s.%(ext)s'),
        'quiet': False,
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'windowsfilenames': True,
        'restrictfilenames': True,
        'trim_file_name': 200,
        'progress_hooks': [cancel_hook],
    }

    if req.format == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        res_map = {'4K': '2160', '1080p': '1080', '720p': '720'}
        target_res = res_map.get(req.resolution, '1080')
        ydl_opts['format'] = f'bestvideo[ext=mp4][height<={target_res}]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'

    result_q = queue.Queue()
    dl_thread = threading.Thread(target=_run_download, args=(ydl_opts, req.url, result_q), daemon=True)
    dl_thread.start()

    # 스레드가 끝날 때까지 대기하되, 취소 감지 시 ffmpeg도 죽임
    while dl_thread.is_alive():
        if _cancel_event.is_set():
            _kill_ffmpeg()  # 후처리(ffmpeg 비디오+오디오 병합) 단계라면 ffmpeg를 죽여서 yt-dlp에 에러를 유발
        dl_thread.join(timeout=0.5)

    # 취소가 요청되었으면 무조건 canceled 반환
    if _cancel_event.is_set():
        _kill_ffmpeg()
        time.sleep(0.5)
        _cleanup_dir(downloads_path)
        return {"status": "canceled", "message": "Download canceled by user"}

    try:
        return result_q.get_nowait()
    except:
        return {"status": "error", "message": "No result from download thread"}

@app.post("/media/cancel")
def cancel_media_download():
    """취소 신호 전송 + ffmpeg 강제 종료"""
    _cancel_event.set()
    _kill_ffmpeg()
    return {"status": "success", "message": "Cancel signal sent"}

import win32com.client as win32
import pythoncom

from fastapi import File, UploadFile, Form

@app.post("/doc/convert")
async def convert_document(file: UploadFile = File(...), direction: str = Form(...), save_path: str = Form("")):
    hwp = None
    file_path = None
    try:
        # 1. 업로드된 파일을 임시 디렉토리에 저장
        temp_dir = os.path.join(os.path.expanduser("~"), "OneHubTemp")
        os.makedirs(temp_dir, exist_ok=True)
        
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
            
        file_path = os.path.abspath(file_path)
        _, file_name = os.path.split(file_path)
        name_only, _ = os.path.splitext(file_name)

        # 저장 경로 결정
        output_dir = save_path if save_path else str(Path.home() / "Downloads")
        os.makedirs(output_dir, exist_ok=True)

        pythoncom.CoInitialize()
    
        # Dispatch 사용 (gencache는 캐시 문제 발생 가능)
        hwp = win32.Dispatch("HWPFrame.HwpObject")
        hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
        hwp.XHwpWindows.Item(0).Visible = False

        if direction == 'HWP_TO_WORD':
            output_path = os.path.join(output_dir, f"{name_only}.docx")

            hwp.Open(file_path, "", "")

            hwp.HAction.GetDefault("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
            hwp.HParameterSet.HFileOpenSave.filename = output_path
            hwp.HParameterSet.HFileOpenSave.Format = "OOXML"
            hwp.HAction.Execute("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)

            hwp.Clear(1)
            hwp.Quit()
            hwp = None

            if os.path.exists(output_path):
                return {"status": "success", "message": f"Saved to {output_path}"}
            else:
                return {"status": "error", "message": f"Conversion completed but file was not created at {output_path}"}

        elif direction == 'WORD_TO_HWP':
            output_path = os.path.join(output_dir, f"{name_only}.hwp")

            # 업로드된 파일 검증
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return {"status": "error", "message": f"Uploaded file is empty (0 bytes): {file_path}"}

            open_result = hwp.Open(file_path, "", "")

            # Open 후 내용 확인
            text_check = hwp.GetTextFile("TEXT", "")
            if text_check is None or len(text_check.strip()) == 0:
                hwp.Clear(1)
                hwp.Quit()
                hwp = None
                return {"status": "error", "message": f"DOCX loaded but content is empty. File size: {file_size}, Open returned: {open_result}"}

            hwp.HAction.GetDefault("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
            hwp.HParameterSet.HFileOpenSave.filename = output_path
            hwp.HParameterSet.HFileOpenSave.Format = "HWP"
            hwp.HAction.Execute("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
            
            hwp.Clear(1)
            hwp.Quit()
            hwp = None
            return {"status": "success", "message": f"Saved to {output_path}"}
        else:
            if hwp:
                hwp.Quit()
                hwp = None
            return {"status": "error", "message": "Invalid direction"}
    except Exception as e:
        import traceback
        if hwp:
            try:
                hwp.Quit()
            except:
                pass
        return {"status": "error", "message": f"{str(e)}\n{traceback.format_exc()}"}
    finally:
        pythoncom.CoUninitialize()
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
