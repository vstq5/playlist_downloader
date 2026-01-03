from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from ..config import Settings, get_settings
from ..models import Playlist, Track

logger = logging.getLogger(__name__)


class SoundCloudError(RuntimeError):
    pass


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    token = f"{client_id}:{client_secret}".encode()
    return base64.b64encode(token).decode()


@dataclass
class SoundCloudPlaylistClient:
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    _settings: Settings = field(default_factory=get_settings)
    _token: Optional[str] = field(default=None, init=False)
    _token_expiry: float = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.client_id = self.client_id or self._settings.soundcloud.client_id
        self.client_secret = self.client_secret or self._settings.soundcloud.client_secret
        if not (self.client_id and self.client_secret):
            raise SoundCloudError("SoundCloud client_id and client_secret must be configured via env or CLI.")

    def fetch_playlist(self, playlist_url: str) -> Playlist:
        resolved = self._resolve_url(playlist_url)
        if resolved.get("kind") != "playlist":
            raise SoundCloudError("Provided URL does not resolve to a playlist")
        playlist_id = str(resolved.get("id"))
        tracks = [self._hydrate_track(track) for track in resolved.get("tracks", [])]
        return Playlist(
            id=playlist_id,
            title=resolved.get("title", "Untitled Playlist"),
            description=resolved.get("description"),
            cover_url=resolved.get("artwork_url"),
            tracks=tracks,
            provider="soundcloud",
            raw=resolved,
        )

    # --- internal helpers -------------------------------------------------
    def _resolve_url(self, playlist_url: str) -> Dict[str, Any]:
        token = self._ensure_token()
        endpoint = f"{self._settings.soundcloud.api_base}/resolve"
        headers = {"Authorization": f"OAuth {token}", "Accept": "application/json"}
        with httpx.Client(timeout=self._settings.downloader.timeout_seconds) as client:
            response = client.get(endpoint, params={"url": playlist_url}, headers=headers)
            response.raise_for_status()
            return response.json()

    def _hydrate_track(self, track_data: Dict[str, Any]) -> Track:
        track_id = track_data.get("id")
        stream_url = self._resolve_stream_url(track_id)
        user = track_data.get("user", {})
        return Track(
            id=str(track_id),
            title=track_data.get("title", "Untitled"),
            artist=user.get("username"),
            stream_url=stream_url,
            source_url=track_data.get("permalink_url"),
            duration_ms=track_data.get("duration"),
            cover_url=track_data.get("artwork_url") or track_data.get("user", {}).get("avatar_url"),
            published_at=None,
        )

    def _resolve_stream_url(self, track_id: int) -> str:
        token = self._ensure_token()
        endpoint = f"{self._settings.soundcloud.api_base}/tracks/{track_id}/stream"
        headers = {"Authorization": f"OAuth {token}", "Accept": "application/json"}
        with httpx.Client(timeout=self._settings.downloader.timeout_seconds, follow_redirects=True) as client:
            response = client.get(endpoint, headers=headers)
            response.raise_for_status()
            data = response.json()
            url = data.get("url") or data.get("redirect_url") or data.get("redirectUri")
            if not url:
                raise SoundCloudError("Stream URL missing in response; track might be blocked for streaming.")
            return url

    def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token
        auth_endpoint = f"{self._settings.soundcloud.auth_base}/oauth/token"
        headers = {
            "Authorization": f"Basic {_basic_auth_header(self.client_id, self.client_secret)}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}
        with httpx.Client(timeout=self._settings.downloader.timeout_seconds) as client:
            response = client.post(auth_endpoint, data=data, headers=headers)
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._token_expiry = now + int(payload.get("expires_in", 3600))
            return self._token
