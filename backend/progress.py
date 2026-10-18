"""Translate yt-dlp stream events into bounded, JSON-safe UI progress."""

import math
import time


def positive_number(value):
    if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
        return value
    return None


class ProgressReporter:
    def __init__(self, emit):
        self.emit = emit
        self.last_update = 0
        self.last_stream = None

    def download(self, data):
        status = data.get("status")
        if status not in {"downloading", "finished"}:
            return
        info = data.get("info_dict") or {}
        stream = info.get("format_id") or data.get("filename")
        now = time.monotonic()
        if (
            status == "downloading"
            and stream == self.last_stream
            and now - self.last_update < 0.25
        ):
            return
        self.last_update, self.last_stream = now, stream
        downloaded = positive_number(data.get("downloaded_bytes")) or 0
        total = positive_number(data.get("total_bytes")) or positive_number(
            data.get("total_bytes_estimate")
        )
        # This is the current stream's progress. Completion of a stream does not
        # mean that merging, conversion and saving the final file have completed.
        percent = min(99, int(downloaded / total * 100)) if total else None
        kind = "audio" if info.get("vcodec") == "none" else "video"
        self.emit(
            status="downloading",
            progress=percent,
            stream_kind=kind,
            downloaded_bytes=downloaded,
            total_bytes=total,
            total_estimated=not bool(data.get("total_bytes")),
            speed=positive_number(data.get("speed"))
            if status == "downloading"
            else None,
            eta=positive_number(data.get("eta")) if status == "downloading" else None,
            title=info.get("title", ""),
        )

    def postprocess(self, data):
        if data.get("status") in {"started", "processing"}:
            self.emit(status="processing", progress=None, speed=None, eta=None)
