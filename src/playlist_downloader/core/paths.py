from __future__ import annotations

from pathlib import Path

# NOTE: This file lives at: src/playlist_downloader/core/paths.py
# parents[0]=core, [1]=playlist_downloader, [2]=src, [3]=project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

VITE_DIST_DIR = PROJECT_ROOT / "web" / "dist"
LEGACY_STATIC_DIR = PROJECT_ROOT / "static"
DOWNLOADS_DIR = LEGACY_STATIC_DIR / "downloads"
