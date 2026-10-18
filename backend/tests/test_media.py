import io
import json
from unittest.mock import patch

import pytest
import worker
import yt_dlp
from fastapi.testclient import TestClient
from main import create_app
from media import DownloadRequest, download_options, error_message, youtube_url
from pydantic import ValidationError

VIDEO = "jBIqI9I5IPg"
URL = f"https://www.youtube.com/watch?v={VIDEO}"


@pytest.mark.parametrize(
    "url",
    [
        f"{URL}&list=RD{VIDEO}&start_radio=1",
        f"https://youtu.be/{VIDEO}?si=abc",
        f"https://www.youtube.com/shorts/{VIDEO}",
        f"https://www.youtube.com/live/{VIDEO}",
        f"https://music.youtube.com/watch?v={VIDEO}",
    ],
)
def test_accepts_only_the_selected_video(url):
    assert youtube_url(url) == URL


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/watch?v=jBIqI9I5IPg",
        "file:///etc/passwd",
        "https://youtube.com.evil.test/watch?v=jBIqI9I5IPg",
        "https://youtube.com/playlist?list=123",
        "https://youtube.com/watch?v=bad",
        "https://youtube.com:8000/watch?v=jBIqI9I5IPg",
        "https://user:pass@youtube.com/watch?v=jBIqI9I5IPg",
    ],
)
def test_rejects_non_video_urls(url):
    with pytest.raises(ValueError):
        youtube_url(url)


def test_invalid_output_settings_rejected():
    with pytest.raises(ValidationError):
        DownloadRequest(url=URL, format="exe")
    with pytest.raises(ValidationError):
        DownloadRequest(url=URL, resolution="8K")


@pytest.mark.parametrize(
    "resolution,height", [("720p", 720), ("1080p", 1080), ("4K", 2160)]
)
def test_resolution_limit_applies_to_all_fallbacks(resolution, height, tmp_path):
    with patch("media.js_runtimes", return_value={"node": {}}):
        options = download_options(
            DownloadRequest(url=URL, resolution=resolution),
            tmp_path,
            lambda _: None,
            lambda _: None,
        )
    # Exercise yt-dlp's actual format selector with synthetic formats.
    formats = [
        {
            "format_id": f"mp4-{h}",
            "ext": "mp4",
            "height": h,
            "vcodec": "avc1",
            "acodec": "aac",
            "url": f"https://example.com/{h}",
            "protocol": "https",
        }
        for h in [720, 1080, 2160, 4320]
    ]
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        selected = list(
            ydl.build_format_selector(options["format"])(
                {
                    "formats": formats,
                    "has_merged_format": True,
                    "incomplete_formats": False,
                }
            )
        )
    assert selected[0]["height"] == height


def test_api_removes_documents_and_validates_requests(monkeypatch):
    monkeypatch.delenv("ONEHUB_API_TOKEN", raising=False)
    with TestClient(create_app()) as client:
        assert client.post("/doc/convert").status_code == 404
        assert (
            client.post(
                "/media/download", json={"url": "https://example.com"}
            ).status_code
            == 422
        )
        assert client.get("/media/status/missing").status_code == 404
        assert (
            client.get("/", headers={"Origin": "https://example.com"}).status_code
            == 403
        )


def test_api_token_required(monkeypatch):
    monkeypatch.setenv("ONEHUB_API_TOKEN", "test-token")
    with TestClient(create_app()) as client:
        assert client.get("/").status_code == 401
        assert (
            client.get("/", headers={"X-OneHub-Token": "test-token"}).status_code == 200
        )


def test_403_is_reextracted_once_and_reported_without_traceback(
    monkeypatch, capsys, tmp_path
):
    calls = []

    class RefusingDownloader:
        def __init__(self, options):
            calls.append(dict(options))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            raise yt_dlp.utils.DownloadError("ERROR: HTTP Error 403: Forbidden")

    monkeypatch.setattr(worker.yt_dlp, "YoutubeDL", RefusingDownloader)
    monkeypatch.setattr(worker, "download_options", lambda *args: {})
    monkeypatch.setattr(
        worker.sys,
        "stdin",
        io.StringIO(json.dumps({"request": {"url": URL}, "staging": str(tmp_path)})),
    )
    assert worker.run_worker() == 1
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(calls) == 2
    assert calls[1]["cachedir"] is False
    assert events[0]["status"] == "retrying"
    assert events[-1]["status"] == "error"
    assert "403" in events[-1]["message"]
    assert "Traceback" not in events[-1]["message"]


def test_error_details_are_bounded():
    assert "Traceback" not in error_message("Failed\nTraceback private path")
    assert len(error_message("x" * 2000)) <= 600
