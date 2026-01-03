from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Optional

from pydantic import BaseModel, HttpUrl


class Track(BaseModel):
    id: str
    title: str
    artist: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    stream_url: HttpUrl
    duration_ms: Optional[int] = None
    cover_url: Optional[HttpUrl] = None
    published_at: Optional[datetime] = None

    def target_filename(self, playlist_title: str, ext: str = "mp3") -> Path:
        safe_playlist = _sanitize_filename(playlist_title)
        safe_title = _sanitize_filename(self.title)
        safe_artist = _sanitize_filename(self.artist or "unknown")
        return Path(f"{safe_playlist}/{safe_artist} - {safe_title}.{ext}")


class Playlist(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    cover_url: Optional[HttpUrl] = None
    tracks: List[Track]
    provider: str
    raw: Optional[Any] = None

    @property
    def track_count(self) -> int:
        return len(self.tracks)


def _sanitize_filename(name: str) -> str:
    return "".join(c for c in name.replace("/", "-") if c not in "<>:\\|?*").strip() or "untitled"


def collect_track_stats(tracks: Iterable[Track]) -> dict[str, Any]:
    track_list = list(tracks)
    durations = [t.duration_ms for t in track_list if t.duration_ms]
    total_duration = sum(durations) if durations else None
    return {
        "track_count": len(track_list),
        "total_duration_ms": total_duration,
    }
