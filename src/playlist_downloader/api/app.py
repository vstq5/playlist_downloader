from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from .rate_limit import init_rate_limiter

from ..config import get_settings
from ..core.paths import DOWNLOADS_DIR, LEGACY_STATIC_DIR, VITE_DIST_DIR
from ..database import db
from ..integrations.spotify_client import SpotifyClient
from ..services.download_service import DownloadService
from ..services.search_service import SearchManager

def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log", encoding="utf-8")
        ],
    )
    logger = logging.getLogger(__name__)

    # Ensure ffmpeg from spotdl is in PATH
    spotdl_bin = Path.home() / ".spotdl"
    if spotdl_bin.exists():
        os.environ["PATH"] += os.pathsep + str(spotdl_bin)

    app = FastAPI(title="Playlist Downloader API - Container")
    init_rate_limiter(app)

    # Security middleware
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Assets mount (SPA serving)
    assets_dir: Optional[Path] = None
    if (VITE_DIST_DIR / "assets").exists():
        assets_dir = VITE_DIST_DIR / "assets"
    elif (LEGACY_STATIC_DIR / "assets").exists():
        assets_dir = LEGACY_STATIC_DIR / "assets"

    if assets_dir and assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # State/services
    spotify_client = SpotifyClient(client_id=settings.SPOTIFY_CLIENT_ID, client_secret=settings.SPOTIFY_CLIENT_SECRET)
    app.state.settings = settings
    app.state.db = db
    app.state.spotify_client = spotify_client
    app.state.download_service = DownloadService(settings=settings, db=db, spotify_client=spotify_client)
    app.state.search_manager = SearchManager(spotify_client=spotify_client)

    # Routers (import here to avoid circular imports)
    from .routes.search import router as search_router
    from .routes.spa import router as spa_router
    from .routes.tasks import router as tasks_router

    app.include_router(tasks_router)
    app.include_router(search_router)
    app.include_router(spa_router)

    @app.on_event("startup")
    async def startup_event():
        await db.init_db()

        # Option A (Render free): downloads run in-process.
        # Keep the API stable by using strict capacity controls and low concurrency.
        app.state.redis = None

        try:
            await db.cleanup_interrupted_tasks()
            logger.info("Startup sequence complete. Zombie tasks cleaned.")
        except Exception as e:  # noqa: BLE001
            logger.error("Startup cleanup failed: %s", e)

        # Cleanup old downloads (24h)
        try:
            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
            now = datetime.now().timestamp()
            removed_count = 0
            for f in DOWNLOADS_DIR.iterdir():
                if f.is_file() and (now - f.stat().st_mtime > 86400):
                    f.unlink()
                    removed_count += 1
            if removed_count > 0:
                logger.info("Cleaned up %s old download files.", removed_count)
        except Exception as e:  # noqa: BLE001
            logger.error("File cleanup failed: %s", e)

    return app
