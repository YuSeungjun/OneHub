import subprocess
import sys
import time

import jobs
import psutil
import pytest
from media import DownloadRequest


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for worker")


def test_cancel_stops_only_owned_processes_and_cleans_only_owned_files(
    monkeypatch, tmp_path
):
    original_popen = subprocess.Popen
    fake_worker = """
import json, pathlib, subprocess, sys, time
payload = json.loads(sys.stdin.readline())
pathlib.Path(payload['staging'], 'ours.part').write_text('partial')
locked_file = pathlib.Path(payload['staging'], 'child.temp')
child = subprocess.Popen([sys.executable, '-c', 'import sys, time; handle = open(sys.argv[1], "w"); time.sleep(60)', str(locked_file)])
while not locked_file.exists():
    time.sleep(.01)
print(json.dumps({'status': 'downloading', 'progress': 20, 'child_pid': child.pid}), flush=True)
time.sleep(60)
"""
    monkeypatch.setattr(
        jobs.subprocess,
        "Popen",
        lambda command, **kwargs: original_popen(
            [sys.executable, "-c", fake_worker], **kwargs
        ),
    )
    unrelated = tmp_path / "someone-elses.part"
    unrelated.write_text("keep")
    manager = jobs.DownloadManager()
    try:
        request = DownloadRequest(
            url="https://youtu.be/jBIqI9I5IPg", download_path=str(tmp_path)
        )
        state = manager.start(request)
        wait_for(lambda: manager.snapshot()["status"] == "downloading")
        child_pid = manager.snapshot()["child_pid"]
        with pytest.raises(RuntimeError):
            manager.start(request)
        with pytest.raises(KeyError):
            manager.cancel("another-job")
        manager.cancel(state["id"])
        wait_for(lambda: manager.snapshot()["status"] == "canceled")
        assert unrelated.read_text() == "keep"
        assert not list(tmp_path.glob(".onehub-*"))
        assert not psutil.pid_exists(child_pid)
        # A fresh job can start only after the canceled job's cleanup is complete.
        second = manager.start(request)
        assert second["id"] != state["id"]
        manager.cancel(second["id"])
    finally:
        manager.close()
