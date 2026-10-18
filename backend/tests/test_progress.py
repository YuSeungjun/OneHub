import io
import json

import pytest
import worker
from progress import ProgressReporter


def test_progress_protocol_preserves_unicode_on_legacy_windows_stdout(monkeypatch):
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp949")
    monkeypatch.setattr(worker.sys, "stdout", stream)
    worker.emit(title="한글 日本語 🎵", saved_path="D:/음악/완료.mp3")
    encoded = buffer.getvalue().decode("ascii")
    assert json.loads(encoded)["title"] == "한글 日本語 🎵"


def test_stream_progress_contains_real_bytes_speed_eta():
    events = []
    reporter = ProgressReporter(lambda **event: events.append(event))
    reporter.download(
        {
            "status": "downloading",
            "downloaded_bytes": 25,
            "total_bytes": 100,
            "speed": 10,
            "eta": 8,
            "info_dict": {"format_id": "video", "vcodec": "avc1"},
        }
    )
    assert events[-1]["progress"] == 25
    assert events[-1]["downloaded_bytes"] == 25
    assert events[-1]["speed"] == 10
    assert events[-1]["eta"] == 8
    # A new audio stream must be reported immediately, even inside the throttle window.
    reporter.download(
        {
            "status": "downloading",
            "downloaded_bytes": 50,
            "total_bytes_estimate": 200,
            "info_dict": {"format_id": "audio", "vcodec": "none"},
        }
    )
    assert events[-1]["stream_kind"] == "audio"
    assert events[-1]["total_estimated"] is True
    assert events[-1]["progress"] == 25


def test_finished_stream_and_conversion_are_not_save_completion():
    events = []
    reporter = ProgressReporter(lambda **event: events.append(event))
    reporter.download(
        {"status": "finished", "downloaded_bytes": 100, "total_bytes": 100}
    )
    assert events[-1]["status"] == "downloading"
    assert events[-1]["progress"] < 100
    reporter.postprocess({"status": "started"})
    assert events[-1]["status"] == "processing"
    assert events[-1]["progress"] is None
    assert not any(event["status"] == "success" for event in events)


def test_unknown_sizes_and_invalid_numbers_do_not_invent_progress():
    events = []
    ProgressReporter(lambda **event: events.append(event)).download(
        {
            "status": "downloading",
            "downloaded_bytes": 100,
            "speed": float("nan"),
            "eta": float("inf"),
        }
    )
    assert events[0]["progress"] is None
    assert events[0]["speed"] is None
    assert events[0]["eta"] is None
    json.dumps(events, allow_nan=False)


@pytest.mark.parametrize("save_file", [True, False])
def test_worker_only_signals_success_after_final_file_exists(
    monkeypatch, capsys, tmp_path, save_file
):
    output = tmp_path / "완료.mp3"

    class Downloader:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            if save_file:
                output.write_bytes(b"saved")
            for hook in self.options["post_hooks"]:
                hook(str(output))
            return 0

    monkeypatch.setattr(worker.yt_dlp, "YoutubeDL", Downloader)
    monkeypatch.setattr(worker, "download_options", lambda *args: {})
    monkeypatch.setattr(
        worker.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "request": {"url": "https://youtu.be/jBIqI9I5IPg"},
                    "staging": str(tmp_path),
                }
            )
        ),
    )
    assert worker.run_worker() == (0 if save_file else 1)
    event = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert event["status"] == ("success" if save_file else "error")
    if save_file:
        assert event["saved_path"] == str(output)
