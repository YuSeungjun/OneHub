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
    if _IS_WINDOWS:
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
    else:
        for name in ['ffmpeg', 'ffprobe']:
            try:
                subprocess.run(
                    ['pkill', '-f', name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
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
        'outtmpl': '%(title).200s.%(ext)s',
        'paths': {
            'home': downloads_path,
            'temp': downloads_path,
        },
        'quiet': False,
        'ffmpeg_location': _get_ffmpeg_path(),
        'windowsfilenames': _IS_WINDOWS,
        'restrictfilenames': True,
        'trim_file_name': 200,
        'progress_hooks': [cancel_hook],
        'concurrent_fragment_downloads': 4,
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
        ydl_opts['format'] = (
            f'bestvideo[ext=mp4][vcodec^=avc1][height<={target_res}]+bestaudio[ext=m4a][acodec^=mp4a]/'
            f'bestvideo[ext=mp4][vcodec^=avc1][height<={target_res}]+bestaudio[ext=m4a]/'
            f'bestvideo[ext=mp4][height<={target_res}]+bestaudio[ext=m4a]/'
            f'best[ext=mp4]/best'
        )
        ydl_opts['merge_output_format'] = 'mp4'
        if _IS_WINDOWS:
            # Windows: 리먹싱만 수행 (재인코딩 없음, 수 초 내 완료)
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': 'mp4',
            }]
            ydl_opts['postprocessor_args'] = {
                'videoremuxer': ['-movflags', '+faststart'],
            }
        else:
            # macOS: QuickTime 호환을 위해 H.264+AAC로 재인코딩
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
            ydl_opts['postprocessor_args'] = {
                'videoconvertor': [
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-movflags', '+faststart',
                ],
            }

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

import platform as _platform_mod
_IS_WINDOWS = _platform_mod.system() == 'Windows'
if _IS_WINDOWS:
    import win32com.client as win32
    import pythoncom
else:
    from hwp5.xmlmodel import Hwp5File
    from docx import Document as DocxDocument
    import olefile

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


def _extract_bindata_images(hwp_path):
    """HWP OLE에서 BinData 이미지 추출 → {storage_id_int: BytesIO}"""
    import io, zlib
    images = {}
    try:
        ole = olefile.OleFileIO(hwp_path)
        for entry in ole.listdir():
            if entry[0] == 'BinData' and len(entry) > 1:
                name = entry[1]  # e.g. "BIN0001.png"
                digits = ''.join(c for c in name.split('.')[0] if c.isdigit())
                if not digits:
                    continue
                num = int(digits)
                data = ole.openstream('/'.join(entry)).read()
                try:
                    data = zlib.decompress(data, -15)
                except Exception:
                    pass
                # 이미지 포맷 검증
                if (data[:8] == b'\x89PNG\r\n\x1a\n' or data[:2] == b'\xff\xd8'
                        or data[:4] == b'GIF8' or data[:2] == b'BM'):
                    images[num] = io.BytesIO(data)
        ole.close()
    except Exception:
        pass
    return images


