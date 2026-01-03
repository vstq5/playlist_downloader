from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Header, HTTPException, Request
from fastapi.responses import FileResponse

from ..schemas import InitRequest, StartRequest
from ..rate_limit import limiter
from ...config import get_settings
from ...utils.download_tokens import create_download_token, verify_download_token

router = APIRouter(prefix="/api", tags=["tasks"])


@router.post("/prepare")
@limiter.limit("60/minute")
async def prepare_download(
    request: Request,
    background_tasks: BackgroundTasks,
    init_req: InitRequest = Body(...),
    x_device_id: Optional[str] = Header(None),
):
    settings = get_settings()
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    # Capacity controls: prevent one device from enqueueing unlimited work.
    queued_statuses = ["pending", "preparing", "queued", "ready"]
    running_statuses = ["downloading", "zipping"]
    queued_count = await request.app.state.db.count_tasks_for_owner(owner_id=x_device_id, statuses=queued_statuses)
    running_count = await request.app.state.db.count_tasks_for_owner(owner_id=x_device_id, statuses=running_statuses)
    if queued_count >= int(getattr(settings, "MAX_QUEUED_TASKS_PER_OWNER", 2)):
        raise HTTPException(status_code=429, detail="Too many queued downloads for this device")
    if running_count >= int(getattr(settings, "MAX_RUNNING_TASKS_PER_OWNER", 1)) and queued_count >= int(
        getattr(settings, "MAX_QUEUED_TASKS_PER_OWNER", 2)
    ):
        raise HTTPException(status_code=429, detail="Too many active downloads for this device")

    tid = str(int(datetime.now().timestamp() * 1000))
    await request.app.state.db.create_task(tid, init_req.url, init_req.options, owner_id=x_device_id)

    if not request.app.state.download_service or not bool(getattr(settings, "ALLOW_INPROCESS_DOWNLOADS", True)):
        raise HTTPException(status_code=503, detail="Download service unavailable")

    background_tasks.add_task(request.app.state.download_service.fetch_playlist_info, tid, init_req.url)

    return {"task_id": tid}


