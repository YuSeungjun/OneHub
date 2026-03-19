from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import sys
import typing
from pathlib import Path
import glob as globmod


def _get_ffmpeg_path():
    """PyInstaller 번들 또는 개발 환경에서 ffmpeg 경로를 찾는다."""
    # 1. PyInstaller 번들 내부 (_MEIPASS)
    if hasattr(sys, '_MEIPASS'):
        pattern = os.path.join(sys._MEIPASS, 'imageio_ffmpeg', 'binaries', 'ffmpeg*')
        matches = [f for f in globmod.glob(pattern) if not f.endswith('.md')]
        if matches:
            return matches[0]

    # 2. imageio_ffmpeg 패키지 사용 (개발 환경)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    # 3. 시스템 PATH에서 ffmpeg 찾기
    import shutil
    p = shutil.which('ffmpeg')
    if p:
        return p

    raise RuntimeError("ffmpeg를 찾을 수 없습니다.")


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
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
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
        import traceback
        result_q.put({"status": "error", "message": f"{str(e)}\nTraceback:\n{traceback.format_exc()}"})

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
        'ffmpeg_location': _get_ffmpeg_path(),
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

def _docx_to_html(docx_path):
    """DOCX → HTML 변환 (표준 라이브러리만 사용, 서식/표/셀병합 보존)"""
    import zipfile
    from xml.etree import ElementTree

    W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

    def _v(elem, attr='val'):
        """w:val 속성 값 추출 (네임스페이스 유무 모두 대응)"""
        return elem.get(f'{W}{attr}', elem.get(attr, ''))

    with zipfile.ZipFile(docx_path) as z:
        xml_data = z.read('word/document.xml')

    root = ElementTree.fromstring(xml_data)
    body = root.find(f'{W}body')
    if body is None:
        body = root

    def run_to_html(run):
        rPr = run.find(f'{W}rPr')
        # 줄바꿈
        if run.find(f'{W}br') is not None:
            return '<br>'
        parts = []
        for t in run.iter(f'{W}t'):
            if t.text:
                parts.append(t.text)
        text = ''.join(parts)
        if not text:
            return ''

        styles = []
        b_open, b_close = '', ''

        if rPr is not None:
            if rPr.find(f'{W}b') is not None:
                b_open += '<b>'; b_close = '</b>' + b_close
            if rPr.find(f'{W}i') is not None:
                b_open += '<i>'; b_close = '</i>' + b_close
            if rPr.find(f'{W}u') is not None:
                b_open += '<u>'; b_close = '</u>' + b_close
            sz = rPr.find(f'{W}sz')
            if sz is not None:
                v = _v(sz)
                if v:
                    styles.append(f'font-size:{int(v)//2}pt')
            color = rPr.find(f'{W}color')
            if color is not None:
                v = _v(color)
                if v and v != 'auto':
                    styles.append(f'color:#{v}')
            rFonts = rPr.find(f'{W}rFonts')
            if rFonts is not None:
                font = rFonts.get(f'{W}eastAsia', rFonts.get('eastAsia', ''))
                if not font:
                    font = rFonts.get(f'{W}ascii', rFonts.get('ascii', ''))
                if font:
                    styles.append(f"font-family:'{font}'")

        if styles:
            text = f'<span style="{";".join(styles)}">{text}</span>'
        return f'{b_open}{text}{b_close}'

    def para_to_html(para):
        pPr = para.find(f'{W}pPr')
        p_styles = []

        if pPr is not None:
            # 정렬
            jc = pPr.find(f'{W}jc')
            if jc is not None:
                align = _v(jc)
                align_map = {'center': 'center', 'right': 'right', 'both': 'justify', 'distribute': 'justify'}
                if align in align_map:
                    p_styles.append(f'text-align:{align_map[align]}')
            # 들여쓰기
            ind = pPr.find(f'{W}ind')
            if ind is not None:
                left = ind.get(f'{W}left', ind.get('left', ''))
                if left:
                    p_styles.append(f'margin-left:{int(left)//15}px')
                first = ind.get(f'{W}firstLine', ind.get('firstLine', ''))
                if first:
                    p_styles.append(f'text-indent:{int(first)//15}px')
            # 줄간격
            spacing = pPr.find(f'{W}spacing')
            if spacing is not None:
                after = spacing.get(f'{W}after', spacing.get('after', ''))
                before = spacing.get(f'{W}before', spacing.get('before', ''))
                if after:
                    p_styles.append(f'margin-bottom:{int(after)//15}px')
                if before:
                    p_styles.append(f'margin-top:{int(before)//15}px')

        parts = []
        for child in para:
            tag = child.tag.split('}')[-1]
            if tag == 'r':
                parts.append(run_to_html(child))

        style_attr = f' style="{";".join(p_styles)}"' if p_styles else ''
        content = ''.join(parts)
        return f'<p{style_attr}>{content}</p>' if content else '<p>&nbsp;</p>'

    def table_to_html(tbl):
        # 세로 병합 추적: col_idx -> rowspan count
        vmerge_starts = {}  # col_idx -> (row_list_index, cell_list_index)
        all_rows_html = []

        row_elems = [ch for ch in tbl if ch.tag.endswith('}tr')]

        for row_i, tr in enumerate(row_elems):
            cells_html = []
            col_idx = 0

            for tc in tr:
                if not tc.tag.endswith('}tc'):
                    continue

                tcPr = tc.find(f'{W}tcPr')
                colspan = 1
                vmerge_type = None
                cell_styles = []

                if tcPr is not None:
                    gs = tcPr.find(f'{W}gridSpan')
                    if gs is not None:
                        colspan = int(_v(gs) or '1')

                    vm = tcPr.find(f'{W}vMerge')
                    if vm is not None:
                        v = _v(vm)
                        vmerge_type = v if v else 'continue'

                    # 셀 너비
                    tcW = tcPr.find(f'{W}tcW')
                    if tcW is not None:
                        w = tcW.get(f'{W}w', tcW.get('w', ''))
                        if w:
                            cell_styles.append(f'width:{int(w)//15}px')

                    # 셀 배경색
                    shd = tcPr.find(f'{W}shd')
                    if shd is not None:
                        fill = shd.get(f'{W}fill', shd.get('fill', ''))
                        if fill and fill != 'auto':
                            cell_styles.append(f'background-color:#{fill}')

                    # 셀 세로 정렬
                    vAlign = tcPr.find(f'{W}vAlign')
                    if vAlign is not None:
                        va = _v(vAlign)
                        if va == 'center':
                            cell_styles.append('vertical-align:middle')
                        elif va == 'bottom':
                            cell_styles.append('vertical-align:bottom')

                # 세로 병합: continue면 이 셀 건너뜀
                if vmerge_type == 'continue':
                    col_idx += colspan
                    continue

                # 셀 내용
                cell_content = []
                for p in tc:
                    if p.tag.endswith('}p'):
                        cell_content.append(para_to_html(p))

                attrs = ''
                if colspan > 1:
                    attrs += f' colspan="{colspan}"'
                if cell_styles:
                    attrs += f' style="{";".join(cell_styles)}"'

                cells_html.append(f'<td{attrs}>{"".join(cell_content)}</td>')
                col_idx += colspan

            if cells_html:
                all_rows_html.append(f'<tr>{"".join(cells_html)}</tr>')

        return f'<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;width:100%">{"".join(all_rows_html)}</table>'

    html = ['<html><head><meta charset="utf-8"></head><body>']
    for elem in body:
        tag = elem.tag.split('}')[-1]
        if tag == 'p':
            html.append(para_to_html(elem))
        elif tag == 'tbl':
            html.append(table_to_html(elem))
    html.append('</body></html>')

    html_path = docx_path.rsplit('.', 1)[0] + '.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html))
    return html_path