def _hwp_process_paragraph(doc, para_elem, image_cache, ns):
    """XML Paragraph 요소를 순회하며 docx paragraph에 텍스트+이미지 삽입"""
    from docx.shared import Emu
    HWPUNIT_PER_INCH = 7200

    paragraph = doc.add_paragraph()
    # LineSeg가 있으면 그 안의 자식을 순회, 없으면 직접 자식 순회
    containers = para_elem.findall('LineSeg')
    if not containers:
        containers = [para_elem]

    for container in containers:
        for child in container:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

            if tag == 'Text':
                text = child.text or ''
                if text:
                    paragraph.add_run(text)

            elif tag == 'ControlChar':
                name = child.get('name', '')
                if name == 'LINE_BREAK':
                    paragraph.add_run('\n')

            elif tag == 'GShapeObjectControl':
                # ShapePicture → PictureInfo/@bindata-id 찾기
                pic_info = child.find('.//PictureInfo')
                if pic_info is None:
                    continue
                bid_str = pic_info.get('bindata-id', '0')
                try:
                    bid = int(bid_str)
                except ValueError:
                    continue
                if bid <= 0 or bid not in image_cache:
                    continue

                # 크기 정보 (ShapeComponent의 width)
                shape_comp = child.find('.//ShapeComponent')
                width_hwp = 0
                if shape_comp is not None:
                    try:
                        width_hwp = int(shape_comp.get('width', '0'))
                    except ValueError:
                        pass

                if width_hwp > 0:
                    width_emu = int(width_hwp * 914400 / HWPUNIT_PER_INCH)
                else:
                    width_emu = int(5.5 * 914400)  # 기본 5.5 inches

                img = image_cache[bid]
                img.seek(0)
                try:
                    run = paragraph.add_run()
                    run.add_picture(img, width=Emu(width_emu))
                except Exception:
                    pass

            elif tag == 'TableControl':
                _hwp_process_table(doc, child, image_cache, ns)

    return paragraph


def _hwp_process_table(doc, table_elem, image_cache, ns):
    """XML TableControl 요소를 docx 테이블로 변환"""
    table_body = table_elem.find('.//TableBody')
    if table_body is None:
        return
    rows = table_body.findall('TableRow')
    if not rows:
        return
    first_cells = rows[0].findall('TableCell')
    num_cols = max(len(first_cells), 1)
    table = doc.add_table(rows=len(rows), cols=num_cols)
    for row_idx, row_elem in enumerate(rows):
        cells = row_elem.findall('TableCell')
        for col_idx, cell_elem in enumerate(cells):
            if col_idx >= num_cols:
                break
            cell = table.cell(row_idx, col_idx)
            paras = cell_elem.findall('Paragraph')
            for i, cp in enumerate(paras):
                if i == 0 and cell.paragraphs:
                    # 기존 빈 paragraph에 내용 추가
                    _hwp_fill_paragraph(cell.paragraphs[0], cp, image_cache, ns)
                else:
                    _hwp_process_paragraph_into_cell(cell, cp, image_cache, ns)


def _hwp_fill_paragraph(paragraph, para_elem, image_cache, ns):
    """기존 paragraph에 XML 내용 채우기"""
    from docx.shared import Emu
    HWPUNIT_PER_INCH = 7200
    containers = para_elem.findall('LineSeg')
    if not containers:
        containers = [para_elem]
    for container in containers:
        for child in container:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'Text':
                text = child.text or ''
                if text:
                    paragraph.add_run(text)
            elif tag == 'GShapeObjectControl':
                pic_info = child.find('.//PictureInfo')
                if pic_info is None:
                    continue
                try:
                    bid = int(pic_info.get('bindata-id', '0'))
                except ValueError:
                    continue
                if bid <= 0 or bid not in image_cache:
                    continue
                shape_comp = child.find('.//ShapeComponent')
                width_hwp = 0
                if shape_comp is not None:
                    try:
                        width_hwp = int(shape_comp.get('width', '0'))
                    except ValueError:
                        pass
                width_emu = int(width_hwp * 914400 / HWPUNIT_PER_INCH) if width_hwp > 0 else int(5.5 * 914400)
                img = image_cache[bid]
                img.seek(0)
                try:
                    run = paragraph.add_run()
                    run.add_picture(img, width=Emu(width_emu))
                except Exception:
                    pass


def _hwp_process_paragraph_into_cell(cell, para_elem, image_cache, ns):
    """cell에 새 paragraph 추가 후 내용 채우기"""
    p = cell.add_paragraph()
    _hwp_fill_paragraph(p, para_elem, image_cache, ns)


