from __future__ import annotations

import base64
import time
from typing import Any, Dict, Optional, cast

import requests


class SpotifyClient:
    def __init__(self, *, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: Optional[str] = None
        self.token_expiry: float = 0

    def _extract_id(self, url: str, kind: str) -> str:
        # Supports both open.spotify.com URLs and spotify: URIs.
        if f"{kind}/" in url:
            return url.split(f"{kind}/", 1)[1].split("?", 1)[0].split("/", 1)[0]
        if url.startswith(f"spotify:{kind}:"):
            return url.split(f"spotify:{kind}:", 1)[1].split("?", 1)[0]
        raise ValueError(f"Unsupported Spotify {kind} URL")

    def _get_token(self) -> str:
        if self.token and time.time() < self.token_expiry:
            return self.token

        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()

        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {b64_auth}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        self.token_expiry = time.time() + float(data["expires_in"]) - 60
        return cast(str, self.token)

    def _request_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
        max_retries: int = 6,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                token = self._get_token()
                headers = {"Authorization": f"Bearer {token}"}
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)

                if resp.status_code == 401:
                    self.token = None
                    self.token_expiry = 0
                    if attempt < max_retries - 1:
                        continue

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_s = float(int(retry_after))
                    else:
                        wait_s = float(min(2**attempt, 30))
                    time.sleep(wait_s)
                    continue

                if 500 <= resp.status_code < 600:
                    time.sleep(float(min(2**attempt, 10)))
                    continue

                resp.raise_for_status()

                data = resp.json()
                if isinstance(data, dict) and data.get("error"):
                    err = data.get("error")
                    if isinstance(err, dict):
                        msg = err.get("message") or "Spotify API error"
                        status = err.get("status")
                        raise RuntimeError(f"Spotify API error ({status}): {msg}")
                    raise RuntimeError(f"Spotify API error: {err}")

                return cast(Dict[str, Any], data)

            except Exception as e:  # noqa: BLE001
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(float(min(2**attempt, 5)))
                    continue
                break

        if last_error:
            raise last_error
        raise RuntimeError("Spotify request failed")

    def get_metadata(self, url: str):
        if "playlist" in url:
            pid = self._extract_id(url, "playlist")
            return self._request_json(f"https://api.spotify.com/v1/playlists/{pid}"), "playlist"
        if "album" in url:
            aid = self._extract_id(url, "album")
            return self._request_json(f"https://api.spotify.com/v1/albums/{aid}"), "album"
        if "track" in url:
            tid = self._extract_id(url, "track")
            return self._request_json(f"https://api.spotify.com/v1/tracks/{tid}"), "track"
        raise ValueError("Unsupported Spotify URL")

    def get_playlist_tracks(self, playlist_id: str):
        tracks = []
        url: Optional[str] = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        params: Optional[Dict[str, Any]] = {"limit": 100}

        while url:
            data = self._request_json(url, params=params)
            items = data.get("items") or []
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    t = item.get("track")
                    if t:
                        tracks.append(t)
            url = cast(Optional[str], data.get("next"))
            params = None

        return tracks