def _hwp_convert_worker(input_path, output_path, direction, save_fmt, result_q):
    """별도 스레드에서 HWP COM 변환 (STA 보장)"""
    pythoncom.CoInitialize()
    hwp = None
    html_path = None
    try:
        hwp = win32.Dispatch("HWPFrame.HwpObject")
        hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
        hwp.XHwpWindows.Item(0).Visible = True

        open_ok = False
        used_method = ""

        if direction == 'WORD_TO_HWP':
            # 1차: OOXML 직접 열기 시도 (한글 2020+ 에서 동작)
            r = hwp.Open(input_path, "OOXML", "")
            if r:
                # 내용 검증 — 바이너리가 텍스트로 열린 경우 걸러냄
                text = hwp.GetTextFile("TEXT", "")
                if text and not text.startswith("PK"):
                    open_ok = True
                    used_method = "direct"
                else:
                    hwp.Clear(1)

            # 2차: HTML 변환 후 열기 (한글 2020 미만)
            if not open_ok:
                html_path = _docx_to_html(input_path)
                for fmt in ["HTML", ""]:
                    r = hwp.Open(html_path, fmt, "")
                    if r:
                        open_ok = True
                        used_method = "html"
                        break
        else:
            # HWP_TO_WORD: HWP 파일은 직접 열기
            for fmt in ["HWP", ""]:
                r = hwp.Open(input_path, fmt, "")
                if r:
                    open_ok = True
                    break

        if not open_ok:
            result_q.put({"status": "error", "message": "파일 열기 실패"})
            return

        # 저장
        hwp.HAction.GetDefault("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)
        hwp.HParameterSet.HFileOpenSave.filename = output_path
        hwp.HParameterSet.HFileOpenSave.Format = save_fmt
        hwp.HAction.Execute("FileSaveAs_S", hwp.HParameterSet.HFileOpenSave.HSet)

        hwp.Clear(1)
        hwp.Quit()
        hwp = None
        result_q.put({"status": "success", "method": used_method})
    except Exception as e:
        result_q.put({"status": "error", "message": str(e)})
    finally:
        if hwp:
            try:
                hwp.Quit()
            except:
                pass
        if html_path:
            try:
                os.remove(html_path)
            except:
                pass
        pythoncom.CoUninitialize()


@app.post("/doc/convert")
async def convert_document(file: UploadFile = File(...), direction: str = Form(...), save_path: str = Form("")):
    file_path = None
    try:
        temp_dir = os.path.join(os.path.expanduser("~"), "OneHubTemp")
        os.makedirs(temp_dir, exist_ok=True)

        original_name = file.filename
        _, ext = os.path.splitext(original_name)
        name_only, _ = os.path.splitext(original_name)

        import uuid
        safe_filename = f"onehub_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(temp_dir, safe_filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        file_path = os.path.abspath(file_path)

        output_dir = save_path if save_path else str(Path.home() / "Downloads")
        os.makedirs(output_dir, exist_ok=True)

        if direction == 'HWP_TO_WORD':
            out_ext = ".docx"
            save_fmt = "OOXML"
        elif direction == 'WORD_TO_HWP':
            out_ext = ".hwp"
            save_fmt = "HWP"
        else:
            return {"status": "error", "message": "Invalid direction"}

        safe_output = os.path.join(temp_dir, f"onehub_out_{uuid.uuid4().hex[:8]}{out_ext}")
        safe_output = os.path.abspath(safe_output)
        output_path = os.path.join(output_dir, f"{name_only}{out_ext}")

        result_q = queue.Queue()
        t = threading.Thread(
            target=_hwp_convert_worker,
            args=(file_path, safe_output, direction, save_fmt, result_q),
        )
        t.start()
        t.join(timeout=120)

        if not result_q.empty():
            result = result_q.get()
            if result["status"] == "success" and os.path.exists(safe_output):
                import shutil
                if os.path.exists(output_path):
                    os.remove(output_path)
                shutil.move(safe_output, output_path)
                return {"status": "success", "message": f"Saved to {output_path}"}
            else:
                return {"status": "error", "message": result.get("message", "알 수 없는 오류")}

        return {"status": "error", "message": "변환 시간 초과"}

    except Exception as e:
        import traceback
        return {"status": "error", "message": f"{str(e)}\n{traceback.format_exc()}"}
    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    import socket

    port = 8000

    # 포트가 이미 사용 중인지 확인 후 시작
    def _port_in_use(p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', p)) == 0

    if _port_in_use(port):
        print(f"[OneHub] Port {port} is already in use, waiting 3s and retrying...")
        import time
        time.sleep(3)
        if _port_in_use(port):
            print(f"[OneHub] Port {port} still in use. Exiting.")
            sys.exit(1)

    print(f"[OneHub] Starting backend on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
