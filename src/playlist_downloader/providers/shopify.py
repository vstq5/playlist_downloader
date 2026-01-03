from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from ..config import Settings, get_settings
from ..models import Playlist, Track

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2023-10"


class ShopifyPlaylistError(RuntimeError):
    pass


@dataclass
class ShopifyPlaylistClient:
    store_domain: Optional[str] = None
    access_token: Optional[str] = None
    metaobject_type: Optional[str] = None
    _settings: Settings = field(default_factory=get_settings)

    def __post_init__(self) -> None:
        self.store_domain = self.store_domain or self._settings.shopify.store_domain
        self.access_token = self.access_token or self._settings.shopify.admin_access_token
        self.metaobject_type = self.metaobject_type or self._settings.shopify.metaobject_type
        if not (self.store_domain and self.access_token):
            raise ShopifyPlaylistError(
                "Shopify store_domain and admin access token must be configured via CLI flags or PLAYLIST_SHOPIFY__* env vars."
            )

    def fetch_playlist(self, playlist_url: str) -> Playlist:
        handle = self._extract_handle(playlist_url)
        payload = {
            "query": """
                query Playlist($handle: MetaobjectHandleInput!) {
                  metaobjectByHandle(handle: $handle) {
                    id
                    handle
                    type
                    fields {
                      key
                      value
                    }
                  }
                }
            """,
            "variables": {
                "handle": {"type": self.metaobject_type, "handle": handle},
            },
        }
        endpoint = f"https://{self.store_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
        logger.debug("Requesting playlist %s from %s", handle, endpoint)

        with httpx.Client(timeout=self._settings.downloader.timeout_seconds) as client:
            response = client.post(
                endpoint,
                json=payload,
                headers={
                    "X-Shopify-Access-Token": self.access_token,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        metaobject = data.get("data", {}).get("metaobjectByHandle")
        if not metaobject:
            raise ShopifyPlaylistError("Playlist metaobject not found; verify handle and access scopes.")

        field_map = {field["key"]: field.get("value") for field in metaobject.get("fields", [])}
        playlist_title = field_map.get("title") or metaobject.get("handle", "Untitled Playlist")
        playlist_description = field_map.get("description")
        cover_url = field_map.get("cover")

        raw_tracks = field_map.get("tracks")
        if not raw_tracks:
            raise ShopifyPlaylistError("Playlist metaobject missing 'tracks' field")

        try:
            track_entries = json.loads(raw_tracks)
        except json.JSONDecodeError as exc:  # noqa: PERF203
            raise ShopifyPlaylistError("Tracks field is not valid JSON") from exc

        tracks = [self._to_track(entry) for entry in track_entries]

        return Playlist(
            id=metaobject.get("id", handle),
            title=playlist_title,
            description=playlist_description,
            cover_url=cover_url,
            tracks=tracks,
            provider="shopify",
            raw=metaobject,
        )

    def _extract_handle(self, playlist_url: str) -> str:
        parsed = urlparse(playlist_url)
        if parsed.netloc and not self.store_domain:
            self.store_domain = parsed.netloc
        if parsed.query:
            query = parse_qs(parsed.query)
            if "handle" in query:
                return query["handle"][0]
            if "playlist" in query:
                return query["playlist"][0]
        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return path_parts[-1]
        raise ShopifyPlaylistError("Unable to determine playlist handle from URL")

    def _to_track(self, entry: Dict[str, Any]) -> Track:
        stream_url = entry.get("stream_url") or entry.get("download_url")
        if not stream_url:
            raise ShopifyPlaylistError("Each track must include a stream_url or download_url")
        return Track(
            id=str(entry.get("id") or entry.get("title")),
            title=entry.get("title", "Untitled"),
            artist=entry.get("artist"),
            stream_url=stream_url,
            source_url=entry.get("source_url") or entry.get("stream_url"),
            duration_ms=entry.get("duration"),
            cover_url=entry.get("cover"),
        )