@router.post("/start/{task_id}")
async def start_download(
    task_id: str,
    background_tasks: BackgroundTasks,
    req: Request,
    x_device_id: Optional[str] = Header(None),
    body: Optional[StartRequest] = None,
):
    settings = get_settings()
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    # Capacity controls: only allow N concurrent running tasks per device.
    running_statuses = ["downloading", "zipping"]
    running_count = await req.app.state.db.count_tasks_for_owner(owner_id=x_device_id, statuses=running_statuses)
    if running_count >= int(getattr(settings, "MAX_RUNNING_TASKS_PER_OWNER", 1)):
        raise HTTPException(status_code=429, detail="Another download is already running for this device")

    task = await req.app.state.db.get_task_for_owner(task_id, x_device_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Persist user's track selection
    if body and body.selected_indices is not None:
        task["options"] = task.get("options", {})
        task["options"]["selected_indices"] = body.selected_indices
        await req.app.state.db.save_full_task_state(task_id, task)

    if not req.app.state.download_service or not bool(getattr(settings, "ALLOW_INPROCESS_DOWNLOADS", True)):
        raise HTTPException(status_code=503, detail="Download service unavailable")

    background_tasks.add_task(req.app.state.download_service.process_download, task_id)

    return {"status": "started"}


@router.get("/tasks")
async def get_tasks(request: Request, x_device_id: Optional[str] = Header(None)):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    tasks = await request.app.state.db.get_all_tasks(owner_id=x_device_id)
    return list(tasks.values())


@router.delete("/delete/{task_id}")
async def delete_task(request: Request, task_id: str, x_device_id: Optional[str] = Header(None)):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    deleted = await request.app.state.db.delete_task(task_id, owner_id=x_device_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@router.post("/cancel/{task_id}")
async def cancel_task(request: Request, task_id: str, x_device_id: Optional[str] = Header(None)):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    ok = await request.app.state.db.request_cancel(task_id, owner_id=x_device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "cancel_requested"}


@router.get("/download_file/{task_id}")
async def download_file(
    request: Request,
    task_id: str,
    token: Optional[str] = None,
    x_device_id: Optional[str] = Header(None),
):
    # Browser downloads via <a> cannot attach custom headers reliably, so we support
    # a short-lived signed token in the query string.
    owner_id: Optional[str] = None
    if token:
        settings = get_settings()
        payload = verify_download_token(token=token, secret=settings.SECRET_KEY)
        if not payload or payload.get("task_id") != task_id:
            raise HTTPException(status_code=404, detail="File not ready")
        owner_id = payload.get("owner_id")
    else:
        if not x_device_id:
            raise HTTPException(status_code=400, detail="X-Device-ID header required")
        owner_id = x_device_id

    if not owner_id:
        raise HTTPException(status_code=404, detail="File not ready")

    # Verify DB ownership strictly.
    task_owner = await request.app.state.db.get_task_owner_id(task_id)
    if not task_owner or task_owner != owner_id:
        raise HTTPException(status_code=404, detail="File not ready")

    task = await request.app.state.db.get_task(task_id)
    if not task or not task.get("zip_path"):
        raise HTTPException(status_code=404, detail="File not ready")

    file_path = Path(task["zip_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File expired or missing")

    media_type = "application/octet-stream"
    if file_path.suffix == ".zip":
        media_type = "application/zip"
    elif file_path.suffix == ".mp3":
        media_type = "audio/mpeg"
    elif file_path.suffix == ".m4a":
        media_type = "audio/mp4"
    elif file_path.suffix == ".flac":
        media_type = "audio/flac"

    return FileResponse(file_path, filename=file_path.name, media_type=media_type)


@router.get("/download_token/{task_id}")
async def download_token(request: Request, task_id: str, x_device_id: Optional[str] = Header(None)):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")

    task = await request.app.state.db.get_task_for_owner(task_id, x_device_id)
    if not task or not task.get("zip_path"):
        raise HTTPException(status_code=404, detail="File not ready")

    settings = get_settings()
    token = create_download_token(task_id=task_id, owner_id=x_device_id, secret=settings.SECRET_KEY, ttl_seconds=600)
    return {"token": token}


@router.get("/history")
async def get_history(request: Request, x_device_id: Optional[str] = Header(None)):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="X-Device-ID header required")
    return await request.app.state.db.get_recent_tasks(limit=10, owner_id=x_device_id)


@router.get("/health/diagnose")
async def diagnose_health(request: Request):
    """Run self-check diagnostics for debugging crashes/issues."""
    import shutil
    import subprocess
    import sys
    import importlib
    
    results = {
        "status": "ok",
        "checks": {}
    }
    
    # 1. yt-dlp check
    try:
        import yt_dlp

        yt_dlp_version = getattr(yt_dlp, "__version__", None) or "unknown"
        results["checks"]["yt_dlp"] = {"status": "ok", "version": yt_dlp_version}
    except Exception as e:
        results["checks"]["yt_dlp"] = {"status": "error", "error": str(e)}
        results["status"] = "warning"

    # 2. ffmpeg check
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        results["checks"]["ffmpeg"] = {"status": "ok", "path": ffmpeg_path}
    else:
        results["checks"]["ffmpeg"] = {"status": "error", "error": "ffmpeg not found in PATH"}
        results["status"] = "error"

    # 3. Connectivity (Ping YouTube)
    try:
        import requests
        resp = requests.head("https://www.youtube.com", timeout=5)
        results["checks"]["connectivity"] = {"status": "ok", "code": resp.status_code}
    except Exception as e:
        results["checks"]["connectivity"] = {"status": "error", "error": str(e)}
        results["status"] = "error"

    # 4. Memory (RSS)
    try:
        psutil = importlib.import_module("psutil")
        process = psutil.Process()  # type: ignore[attr-defined]
        mem_info = process.memory_info()
        rss_mb = mem_info.rss / 1024 / 1024
        results["checks"]["memory"] = {"status": "ok", "rss_mb": round(rss_mb, 2)}
    except ModuleNotFoundError:
        results["checks"]["memory"] = {"status": "skipped", "error": "psutil not installed"}

    # 5. Environment Config
    settings = request.app.state.settings
    results["checks"]["config"] = {
        "YTDLP_MAX_WORKERS": getattr(settings, "YTDLP_MAX_WORKERS", "unset"),
        "YTDLP_COOKIES_BROWSER": getattr(settings, "YTDLP_COOKIES_BROWSER", "unset"),
        "YTDLP_PROXY": "configured" if getattr(settings, "YTDLP_PROXY", "") else "none"
    }

    return results
