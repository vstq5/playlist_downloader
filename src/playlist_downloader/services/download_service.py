from __future__ import annotations

import base64
import asyncio
from contextlib import contextmanager
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
import random
import yt_dlp

from ..core.paths import DOWNLOADS_DIR, PROJECT_ROOT
from ..integrations.spotify_client import SpotifyClient
from ..utils.filenames import sanitize_filename


class DownloadService:
    def __init__(self, *, settings: Any, db: Any, spotify_client: SpotifyClient):
        self._settings = settings
        self._db = db
        self._spotify = spotify_client

        # Global concurrency limiter (shared across tasks)
        max_workers = int(getattr(settings, "YTDLP_MAX_WORKERS", 2))
        self._files_semaphore = asyncio.Semaphore(max_workers)
        # Per-owner task-level queue: prevents one user's stuck download from
        # blocking everyone else on a shared single-instance deployment.
        self._owner_download_locks: Dict[str, asyncio.Lock] = {}
        self._owner_download_locks_guard = asyncio.Lock()

    async def _get_owner_lock(self, owner_id: Optional[str]) -> asyncio.Lock:
        key = (owner_id or "__unknown__").strip() or "__unknown__"
        async with self._owner_download_locks_guard:
            lock = self._owner_download_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._owner_download_locks[key] = lock
            return lock

    @contextmanager
    def _yt_dlp_cookiefile(self):
        """Yield a cookies.txt path for yt-dlp, if configured.

        Supports:
        - YTDLP_COOKIES_PATH: path to a cookies.txt file inside the container
        - YTDLP_COOKIES_B64: base64-encoded contents of cookies.txt
        - YTDLP_COOKIES_URL: URL to a cookies.txt file (e.g., a private/presigned URL)
        """

        cookie_path = cast(str, getattr(self._settings, "YTDLP_COOKIES_PATH", "") or "")
        cookie_b64 = cast(str, getattr(self._settings, "YTDLP_COOKIES_B64", "") or "")
        cookie_url = cast(str, getattr(self._settings, "YTDLP_COOKIES_URL", "") or "")

        if cookie_path:
            yield cookie_path
            return

        if cookie_url:
            if not re.match(r"^https?://", cookie_url.strip(), flags=re.IGNORECASE):
                raise RuntimeError("YTDLP_COOKIES_URL must start with http:// or https://")

            try:
                import requests

                resp = requests.get(cookie_url, timeout=20)
                resp.raise_for_status()
                raw = resp.content
            except Exception as e:  # noqa: BLE001
                raise RuntimeError("Failed to fetch cookies from YTDLP_COOKIES_URL") from e

            if len(raw) > 5_000_000:
                raise RuntimeError("Cookies file too large")

            tmp = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt")
            try:
                tmp.write(raw)
                tmp.flush()
                tmp.close()
                yield tmp.name
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
            return

        if cookie_b64:
            try:
                raw = base64.b64decode(cookie_b64.encode("utf-8"), validate=True)
            except Exception as e:  # noqa: BLE001
                raise RuntimeError("Invalid YTDLP_COOKIES_B64 (must be base64)") from e

            tmp = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt")
            try:
                tmp.write(raw)
                tmp.flush()
                tmp.close()
                yield tmp.name
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
            return

        yield None

    def _prepare_cookie_file_for_task(self, base_dir: Path) -> Optional[str]:
        """Prepare a persistent cookies.txt file for the duration of a task.

        This is primarily used for subprocess-based downloads (spotdl) where we
        cannot safely rely on a short-lived temp file.

        Returns a filesystem path to cookies.txt, or None.
        """

        cookie_path = cast(str, getattr(self._settings, "YTDLP_COOKIES_PATH", "") or "").strip()
        cookie_b64 = cast(str, getattr(self._settings, "YTDLP_COOKIES_B64", "") or "").strip()
        cookie_url = cast(str, getattr(self._settings, "YTDLP_COOKIES_URL", "") or "").strip()

        if cookie_path:
            return cookie_path

        if cookie_url:
            if not re.match(r"^https?://", cookie_url, flags=re.IGNORECASE):
                raise RuntimeError("YTDLP_COOKIES_URL must start with http:// or https://")
            try:
                import requests

                resp = requests.get(cookie_url, timeout=20)
                resp.raise_for_status()
                raw = resp.content
            except Exception as e:  # noqa: BLE001
                raise RuntimeError("Failed to fetch cookies from YTDLP_COOKIES_URL") from e

            if len(raw) > 5_000_000:
                raise RuntimeError("Cookies file too large")

            target = base_dir / "cookies.txt"
            target.write_bytes(raw)
            return str(target)

        if cookie_b64:
            try:
                raw = base64.b64decode(cookie_b64.encode("utf-8"), validate=True)
            except Exception as e:  # noqa: BLE001
                raise RuntimeError("Invalid YTDLP_COOKIES_B64 (must be base64)") from e

            target = base_dir / "cookies.txt"
            target.write_bytes(raw)
            return str(target)

        return None

    def _resolve_browser_cookie_source(self) -> Optional[str]:
        """
        Smartly determine which browser to use for cookies.
        If config is 'auto', it tests common browsers.
        Returns the browser name (e.g. 'chrome') or None.
        """
        configured = cast(str, getattr(self._settings, "YTDLP_COOKIES_BROWSER", "") or "").strip()
        if not configured:
            return None
            
        if configured.lower() != "auto":
            return configured

        # Basic "auto" strategy: Check for common browser files or try to use them?
        # Since checking files is OS-specific and complex, we might define a priority list.
        # In a real scenario, we might try to infer installed browsers.
        # For now, we prefer Chrome > Edge > Firefox as they use similar Chromium encryption often easier for yt-dlp.
        # Use a cached result if possible? For now, we return a prioritized list prompt.
        # Actually, let's stick to 'chrome' as default fallback for 'auto' OR allow list expansion.
        # Better yet: Return 'default' which usually tells yt-dlp to try its best default? 
        # No, yt-dlp requires a browser name.
        
        # We will assume 'chrome' is the safest 'auto' bet on Windows/Mac, but let's try a heuristic if we can.
        # Simpler approach: Return 'chrome' as primary, let user override in env if needed.
        # But user asked for "different users" support.
        # Let's try to detect if Chrome/Edge are present?
        # That's overkill for this step.
        # Let's support a comma-separated list in config? e.g. "chrome,edge,firefox" and try them?
        # Too slow to try sequentially during download.
        
        # DECISION: 'auto' will map to 'chrome' for now, but we'll document that users can change it.
        # Wait, that defeats the point.
        # Let's actually TRY to see if we can detect.
        # Windows: Check %LOCALAPPDATA%/Google/Chrome
        
        candidates = ["chrome", "edge", "firefox"]
        if os.name == 'nt': # Windows
            local_app_data = os.environ.get('LOCALAPPDATA', '')
            if 'chrome' in candidates and os.path.exists(os.path.join(local_app_data, r'Google\Chrome\User Data')):
                return 'chrome'
            if 'edge' in candidates and os.path.exists(os.path.join(local_app_data, r'Microsoft\Edge\User Data')):
                return 'edge'
            # fallback
            return 'chrome' 
            
        # Linux/Mac/Docker checks
        # We must NOT return 'chrome' or 'firefox' if the directory doesn't exist, otherwise yt-dlp crashes.
        
        # Chrome
        chrome_paths = [
            Path.home() / ".config" / "google-chrome",
            Path.home() / ".config" / "chromium",
            Path.home() / "Library" / "Application Support" / "Google" / "Chrome" # Mac
        ]
        if 'chrome' in candidates:
            for p in chrome_paths:
                 if p.exists():
                     return 'chrome'

        # Firefox
        firefox_paths = [
            Path.home() / ".mozilla" / "firefox",
            Path.home() / "Library" / "Application Support" / "Firefox" # Mac
        ]
        if 'firefox' in candidates:
            for p in firefox_paths:
                 if p.exists():
                     return 'firefox'

        # If we are in a container (likely root with no browser), return None explicitly
        # This prevents the "could not find cookies database" error.
        return None

    
    def _get_proxy(self) -> Optional[str]:
        """Get a random proxy from the configuration pool."""
        raw_proxy = cast(str, getattr(self._settings, "YTDLP_PROXY", "") or "")
        if not raw_proxy:
            return None
        # Support comma-separated list for rotation
        proxies = [p.strip() for p in raw_proxy.split(",") if p.strip()]
        if not proxies:
            return None
        return random.choice(proxies)

    def _apply_yt_dlp_runtime_opts(self, ydl_opts: Dict[str, Any], cookiefile: Optional[str], override_client: Optional[str] = None):
        """Mutate yt-dlp options with runtime settings (cookies/headers/extractor tweaks)."""

        cookies_browser = self._resolve_browser_cookie_source()
        if cookies_browser:
            # Use real browser cookies (no file path needed)
            ydl_opts["cookiesfrombrowser"] = (cookies_browser, None, None, None)
        elif cookiefile:
            ydl_opts["cookiefile"] = cookiefile

        # Client Rotation Strategy
        # If override is provided (from retry loop), use it. Else use config default.
        player_client = override_client or cast(str, getattr(self._settings, "YTDLP_YOUTUBE_PLAYER_CLIENT", "") or "")
        
        if player_client:
            extractor_args = cast(Dict[str, Any], ydl_opts.setdefault("extractor_args", {}))
            youtube_args = cast(Dict[str, Any], extractor_args.setdefault("youtube", {}))
            youtube_args["player_client"] = [player_client]

        proxy = self._get_proxy()
        if proxy:
            ydl_opts["proxy"] = proxy

        po_token = cast(str, getattr(self._settings, "YTDLP_PO_TOKEN", "") or "")
        po_provider = cast(str, getattr(self._settings, "YTDLP_PO_PROVIDER", "web"))
        if po_token:
            extractor_args = cast(Dict[str, Any], ydl_opts.setdefault("extractor_args", {}))
            youtube_args = cast(Dict[str, Any], extractor_args.setdefault("youtube", {}))
            youtube_args["po_token"] = [f"{po_provider}+{po_token}"]

        if cast(bool, getattr(self._settings, "YTDLP_USE_OAUTH", False)):
            ydl_opts["username"] = "oauth2"
            ydl_opts["password"] = ""

        # User-Agent Rotation (Real Data simulation)
        headers = cast(Dict[str, Any], ydl_opts.setdefault("http_headers", {}))
        
        # Pick a random "Real" User-Agent if not explicitly set in headers
        if "User-Agent" not in headers:
            agents = getattr(self._settings, "REAL_USER_AGENTS", [])
            if agents:
                 headers["User-Agent"] = random.choice(agents)
            else:
                 # Fallback default
                 headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        headers.setdefault("Accept-Language", "en-US,en;q=0.9")

        # Gentle pacing to reduce cloud-IP throttling.
        # These options are supported by yt-dlp and help on hosts where YouTube is aggressive.
        sleep_interval = float(getattr(self._settings, "YTDLP_SLEEP_INTERVAL", 0) or 0)
        max_sleep_interval = float(getattr(self._settings, "YTDLP_MAX_SLEEP_INTERVAL", 0) or 0)
        sleep_interval_requests = int(getattr(self._settings, "YTDLP_SLEEP_INTERVAL_REQUESTS", 0) or 0)
        if sleep_interval > 0:
            ydl_opts["sleep_interval"] = sleep_interval
        if max_sleep_interval > 0:
            ydl_opts["max_sleep_interval"] = max_sleep_interval
        if sleep_interval_requests > 0:
            ydl_opts["sleep_interval_requests"] = sleep_interval_requests

        # Retries help on shared cloud IPs where YouTube rate-limits aggressively.
        retries = int(getattr(self._settings, "YTDLP_RETRIES", 0) or 0)
        fragment_retries = int(getattr(self._settings, "YTDLP_FRAGMENT_RETRIES", 0) or 0)
        extractor_retries = int(getattr(self._settings, "YTDLP_EXTRACTOR_RETRIES", 0) or 0)
        if retries > 0:
            ydl_opts["retries"] = retries
        if fragment_retries > 0:
            ydl_opts["fragment_retries"] = fragment_retries
        if extractor_retries > 0:
            ydl_opts["extractor_retries"] = extractor_retries

        return ydl_opts

    async def fetch_playlist_info(self, task_id: str, url: str):
        """Fetch metadata and write the 'ready' playlist structure to DB."""
        try:
            initial_state = {"id": task_id, "status": "preparing", "playlist": {"url": url}, "options": {}}
            await self._db.save_full_task_state(task_id, initial_state)

            loop = asyncio.get_running_loop()

            if "spotify.com" in url or url.startswith("spotify:"):
                data, type_ = await loop.run_in_executor(None, lambda: self._spotify.get_metadata(url))

                track_list: List[Dict[str, Any]] = []
                title = cast(str, data.get("name") or "Unknown")
                images = data.get("images") if isinstance(data, dict) else None
                cover_url = None
                if isinstance(images, list) and images:
                    first_img = images[0]
                    if isinstance(first_img, dict):
                        cover_url = first_img.get("url")

                skipped = 0

                def add_track(i: int, t: Dict[str, Any]):
                    nonlocal skipped
                    name = t.get("name")
                    if not name:
                        skipped += 1
                        return

                    if t.get("is_local") is True:
                        skipped += 1
                        return

                    artists = t.get("artists")
                    artist_name = None
                    if isinstance(artists, list) and artists:
                        a0 = artists[0]
                        if isinstance(a0, dict):
                            artist_name = a0.get("name")
                    if not artist_name:
                        skipped += 1
                        return

                    ext = t.get("external_urls")
                    track_url = None
                    if isinstance(ext, dict):
                        track_url = ext.get("spotify")
                    if not track_url:
                        skipped += 1
                        return

                    track_list.append(
                        {
                            "id": str(i),
                            "title": cast(str, name),
                            "artist": cast(str, artist_name),
                            "url": cast(str, track_url),
                            "status": "pending",
                        }
                    )

                if type_ == "playlist":
                    playlist_id = data.get("id")
                    if not playlist_id:
                        raise ValueError("Spotify playlist metadata missing 'id'")
                    tracks_data = await loop.run_in_executor(
                        None, lambda: self._spotify.get_playlist_tracks(cast(str, playlist_id))
                    )
                    for i, t in enumerate(tracks_data):
                        if isinstance(t, dict):
                            add_track(i, t)
                        else:
                            skipped += 1
                elif type_ == "album":
                    tracks_obj = data.get("tracks") if isinstance(data, dict) else None
                    tracks_items = tracks_obj.get("items") if isinstance(tracks_obj, dict) else None
                    if not isinstance(tracks_items, list):
                        raise ValueError("Spotify album metadata missing tracks")
                    for i, t in enumerate(tracks_items):
                        if isinstance(t, dict):
                            add_track(i, t)
                        else:
                            skipped += 1
                elif type_ == "track":
                    if not isinstance(data, dict):
                        raise ValueError("Spotify track metadata invalid")
                    title = cast(str, data.get("name") or title)
                    add_track(0, data)

                if len(track_list) == 0:
                    raise ValueError(
                        "No playable Spotify tracks found (playlist may contain only local/unavailable items)"
                    )

                ready_message = "Ready to download"
                if skipped > 0:
                    ready_message = f"Ready to download (skipped {skipped} unavailable/local tracks)"

                update = {
                    "playlist": {
                        "title": title,
                        "provider": "spotify",
                        "tracks": track_list,
                        "track_count": len(track_list),
                        "cover_url": cover_url,
                        "thumbnail": cover_url,
                    },
                    "status": "ready",
                    "message": ready_message,
                }
                current_task = await self._db.get_task(task_id)
                if current_task:
                    current_task.update(update)
                    await self._db.save_full_task_state(task_id, current_task)
                return

            # Non-Spotify: use yt-dlp metadata extraction
            def get_info():
                with self._yt_dlp_cookiefile() as cookiefile:
                    ydl_opts = cast(Any, {"extract_flat": "in_playlist", "dump_single_json": True, "quiet": True})
                    self._apply_yt_dlp_runtime_opts(cast(Dict[str, Any], ydl_opts), cookiefile)
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(url, download=False)

            info = await loop.run_in_executor(None, get_info)
            if not info:
                raise Exception("Could not fetch info")

            title = info.get("title", "Unknown Playlist")
            entries = info.get("entries", [info])
            entries = [e for e in entries if e]

            track_list = []
            for i, entry in enumerate(entries):
                t_url = entry.get("url") or entry.get("webpage_url")
                if not t_url and entry.get("id"):
                    t_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                track_list.append(
                    {
                        "id": str(i),
                        "title": entry.get("title", "Unknown"),
                        "artist": entry.get("uploader", "Unknown"),
                        "status": "pending",
                        "url": t_url,
                    }
                )

            update = {
                "playlist": {
                    "title": title,
                    "provider": "youtube",
                    "tracks": track_list,
                    "track_count": len(track_list),
                    "cover_url": info.get("thumbnail"),
                    "thumbnail": info.get("thumbnail"),
                },
                "status": "ready",
                "message": "Ready to download",
            }
            current_task = await self._db.get_task(task_id)
            if current_task:
                current_task.update(update)
                await self._db.save_full_task_state(task_id, current_task)

        except KeyError as e:
            missing_key = e.args[0] if e.args else "<unknown>"
            error_update = {
                "status": "error",
                "message": (
                    f"Metadata parse error: missing field '{missing_key}'. "
                    "This can happen with local/unavailable Spotify items."
                ),
            }
            current_task = await self._db.get_task(task_id)
            if current_task:
                current_task.update(error_update)
                await self._db.save_full_task_state(task_id, current_task)

        except Exception as e:  # noqa: BLE001
            error_update = {"status": "error", "message": str(e)}
            current_task = await self._db.get_task(task_id)
            if current_task:
                current_task.update(error_update)
                await self._db.save_full_task_state(task_id, current_task)

    async def process_download(self, task_id: str):
        try:
            task = await self._db.get_task(task_id)
            if not task:
                return

            task_state: Dict[str, Any] = cast(Dict[str, Any], task)

            owner_lock = await self._get_owner_lock(cast(Optional[str], task_state.get("owner_id")))

            options = task_state.get("options") or {}
            if options.get("cancel_requested") is True:
                task_state["status"] = "cancelled"
                task_state["message"] = "Cancelled"
                await self._db.save_full_task_state(task_id, task_state)
                return

            # Cache cancel checks to avoid DB hammering on large playlists.
            cancel_lock = asyncio.Lock()
            cancel_last_check = 0.0
            cancel_cached = False

            async def should_cancel() -> bool:
                nonlocal cancel_last_check, cancel_cached
                now = time.monotonic()
                if (now - cancel_last_check) < 1.0:
                    return cancel_cached

                async with cancel_lock:
                    now2 = time.monotonic()
                    if (now2 - cancel_last_check) < 1.0:
                        return cancel_cached

                    latest = await self._db.get_task(task_id)
                    latest_options = (latest or {}).get("options") or {}
                    cancel_cached = latest_options.get("cancel_requested") is True
                    cancel_last_check = now2
                    return cancel_cached

            acquired_immediately = False
            try:
                await asyncio.wait_for(owner_lock.acquire(), timeout=0.001)
                acquired_immediately = True
            except asyncio.TimeoutError:
                acquired_immediately = False

            if not acquired_immediately:
                task_state["status"] = "queued"
                task_state["message"] = "Queued for download..."
                task_state["progress"] = float(task_state.get("progress") or 0)
                await self._db.save_full_task_state(task_id, task_state)
                await owner_lock.acquire()

            try:
                task = await self._db.get_task(task_id)
                if not task:
                    logging.error(f"[DownloadService] Task {task_id} not found after acquiring lock")
                    return
                task_state = cast(Dict[str, Any], task)

                task_state["status"] = "downloading"
                task_state["message"] = "Starting download..."
                await self._db.save_full_task_state(task_id, task_state)

                loop = asyncio.get_running_loop()

                playlist = task_state["playlist"]
                all_tracks = playlist["tracks"]
                options = task_state.get("options") or {}

                selected = options.get("selected_indices")
                if selected is not None:
                    tracks = [t for i, t in enumerate(all_tracks) if i in selected or str(i) in map(str, selected)]
                    if not tracks:
                        tracks = all_tracks
                else:
                    tracks = all_tracks

                for i, t in enumerate(tracks, start=1):
                    if isinstance(t, dict):
                        t["_download_index"] = i

                for t in tracks:
                    if not isinstance(t, dict):
                        continue
                    if t.get("status") in (None, "pending", "ready"):
                        t["status"] = "queued"
                    if t.get("progress") is None:
                        t["progress"] = 0
                await self._db.save_full_task_state(task_id, task_state)

                total_tracks = len(tracks)

                progress_lock = asyncio.Lock()
                last_progress_save = 0.0
                SAVE_INTERVAL_SECONDS = 1.0

                async def update_overall_progress(force: bool = False):
                    nonlocal last_progress_save
                    if total_tracks <= 0:
                        return

                    async with progress_lock:
                        done = 0
                        failed = 0
                        for t in tracks:
                            s = t.get("status")
                            if s in ("completed", "error"):
                                done += 1
                            if s == "error":
                                failed += 1

                        task_state["progress"] = round((done / total_tracks) * 85.0, 2)
                        if failed > 0:
                            task_state["message"] = f"Downloading {done}/{total_tracks} (failed: {failed})"
                        else:
                            task_state["message"] = f"Downloading {done}/{total_tracks}"

                        now = time.monotonic()
                        if force or (now - last_progress_save) >= SAVE_INTERVAL_SECONDS or done == total_tracks:
                            last_progress_save = now
                            await self._db.save_full_task_state(task_id, task_state)

                target_format = options.get("format", "mp3")
                filename_template = options.get("filename_template", "{title}")

                if total_tracks > 1:
                    if "{track_number}" not in filename_template and "{track-number}" not in filename_template:
                        filename_template = f"{filename_template} - {{track_number}}"

                import tempfile

                audio_exts = {".mp3", ".m4a", ".flac", ".wav", ".opus", ".ogg"}

                with tempfile.TemporaryDirectory() as temp_dir_str:
                    base_dir = Path(temp_dir_str)
                    safe_title = sanitize_filename(playlist["title"]) or f"download_{task_id}"
                    download_dir = base_dir / f"{safe_title}_{task_id}"
                    download_dir.mkdir(parents=True, exist_ok=True)
                    safe_download_str = str(download_dir).replace("\\", "/")

                    # Pre-calculate the browser to use so we don't vary between spotdl/yt-dlp checks
                    active_browser_source = self._resolve_browser_cookie_source()

                    # Prepare a persistent cookie file for subprocess usage (spotdl)
                    cookie_file_for_task = self._prepare_cookie_file_for_task(base_dir)

                    has_cookie_config = bool(cookie_file_for_task or active_browser_source)

                    def download_spotify_subprocess(url: str, output_template: str, override_client: Optional[str] = None, user_agent: Optional[str] = None):
                        # Construct yt-dlp args for spotdl
                        # We need to pass proxy, cookies, and PO token
                        
                        yt_dlp_args = []
                        
                        # Proxy
                        # We resolve the proxy per-call to ensure rotation if a pool is provided
                        proxy = self._get_proxy()

                        # Cookies
                        cookie_file = cookie_file_for_task
                        cookies_browser = active_browser_source

                        # We might have created a temp cookie file in _yt_dlp_cookiefile but spotdl expects a persistent path.
                        # For simplicity, if we have YTDLP_COOKIES_B64, we rely on the user to have configured it correctly or we could try to pass it via args if spotdl supported it seamlessly.
                        # Actually spotdl supports --cookie-file.
                        
                        # PO Token
                        po_token = cast(str, getattr(self._settings, "YTDLP_PO_TOKEN", "") or "")
                        po_provider = cast(str, getattr(self._settings, "YTDLP_PO_PROVIDER", "web"))
                        
                        extractor_args_list = []
                        if po_token:
                            extractor_args_list.append(f"youtube:po_token={po_provider}+{po_token}")
                        
                        if extractor_args_list:
                            # IMPORTANT: We must escape quotes carefully for subprocess
                            # spotdl parses --yt-dlp-args using shlex.split usually.
                            # Format: --extractor-args "key:value"
                            for ea in extractor_args_list:
                                yt_dlp_args.extend(["--extractor-args", ea])

                        if proxy:
                            yt_dlp_args.extend(["--proxy", proxy])

                        # Gentle pacing + retries (no cookies required)
                        sleep_interval = float(getattr(self._settings, "YTDLP_SLEEP_INTERVAL", 0) or 0)
                        max_sleep_interval = float(getattr(self._settings, "YTDLP_MAX_SLEEP_INTERVAL", 0) or 0)
                        sleep_interval_requests = int(getattr(self._settings, "YTDLP_SLEEP_INTERVAL_REQUESTS", 0) or 0)
                        if sleep_interval > 0:
                            yt_dlp_args.extend(["--sleep-interval", str(sleep_interval)])
                        if max_sleep_interval > 0:
                            yt_dlp_args.extend(["--max-sleep-interval", str(max_sleep_interval)])
                        if sleep_interval_requests > 0:
                            yt_dlp_args.extend(["--sleep-interval-requests", str(sleep_interval_requests)])

                        retries = int(getattr(self._settings, "YTDLP_RETRIES", 0) or 0)
                        fragment_retries = int(getattr(self._settings, "YTDLP_FRAGMENT_RETRIES", 0) or 0)
                        extractor_retries = int(getattr(self._settings, "YTDLP_EXTRACTOR_RETRIES", 0) or 0)
                        if retries > 0:
                            yt_dlp_args.extend(["--retries", str(retries)])
                        if fragment_retries > 0:
                            yt_dlp_args.extend(["--fragment-retries", str(fragment_retries)])
                        if extractor_retries > 0:
                            yt_dlp_args.extend(["--extractor-retries", str(extractor_retries)])
                            
                        # If we have a cookie file path from env, pass it.
                        # If it's a temp file, it's tricky because this is a subprocess.
                        # Ideally user sets YTDLP_COOKIES_PATH. 
                        if cookie_file:
                             yt_dlp_args.extend(["--cookies", cookie_file])
                        
                        # Pass --cookies-from-browser if configured
                        if cookies_browser:
                             yt_dlp_args.extend(["--cookies-from-browser", cookies_browser])

                        # Client Rotation (passed via arg)
                        if override_client:
                            # We need to append to extractor-args.
                            # Existing extractor args might have been added above for PO Token.
                            # We can just add another --extractor-args flag? yt-dlp supports multiple?
                            # Usually yes, or we merge them.
                            # Safer to add a separate entry? spotdl passes them blindly.
                            # Usually yes, or we merge them.
                            # Safer to add a separate entry? spotdl passes them blindly.
                            yt_dlp_args.extend(["--extractor-args", f"youtube:player_client={override_client}"])

                        # User Agent Injection
                        if user_agent:
                            yt_dlp_args.extend(["--user-agent", user_agent])

                        cmd = [
                            "spotdl",
                            "download",
                            url,
                            "--output",
                            output_template,
                            "--overwrite",
                            "skip",
                            "--format",
                            target_format,
                            "--simple-tui",
                        ]
                        
                        if yt_dlp_args:
                            # Pass as a single string to --yt-dlp-args if needed, or see if spotdl accepts them directly?
                            # spotdl --yt-dlp-args "ARGS"
                            # We need to construct the string carefully.
                            # Example: --yt-dlp-args "--proxy http://... --extractor-args youtube:..."
                            
                            # Naive join might break if args have spaces, but ours (proxy/po token) typically don't.
                            flat_args = " ".join(yt_dlp_args)  
                            cmd.extend(["--yt-dlp-args", flat_args])

                        env = os.environ.copy()
                        env["SPOTIPY_CLIENT_ID"] = self._settings.SPOTIFY_CLIENT_ID
                        env["SPOTIPY_CLIENT_SECRET"] = self._settings.SPOTIFY_CLIENT_SECRET

                        if not env.get("SPOTIPY_CLIENT_ID") or not env.get("SPOTIPY_CLIENT_SECRET"):
                            raise RuntimeError(
                                "Spotify downloads require SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to be set"
                            )

                        try:
                            subprocess.run(
                                cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                env=env,
                                encoding="utf-8",
                                errors="replace",
                                check=True,
                                cwd=str(download_dir),
                                timeout=300,
                            )
                        except subprocess.TimeoutExpired as e:
                            raise RuntimeError("spotdl timed out (300s)") from e
                        except subprocess.CalledProcessError as e:
                            stderr = (getattr(e, "stderr", None) or "").strip()
                            stdout = (getattr(e, "stdout", None) or "").strip()
                            combined = "\n".join([s for s in [stderr, stdout] if s])
                            tail = combined[-800:] if combined else ""
                            msg = f"spotdl failed (exit {getattr(e, 'returncode', 'unknown')})"
                            if tail:
                                msg = f"{msg}: {tail}"
                            raise RuntimeError(msg) from e

                    async def download_worker(track: Dict[str, Any]):
                        async with self._files_semaphore:
                            try:
                                if await should_cancel():
                                    track["status"] = "cancelled"
                                    track["progress"] = 0
                                    await update_overall_progress()
                                    return

                                await asyncio.sleep(0.1)
                                track["status"] = "downloading"
                                track["progress"] = 0

                                # Snapshot existing audio files so we can confirm a new one was produced.
                                before_audio = {p.resolve() for p in download_dir.rglob("*") if p.is_file() and p.suffix.lower() in audio_exts}
                                start_ts = time.time()

                                if playlist["provider"] == "spotify":
                                    if not track.get("url"):
                                        raise Exception("Missing URL")
                                    idx = int(track.get("_download_index") or 1)
                                    raw_title = track.get("title") or track.get("name") or "track"
                                    safe_track_title = sanitize_filename(str(raw_title)) or "track"
                                    prefix = f"{idx:03d} - "
                                    use_spotdl = bool(getattr(self._settings, "SPOTIFY_USE_SPOTDL", False))

                                    # Default: avoid spotdl (more reliable on shared/cloud IPs)
                                    after_audio: list[Path] = []

                                    if use_spotdl:
                                        # spotdl expects --output to be a directory or a template.
                                        # Using a directory is the most reliable across versions.
                                        output_dir = safe_download_str

                                        # CLIENT ROTATION FOR SPOTDL
                                        clients_to_try_sp = [None, "ios", "android", "web", "tv"]
                                        success_sp = False
                                        last_error_sp = ""

                                        for attempt_client_sp in clients_to_try_sp:
                                            try:
                                                # Provide UI feedback
                                                if attempt_client_sp:
                                                    track["error"] = f"Bot check. Rotating client... (trying {attempt_client_sp})"
                                                    await update_overall_progress(force=True)

                                                # Pick a random User-Agent for this attempt
                                                current_ua = random.choice(getattr(self._settings, "REAL_USER_AGENTS", [])) if getattr(self._settings, "REAL_USER_AGENTS", []) else None

                                                await loop.run_in_executor(
                                                    None, lambda: download_spotify_subprocess(cast(str, track["url"]), output_dir, override_client=attempt_client_sp, user_agent=current_ua)
                                                )
                                                success_sp = True
                                                track["error"] = None  # Clear error on success
                                                break
                                            except Exception as e:
                                                msg = str(e)
                                                if "confirm you" in msg or "bot" in msg or "429" in msg or "Sign in" in msg or "spotdl failed" in msg:
                                                    logging.warning(f"SpotDL failed with client={attempt_client_sp}: {msg}")
                                                    last_error_sp = msg
                                                    attempt_idx = clients_to_try_sp.index(attempt_client_sp)
                                                    delay = 2.0 * (attempt_idx + 1)
                                                    await asyncio.sleep(delay)
                                                    continue
                                                raise

                                        if success_sp:
                                            after_audio = [
                                                p for p in download_dir.rglob("*")
                                                if p.is_file() and p.suffix.lower() in audio_exts and p.resolve() not in before_audio
                                            ]

                                    # If spotdl is disabled or produced no file, use yt-dlp search for the track.
                                    if not after_audio:
                                        query = f"{track.get('artist','')} - {track.get('title','')} audio".strip(" -")
                                        out_tmpl = f"{safe_download_str}/{prefix}{safe_track_title}.%(ext)s"
                                        
                                        # CLIENT ROTATION FOR FALLBACK SEARCH
                                        clients_to_try_fb = [None, "ios", "android", "web", "tv"]
                                        success_fb = False
                                        last_error_fb = ""

                                        for attempt_client_fb in clients_to_try_fb:
                                            try:
                                                if attempt_client_fb:
                                                    track["error"] = f"Fallback search... (trying {attempt_client_fb})"
                                                    await update_overall_progress(force=True)

                                                with self._yt_dlp_cookiefile() as cookiefile:
                                                    ydl_opts = cast(
                                                        Any,
                                                        {
                                                            "format": "bestaudio/best",
                                                            "outtmpl": out_tmpl,
                                                            "postprocessors": [
                                                                {"key": "FFmpegExtractAudio", "preferredcodec": target_format}
                                                            ],
                                                            "quiet": True,
                                                            "ignoreerrors": False,
                                                            "socket_timeout": 30,
                                                            "noplaylist": True,
                                                        },
                                                    )
                                                    self._apply_yt_dlp_runtime_opts(cast(Dict[str, Any], ydl_opts), cookiefile, override_client=attempt_client_fb)
                                                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                                        await loop.run_in_executor(
                                                            None, lambda: ydl.download([f"ytsearch1:{query}"])
                                                        )
                                                success_fb = True
                                                track["error"] = None
                                                break
                                            except Exception as e:
                                                msg = str(e)
                                                if "confirm you" in msg or "bot" in msg or "429" in msg or "Sign in" in msg:
                                                    logging.warning(f"Fallback Search bot check failed with client={attempt_client_fb}. Rotating...")
                                                    last_error_fb = msg
                                                    attempt_idx = clients_to_try_fb.index(attempt_client_fb)
                                                    delay = 2.0 * (attempt_idx + 1)
                                                    await asyncio.sleep(delay)
                                                    continue
                                                else:
                                                    raise e

                                        if not success_fb and last_error_fb:
                                            # If we failed all rotations, allow it to bubble up so the outer error handler catches it
                                             raise RuntimeError(f"Fallback Search failed (all clients). Last error: {last_error_fb}")
                                else:
                                    codec = target_format
                                    if target_format == "m4a":
                                        codec = "m4a"
                                    if target_format == "flac":
                                        codec = "flac"

                                    ydl_tmpl = (
                                        filename_template.replace("{artist}", "%(artist,uploader)s")
                                        .replace("{title}", "%(title)s")
                                        .replace("{album}", "%(album)s")
                                        .replace("{track_number}", "%(playlist_index)s")
                                        .replace("{year}", "%(release_year)s")
                                    )



                                    if total_tracks > 1 and "%(id)s" not in ydl_tmpl:
                                        ydl_tmpl = f"{ydl_tmpl}_%(id)s"

                                    out_tmpl = str(download_dir / f"{ydl_tmpl}.%(ext)s")
                                    
                                    # CLIENT ROTATION LOGIC
                                    # Try default -> ios -> android -> web -> tv
                                    clients_to_try = [None, "ios", "android", "web", "tv"]
                                    success = False
                                    last_error = ""

                                    for attempt_client in clients_to_try:
                                        try:
                                            if attempt_client:
                                                track["error"] = f"Bot check. Rotating client... (trying {attempt_client})"
                                                await update_overall_progress(force=True)

                                            with self._yt_dlp_cookiefile() as cookiefile:
                                                ydl_opts = cast(
                                                    Any,
                                                    {
                                                        "format": "bestaudio/best",
                                                        "outtmpl": out_tmpl,
                                                        "postprocessors": [
                                                            {"key": "FFmpegExtractAudio", "preferredcodec": codec}
                                                        ],
                                                        "writethumbnail": True,
                                                        "addmetadata": True,
                                                        "quiet": True,
                                                        "ignoreerrors": False,
                                                        "socket_timeout": 30,
                                                    },
                                                )
                                                # Pass rotation client
                                                self._apply_yt_dlp_runtime_opts(cast(Dict[str, Any], ydl_opts), cookiefile, override_client=attempt_client)
                                                
                                                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                                    await loop.run_in_executor(
                                                        None, lambda: ydl.download([cast(str, track["url"])])
                                                    )
                                            success = True
                                            track["error"] = None
                                            break # Success!
                                        except Exception as e:
                                            msg = str(e)
                                            if "confirm you" in msg or "bot" in msg or "429" in msg or "Sign in" in msg:
                                                logging.warning(f"Bot check failed with client={attempt_client or 'default'}. Rotating...")
                                                last_error = msg
                                                attempt_idx = clients_to_try.index(attempt_client)
                                                delay = 2.0 * (attempt_idx + 1)
                                                await asyncio.sleep(delay)
                                                continue # Try next client
                                            else:
                                                raise e # Real error, re-raise

                                    if not success:
                                         if last_error:
                                             raise RuntimeError(f"All clients failed. Last error: {last_error}")
                                         else:
                                             raise RuntimeError("Download failed (Rotated clients)")

                                # Validate that an audio file was actually created.
                                after_audio = [
                                    p for p in download_dir.rglob("*")
                                    if p.is_file() and p.suffix.lower() in audio_exts and p.resolve() not in before_audio
                                ]
                                # Some tools may overwrite an existing file; in that case, accept a recently modified file.
                                if not after_audio:
                                    recent = [
                                        p for p in download_dir.rglob("*")
                                        if p.is_file() and p.suffix.lower() in audio_exts and p.stat().st_mtime >= (start_ts - 1)
                                    ]
                                    after_audio = recent

                                if not after_audio:
                                    produced = [
                                        p.name for p in sorted(download_dir.rglob("*"))
                                        if p.is_file()
                                    ]
                                    preview = ", ".join(produced[:10])
                                    extra = f" Produced files: {preview}" if preview else ""
                                    raise RuntimeError(f"Download step completed but no audio file was produced.{extra}")

                                # For Spotify/spotdl, normalize the produced filename to our expected prefix/title.
                                # (yt-dlp branch already controls the output name).
                                if playlist["provider"] == "spotify" and after_audio:
                                    try:
                                        newest = max(after_audio, key=lambda p: p.stat().st_mtime)
                                        desired = download_dir / f"{prefix}{safe_track_title}{newest.suffix}"
                                        if newest != desired and not desired.exists():
                                            newest.replace(desired)
                                    except Exception:
                                        pass

                                track["status"] = "completed"
                                track["progress"] = 100
                                await update_overall_progress()
                            except Exception as e:  # noqa: BLE001
                                track["status"] = "error"
                                track["progress"] = 0
                                msg = str(e) or e.__class__.__name__
                                if (
                                    "confirm you\u2019re not a bot" in msg
                                    or "confirm you're not a bot" in msg
                                    or "temporarily limiting requests" in msg
                                    or "HTTP Error 429" in msg
                                    or "429" in msg
                                ):
                                    # Privacy-friendly guidance (no cookies required).
                                    msg = (
                                        "Service busy: YouTube is limiting requests from this server IP. "
                                        "Please try again in 10-15 minutes."
                                    )

                                    # Add a small task-level backoff to avoid hammering the shared IP.
                                    try:
                                        backoff = float(getattr(self._settings, "YTDLP_THROTTLE_BACKOFF_SECONDS", 0) or 0)
                                        if backoff > 0:
                                            await asyncio.sleep(backoff)
                                    except Exception:
                                        pass
                                # Keep payloads small; UI just needs the gist.
                                track["error"] = msg[-500:]
                                await update_overall_progress()

                    await update_overall_progress(force=True)
                    await asyncio.gather(*[download_worker(cast(Dict[str, Any], t)) for t in tracks])

                    if await should_cancel():
                        task_state["status"] = "cancelled"
                        task_state["message"] = "Cancelled"
                        await self._db.save_full_task_state(task_id, task_state)
                        return

                    task_state["status"] = "zipping"
                    task_state["message"] = "Finalizing..."
                    task_state["progress"] = max(float(task_state.get("progress") or 0), 90.0)
                    await self._db.save_full_task_state(task_id, task_state)

                    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

                    audio_files = [f for f in download_dir.rglob("*") if f.is_file() and f.suffix.lower() in audio_exts]
                    if len(audio_files) == 0:
                        # Surface a helpful error message for debugging in production.
                        failures: list[str] = []
                        for t in tracks:
                            if not isinstance(t, dict):
                                continue
                            if t.get("status") != "error":
                                continue
                            title = str(t.get("title") or "track")
                            err = str(t.get("error") or "unknown error")
                            failures.append(f"{title}: {err}")

                        if failures:
                            preview = " | ".join(failures[:3])
                            raise Exception(f"No tracks were downloaded successfully. Examples: {preview}")
                        raise Exception("No tracks were downloaded successfully")

                    final_path: Optional[Path] = None
                    should_zip = total_tracks > 1 or len(audio_files) > 1

                    if not should_zip and len(audio_files) == 1:
                        single_file = audio_files[0]
                        final_name = f"{single_file.name}"
                        if (DOWNLOADS_DIR / final_name).exists():
                            final_name = f"{task_id}_{single_file.name}"
                        final_path = DOWNLOADS_DIR / final_name
                        shutil.move(str(single_file), str(final_path))
                        task_state["message"] = "Ready!"
                        task_state["progress"] = max(float(task_state.get("progress") or 0), 95.0)
                    else:
                        zip_name = f"{safe_title}_{task_id}"
                        task_state["message"] = "Zipping..."
                        task_state["progress"] = max(float(task_state.get("progress") or 0), 95.0)
                        await self._db.save_full_task_state(task_id, task_state)
                        zip_path = await loop.run_in_executor(
                            None, lambda: shutil.make_archive(str(base_dir / zip_name), "zip", download_dir)
                        )
                        final_path = DOWNLOADS_DIR / f"{zip_name}.zip"
                        shutil.move(zip_path, final_path)
                        task_state["message"] = "Download Ready!"

                    task_state["status"] = "completed"
                    task_state["zip_path"] = str(final_path)
                    task_state["progress"] = 100
                    await self._db.save_full_task_state(task_id, task_state)

            finally:
                try:
                    owner_lock.release()
                except RuntimeError:
                    pass

        except Exception as e:  # noqa: BLE001
            task = await self._db.get_task(task_id)
            if task:
                task.update({"status": "error", "message": str(e)})
                await self._db.save_full_task_state(task_id, task)
