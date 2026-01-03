from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import httpx
from tqdm import tqdm

from .config import settings
from .models import Playlist, Track

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Raised when a track fails to download after retries."""


def download_playlist(playlist: Playlist, destination: Path | None = None) -> Path:
    destination = destination or settings.ensure_download_dir()
    playlist_dir = destination / playlist.tracks[0].target_filename(playlist.title).parent
    playlist_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s tracks from %s", playlist.track_count, playlist.title)

    with httpx.Client(timeout=settings.downloader.timeout_seconds) as client:
        for track in tqdm(playlist.tracks, desc=f"{playlist.title}"):
            _download_track(client, track, playlist, playlist_dir)

    return playlist_dir


def _download_track(client: httpx.Client, track: Track, playlist: Playlist, playlist_dir: Path) -> None:
    retries = settings.downloader.max_retries
    target_file = playlist_dir / track.target_filename(playlist.title)
    target_file.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 2):
        try:
            with client.stream("GET", track.stream_url, follow_redirects=True) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                with open(target_file, "wb") as file, tqdm(
                    total=total,
                    unit="B",
                    unit_scale=True,
                    desc=track.title,
                    leave=False,
                ) as progress:
                    for chunk in response.iter_bytes(settings.downloader.chunk_size):
                        file.write(chunk)
                        progress.update(len(chunk))
            logger.info("Saved %s", target_file)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Attempt %s failed for %s: %s", attempt, track.title, exc)
            if attempt > retries:
                raise DownloadError(f"Failed to download {track.title}") from exc


def summarize(playlist: Playlist) -> dict[str, str | int | None]:
    return {
        "provider": playlist.provider,
        "tracks": playlist.track_count,
        "title": playlist.title,
    }
