from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...core.paths import LEGACY_STATIC_DIR, VITE_DIST_DIR

router = APIRouter(tags=["spa"])


@router.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(404, "API endpoint not found")

    vite_index = VITE_DIST_DIR / "index.html"
    if vite_index.exists():
        return FileResponse(vite_index)

    index_path = LEGACY_STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    return {"message": "API Running (Frontend not built)"}
