"""One isolated download process. stdout is a JSON-lines progress protocol."""

import json
import logging
import sys
from pathlib import Path

import yt_dlp
from media import DownloadRequest, download_options, error_message
from progress import ProgressReporter


def emit(**payload):
    # Keep the pipe protocol ASCII-safe even when a frozen Windows runtime uses
    # a legacy console encoding. json.loads restores the original Unicode text.
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def run_worker():
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    reporter = ProgressReporter(emit)
    saved_files = []

    try:
        payload = json.loads(sys.stdin.readline())
        req = DownloadRequest.model_validate(payload["request"])
        options = download_options(
            req, payload["staging"], reporter.download, reporter.postprocess
        )
        options["post_hooks"] = [saved_files.append]
        # Re-extract fresh media URLs once after a 403; never loop indefinitely or
        # force clients that require authentication/PO tokens.
        for attempt in range(2):
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    result = ydl.download([req.url])
                    if result:
                        raise RuntimeError("다운로드가 완료되지 않았습니다.")
                break
            except yt_dlp.utils.DownloadError as error:
                if attempt or "403" not in str(error):
                    raise
                emit(status="retrying", progress=None, speed=None, eta=None)
                options["cachedir"] = False
        if not saved_files or not all(
            Path(filename).is_file() for filename in saved_files
        ):
            raise RuntimeError(
                "저장된 파일을 확인할 수 없습니다. 저장 폴더를 확인해 주세요."
            )
        emit(
            status="success",
            progress=100,
            saved_path=str(Path(saved_files[-1]).resolve()),
            speed=None,
            eta=None,
        )
    except Exception as error:
        logging.getLogger("onehub.worker").exception("Download failed")
        emit(status="error", progress=0, message=error_message(error))
        return 1
    return 0
