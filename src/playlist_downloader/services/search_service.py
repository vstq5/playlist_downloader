from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, cast

import requests
import yt_dlp
from pydantic import BaseModel
from ytmusicapi import YTMusic

from ..integrations.spotify_client import SpotifyClient


class SearchRequest(BaseModel):
    query: str
    providers: List[str] = ["spotify", "youtube", "soundcloud"]


class SearchManager:
    def __init__(self, *, spotify_client: SpotifyClient):
        self._spotify_client = spotify_client
        self._yt = YTMusic()

    async def search_spotify(self, query: str) -> List[Dict[str, Any]]:
        try:
            results: List[Dict[str, Any]] = []
            loop = asyncio.get_running_loop()

            token = self._spotify_client._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            resp = await loop.run_in_executor(
                None,
                lambda: requests.get(
                    "https://api.spotify.com/v1/search",
                    headers=headers,
                    params={"q": query, "type": "track,album,playlist", "limit": 4},
                    timeout=5,
                ),
            )
            if resp.status_code != 200:
                return []
            data = resp.json()

            for t in data.get("tracks", {}).get("items", []):
                results.append(
                    {
                        "title": t["name"],
                        "uploader": t["artists"][0]["name"],
                        "duration": t["duration_ms"] / 1000,
                        "url": t["external_urls"]["spotify"],
                        "thumbnail": t["album"]["images"][0]["url"] if t["album"]["images"] else None,
                        "type": "track",
                        "source": "spotify",
                    }
                )

            for a in data.get("albums", {}).get("items", []):
                results.append(
                    {
                        "title": a["name"],
                        "uploader": a["artists"][0]["name"],
                        "duration": 0,
                        "url": a["external_urls"]["spotify"],
                        "thumbnail": a["images"][0]["url"] if a["images"] else None,
                        "type": "album",
                        "source": "spotify",
                    }
                )

            for p in data.get("playlists", {}).get("items", []):
                if not p:
                    continue
                results.append(
                    {
                        "title": p.get("name") or "Playlist",
                        "uploader": (p.get("owner") or {}).get("display_name") or "Spotify",
                        "duration": 0,
                        "url": (p.get("external_urls") or {}).get("spotify"),
                        "thumbnail": (p.get("images") or [{}])[0].get("url") if p.get("images") else None,
                        "type": "playlist",
                        "source": "spotify",
                    }
                )

            return results
        except Exception:
            return []

    async def search_youtube(self, query: str) -> List[Dict[str, Any]]:
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, lambda: self._yt.search(query, filter="songs", limit=4))

            normalized: List[Dict[str, Any]] = []
            for item in results:
                if item.get("resultType") not in ["song", "video"]:
                    continue

                duration = 0
                dur = item.get("duration")
                if dur:
                    parts = dur.split(":")
                    if len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                normalized.append(
                    {
                        "title": item.get("title"),
                        "uploader": item.get("artists", [{}])[0].get("name") if item.get("artists") else "Unknown",
                        "duration": duration,
                        "url": f"https://music.youtube.com/watch?v={item['videoId']}",
                        "thumbnail": item.get("thumbnails", [None])[-1]["url"] if item.get("thumbnails") else None,
                        "type": "track",
                        "source": "youtube",
                    }
                )
            return normalized
        except Exception:
            return []

    async def search_soundcloud(self, query: str) -> List[Dict[str, Any]]:
        try:
            loop = asyncio.get_running_loop()

            def sc_scrape():
                opts = cast(Any, {"quiet": True, "extract_flat": True, "dump_single_json": True})
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(f"scsearch5:{query}", download=False)

            info = await loop.run_in_executor(None, sc_scrape)
            entries = info.get("entries", []) if info else []

            normalized: List[Dict[str, Any]] = []
            for e in entries:
                normalized.append(
                    {
                        "title": e.get("title"),
                        "uploader": e.get("uploader"),
                        "duration": e.get("duration", 0),
                        "url": e.get("url"),
                        "thumbnail": None,
                        "type": "track",
                        "source": "soundcloud",
                    }
                )
            return normalized
        except Exception:
            return []


def build_suggestions(*, query: str, spotify_client: SpotifyClient, search_manager: SearchManager) -> List[Dict[str, str]]:
    query = (query or "").strip()
    if len(query) < 2:
        return []

    suggestions: List[Dict[str, str]] = []
    suggestions.append({"label": f'Search "{query}"', "value": query, "type": "text", "action": "search"})

    try:
        token = spotify_client._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params={"q": query, "type": "track,album,playlist", "limit": 5},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()

            for t in data.get("tracks", {}).get("items", [])[:2]:
                artist = (t.get("artists") or [{}])[0].get("name") or "Unknown"
                suggestions.append(
                    {
                        "label": f"{t.get('name', 'Track')} — {artist}",
                        "value": t.get("external_urls", {}).get("spotify", ""),
                        "type": "spotify",
                        "action": "download",
                        "kind": "track",
                    }
                )

            for p in data.get("playlists", {}).get("items", [])[:2]:
                if not p:
                    continue
                suggestions.append(
                    {
                        "label": f"{p.get('name', 'Playlist')} (Playlist)",
                        "value": p.get("external_urls", {}).get("spotify", ""),
                        "type": "spotify",
                        "action": "view",
                        "kind": "playlist",
                    }
                )

            for a in data.get("albums", {}).get("items", [])[:1]:
                if not a:
                    continue
                artist = (a.get("artists") or [{}])[0].get("name") or "Unknown"
                suggestions.append(
                    {
                        "label": f"{a.get('name', 'Album')} — {artist} (Album)",
                        "value": a.get("external_urls", {}).get("spotify", ""),
                        "type": "spotify",
                        "action": "view",
                        "kind": "album",
                    }
                )
    except Exception:
        pass

    return [s for s in suggestions if s.get("value")][:10]


def _normalize_text(s: str) -> str:
    return (s or "").strip().lower()


def relevance_score(item: Dict[str, Any], query: str) -> int:
    q = _normalize_text(query)
    if not q:
        return 0

    title = _normalize_text(cast(str, item.get("title", "")))
    uploader = _normalize_text(cast(str, item.get("uploader", "")))

    score = 0
    if title == q:
        score += 120
    if title.startswith(q):
        score += 80
    if q in title:
        score += 50
    if q in uploader:
        score += 10

    tokens = [t for t in q.split() if len(t) >= 2]
    if tokens:
        token_hits = sum(1 for t in tokens if t in title)
        score += token_hits * 12

    t = item.get("type")
    if t == "track":
        score += 8
    elif t in ("album", "playlist"):
        score += 5

    src = item.get("source")
    if src == "spotify":
        score += 4

    return score
