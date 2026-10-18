"""YouTube validation and yt-dlp options shared by the API and its worker."""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

import imageio_ffmpeg
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("onehub.download")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


def youtube_url(value: str) -> str:
    """Keep one video only, discarding radio/playlist/tracking parameters."""
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
            raise ValueError
        if parsed.port not in {None, 80, 443}:
            raise ValueError
        parts = parsed.path.strip("/").split("/")
        if parsed.hostname in {"youtu.be", "www.youtu.be"} and len(parts) == 1:
            video_id = parts[0]
        elif parsed.hostname in YOUTUBE_HOSTS:
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}:
                video_id = parts[1]
            else:
                raise ValueError
        else:
            raise ValueError
        if not VIDEO_ID.fullmatch(video_id):
            raise ValueError
        return f"https://www.youtube.com/watch?v={video_id}"
    except ValueError:
        raise ValueError(
            "YouTube 영상 링크를 입력해 주세요. 재생목록과 다른 사이트는 지원하지 않습니다."
        ) from None


class DownloadRequest(BaseModel):
    url: str = Field(max_length=2048)
    format: Literal["mp4", "mp3"] = "mp4"
    resolution: Literal["4K", "1080p", "720p"] = "1080p"
    download_path: str = Field(default="", max_length=4096)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        return youtube_url(value)


def js_runtimes():
    # Packaged builds ship a standalone Node executable alongside the backend.
    node = os.environ.get("ONEHUB_NODE_PATH") or shutil.which("node")
    if node and Path(node).is_file():
        return {"node": {"path": node}}
    deno = shutil.which("deno")
    if deno:
        return {"deno": {"path": deno}}
    raise RuntimeError(
        "YouTube 다운로드에 필요한 JavaScript 실행기가 없습니다. Node.js 22 이상을 설치하거나 앱을 다시 설치해 주세요."
    )


def download_options(req, staging, progress_hook, postprocessor_hook):
    options = {
        "noplaylist": True,
        "js_runtimes": js_runtimes(),
        "logger": logger,
        "quiet": True,
        "noprogress": True,
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_retries": 2,
        "concurrent_fragment_downloads": 2,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "paths": {"home": req.download_path, "temp": str(staging)},
        "outtmpl": "%(title).150B [%(id)s].%(ext)s",
        "windowsfilenames": True,
        "overwrites": False,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
    }
    if req.format == "mp3":
        options.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )
    else:
        height = {"4K": 2160, "1080p": 1080, "720p": 720}[req.resolution]
        # Apply the requested height to every fallback, including combined streams.
        options.update(
            {
                "format": (
                    f"bv[ext=mp4][vcodec^=avc1][height<={height}]+ba[ext=m4a]/"
                    f"bv[ext=mp4][height<={height}]+ba[ext=m4a]/"
                    f"b[ext=mp4][height<={height}]/"
                    f"bv[height<={height}]+ba/b[height<={height}]"
                ),
                "merge_output_format": "mp4",
                "postprocessors": [
                    {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
                ],
                "postprocessor_args": {"videoremuxer": ["-movflags", "+faststart"]},
            }
        )
    return options


def error_message(error):
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(error)).removeprefix("ERROR: ").strip()
    if "403" in message:
        return (
            "YouTube에서 다운로드를 거부했습니다(403). 최신 다운로드 엔진으로 다시 시도했지만 실패했습니다. "
            "잠시 후 재시도하고, 계속되면 앱 업데이트와 해당 영상의 로그인·지역 제한을 확인해 주세요."
        )
    if "sign in" in message.lower() or "login" in message.lower():
        return "YouTube에서 로그인을 요구하는 영상입니다. 공개 상태로 재생할 수 있는 영상인지 확인해 주세요."
    return (
        message.split("Traceback")[0].strip()[:600]
        or "다운로드 중 오류가 발생했습니다."
    )
