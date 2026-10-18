"""Local API and packaged download worker entry point."""

import os
import sys


def create_app():
    import secrets
    from contextlib import asynccontextmanager

    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from jobs import DownloadManager
    from media import DownloadRequest
    from yt_dlp.version import __version__

    manager = DownloadManager()
    token = os.environ.get("ONEHUB_API_TOKEN", "")

    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.close()

    app = FastAPI(title="OneHub YouTube API", lifespan=lifespan)
    app.state.downloads = manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "null"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-OneHub-Token"],
    )

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        if (
            request.method != "OPTIONS"
            and token
            and not secrets.compare_digest(
                request.headers.get("X-OneHub-Token", ""), token
            )
        ):
            return JSONResponse(status_code=401, content={"message": "Unauthorized"})
        origin = request.headers.get("origin")
        if origin and origin not in {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "null",
        }:
            return JSONResponse(
                status_code=403, content={"message": "Origin not allowed"}
            )
        return await call_next(request)

    @app.get("/")
    def health():
        return {"status": "ok", "app": "onehub", "yt_dlp": __version__}

    @app.post("/media/download", status_code=202)
    def download(request: DownloadRequest):
        try:
            return manager.start(request)
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        except OSError as error:
            raise HTTPException(
                400, "저장 폴더에 쓸 수 없습니다. 경로와 권한을 확인해 주세요."
            ) from error

    @app.get("/media/status/{job_id}")
    def status(job_id: str):
        try:
            return manager.snapshot(job_id)
        except KeyError as error:
            raise HTTPException(404, "Download not found") from error

    @app.post("/media/cancel/{job_id}")
    def cancel(job_id: str):
        try:
            return manager.cancel(job_id)
        except KeyError as error:
            raise HTTPException(404, "Download not found") from error

    @app.post("/shutdown")
    def shutdown():
        manager.close()
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if "--download-worker" in sys.argv:
        from worker import run_worker

        sys.exit(run_worker())
    import socket

    import uvicorn

    # Bind port 0 for Electron so unrelated services never need to be terminated.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", int(os.environ.get("ONEHUB_PORT", "8000"))))
    print(f"ONEHUB_PORT={sock.getsockname()[1]}", flush=True)
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level="info"))
    server.run(sockets=[sock])