def _hwp_to_docx_mac(input_path, output_path):
    """macOS: hwp5 XML 모델 기반 HWP→DOCX 변환 (이미지 원본 위치 매핑)"""
    import io
    from contextlib import closing
    from hwp5.xmlmodel import Hwp5File
    from xml.etree import ElementTree as ET

    # 1. BinData 이미지 추출 (olefile)
    image_cache = _extract_bindata_images(input_path)

    try:
        # 2. hwp5 XML 생성 + 파싱
        with closing(Hwp5File(input_path)) as hwp5file:
            xml_buf = io.BytesIO()
            hwp5file.xmlevents().dump(xml_buf)
            xml_buf.seek(0)

        tree = ET.parse(xml_buf)
        root = tree.getroot()

        # 3. XML 순회하며 DOCX 생성
        doc = DocxDocument()

        # 부모 맵 구축 (테이블 셀 내부 Paragraph 필터링용)
        parent_map = {c: p for p in root.iter() for c in p}

        # BodyText 내 모든 Paragraph를 순서대로 처리
        # 단, TableCell 내부 Paragraph는 _hwp_process_table에서 처리하므로 건너뜀
        body_text = root.find('.//BodyText')
        if body_text is None:
            body_text = root

        def _walk_elements(container):
            """재귀적으로 Paragraph와 TableControl을 찾아 처리"""
            for child in container:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag == 'Paragraph':
                    _hwp_process_paragraph(doc, child, image_cache, None)
                elif tag == 'TableControl':
                    _hwp_process_table(doc, child, image_cache, None)
                elif tag in ('SectionDef', 'ColumnSet', 'Column'):
                    # 중간 컨테이너는 재귀 탐색
                    _walk_elements(child)

        _walk_elements(body_text)

        doc.save(output_path)

    except Exception:
        # XML 파싱 실패 시 fallback: 텍스트만 추출
        _hwp_to_docx_mac_fallback(input_path, output_path, image_cache)



def _hwp_to_docx_mac_fallback(input_path, output_path, image_cache):
    """Fallback: hwp5txt로 텍스트 추출 + 이미지 끝에 추가"""
    import io
    from contextlib import closing
    from hwp5.hwp5txt import Hwp5File, TextTransform
    from docx.shared import Inches

    text_transform = TextTransform()
    buf = io.BytesIO()
    with closing(Hwp5File(input_path)) as hwp5file:
        text_transform.transform_hwp5_to_text(hwp5file, buf)
    text = buf.getvalue().decode('utf-8', errors='replace')

    doc = DocxDocument()
    for line in text.splitlines():
        doc.add_paragraph(line)
    if image_cache:
        for img in image_cache.values():
            img.seek(0)
            try:
                doc.add_picture(img, width=Inches(5.5))
            except Exception:
                pass
    doc.save(output_path)


def _hwp_convert_worker(input_path, output_path, direction, save_fmt, result_q):
    """별도 스레드에서 HWP 변환 (Windows: COM, macOS: pyhwp)"""
    if not _IS_WINDOWS:
        # macOS
        if direction == 'WORD_TO_HWP':
            result_q.put({"status": "error", "message": "Word→HWP conversion is not supported on macOS."})
            return
        try:
            _hwp_to_docx_mac(input_path, output_path)
            result_q.put({"status": "success", "method": "pyhwp"})
        except Exception as e:
            result_q.put({"status": "error", "message": str(e)})
        return

    # Windows: COM 자동화
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
            r = hwp.Open(input_path, "OOXML", "")
            if r:
                text = hwp.GetTextFile("TEXT", "")
                if text and not text.startswith("PK"):
                    open_ok = True
                    used_method = "direct"
                else:
                    hwp.Clear(1)

            if not open_ok:
                html_path = _docx_to_html(input_path)
                for fmt in ["HTML", ""]:
                    r = hwp.Open(html_path, fmt, "")
                    if r:
                        open_ok = True
                        used_method = "html"
                        break
        else:
            for fmt in ["HWP", ""]:
                r = hwp.Open(input_path, fmt, "")
                if r:
                    open_ok = True
                    break

        if not open_ok:
            result_q.put({"status": "error", "message": "파일 열기 실패"})
            return

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

        if not _IS_WINDOWS and direction == 'WORD_TO_HWP':
            return {"status": "error", "message": "Word→HWP conversion is not supported on macOS."}

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
