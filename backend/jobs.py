"""Own a single download and terminate only that job's process tree."""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from uuid import uuid4

import psutil

ACTIVE = {"starting", "downloading", "processing", "retrying", "canceling"}
logger = logging.getLogger("onehub.jobs")


def stop_process_tree(process):
    if process.poll() is not None:
        return
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        # Stop the worker before it can spawn another ffmpeg/runtime process.
        parent.kill()
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs([parent, *children], timeout=5)
    except psutil.NoSuchProcess:
        pass


class DownloadManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._state = None
        self._process = None
        self._monitor_thread = None

    def snapshot(self, job_id=None):
        with self._lock:
            if not self._state or (job_id and self._state["id"] != job_id):
                raise KeyError("Download not found")
            return dict(self._state)

    def start(self, request):
        with self._lock:
            if self._state and self._state["status"] in ACTIVE:
                raise RuntimeError("이미 다운로드가 진행 중입니다.")
            destination = (
                Path(request.download_path or Path.home() / "Downloads")
                .expanduser()
                .resolve()
            )
            destination.mkdir(parents=True, exist_ok=True)
            request = request.model_copy(update={"download_path": str(destination)})
            staging = Path(tempfile.mkdtemp(prefix=".onehub-", dir=destination))
            command = [sys.executable]
            if not getattr(sys, "frozen", False):
                command += [str(Path(__file__).with_name("main.py"))]
            command += ["--download-worker"]
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=None,
                    text=True,
                    encoding="utf-8",
                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32"
                    else 0,
                )
                process.stdin.write(
                    json.dumps(
                        {"request": request.model_dump(), "staging": str(staging)}
                    )
                )
                process.stdin.write("\n")
                process.stdin.close()
            except Exception:
                if "process" in locals():
                    stop_process_tree(process)
                shutil.rmtree(staging)
                raise
            self._state = {
                "id": uuid4().hex,
                "status": "starting",
                "progress": None,
                "message": "",
            }
            self._process = process
            self._monitor_thread = threading.Thread(
                target=self._monitor, args=(process, staging), daemon=True
            )
            self._monitor_thread.start()
            return dict(self._state)

    def _monitor(self, process, staging):
        terminal = None
        try:
            for line in process.stdout:
                try:
                    update = json.loads(line)
                except (ValueError, TypeError):
                    logger.warning("Unexpected worker output: %s", line.rstrip())
                    continue
                with self._lock:
                    if update.get("status") in {"success", "error"}:
                        terminal = update
                    elif (
                        self._state["status"] != "canceling"
                        and update.get("status") in ACTIVE
                    ):
                        self._state.update(update)
            process.wait()
        except Exception:
            logger.exception("Could not read download progress")
            with self._lock:
                stop_process_tree(process)
        finally:
            process.stdout.close()
            with self._lock:
                # Cancellation holds this lock until ffmpeg and other children
                # have exited. Wait before removing files they may still hold open.
                try:
                    shutil.rmtree(staging)
                except OSError:
                    logger.exception(
                        "Could not remove job temporary directory: %s", staging
                    )
                if self._state["status"] == "canceling":
                    self._state.update(status="canceled", progress=0)
                else:
                    self._state.update(
                        terminal
                        or {
                            "status": "error",
                            "progress": 0,
                            "message": "다운로드 프로세스가 종료되었습니다. 앱 로그를 확인해 주세요.",
                        }
                    )
                self._process = None

    def cancel(self, job_id):
        with self._lock:
            state = self.snapshot(job_id)
            if state["status"] not in ACTIVE:
                return state
            self._state["status"] = "canceling"
            process = self._process
            # Keep ownership until the process tree has stopped. The monitor marks
            # this job terminal only after cleanup, so a new job cannot race it.
            stop_process_tree(process)
            return dict(self._state)

    def close(self):
        with self._lock:
            if self._state and self._state["status"] in ACTIVE:
                self.cancel(self._state["id"])
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
