from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class DownloaderSettings(BaseModel):
    chunk_size: int = 1024 * 256
    timeout_seconds: float = 30.0
    max_retries: int = 2


class ShopifySettings(BaseModel):
    store_domain: Optional[str] = None
    admin_access_token: Optional[str] = None
    metaobject_type: str = "playlist"


class SoundCloudSettings(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    api_base: str = "https://api.soundcloud.com"
    auth_base: str = "https://secure.soundcloud.com"


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    API_PORT: int = 8000

    # Security: Parse JSON list
    CORS_ORIGINS: List[str] = ["*"]

    # Database
    # Default is local SQLite for dev/tests; override in Docker/Render.
    DATABASE_URL: str = "sqlite+aiosqlite:///./playlist_downloader.db"

    # In-process downloads
    # On Render free (zero-cost), downloads must run inside the web service.
    ALLOW_INPROCESS_DOWNLOADS: bool = True

    # Capacity controls (per owner/device)
    # Running: tasks actively downloading/zipping
    # Queued: tasks waiting to run (pending/preparing/queued/ready)
    MAX_RUNNING_TASKS_PER_OWNER: int = 1
    MAX_QUEUED_TASKS_PER_OWNER: int = 2

    # Download artifact storage
    # With Option A, completed downloads are stored on the web service filesystem.
    # NOTE: files may be lost on redeploy/restart on free tiers.
    STORAGE_BACKEND: str = "local"

    # Spotify (optional; required only for Spotify features)
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""

    # Spotify download strategy
    # On shared/free cloud IPs, spotdl can be unreliable because it ultimately depends
    # on YouTube fetches and can trigger throttling quickly.
    # Default to yt-dlp search per track for better robustness.
    SPOTIFY_USE_SPOTDL: bool = False

    # yt-dlp / YouTube (optional; helps on some cloud hosts where YouTube triggers bot checks)
    # Provide either a path inside the container, base64-encoded cookies.txt contents,
    # or a URL to fetch cookies.txt from at runtime.
    YTDLP_COOKIES_PATH: str = ""
    YTDLP_COOKIES_B64: str = ""
    YTDLP_COOKIES_URL: str = ""
    # Some environments work better with the Android client.
    # 'ios' is currently providing better playback reliability.
    YTDLP_YOUTUBE_PLAYER_CLIENT: str = "ios"
    
    # Bypass (PO Token)
    # See: https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
    YTDLP_PO_TOKEN: str = ""
    YTDLP_PO_PROVIDER: str = "web"  # "web" or "ios" etc.
    YTDLP_USE_OAUTH: bool = False
    YTDLP_PROXY: str = ""  # e.g. http://user:pass@host:port

    # Real-world User Agents to rotate through for better "Real User" simulation
    REAL_USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
    ]

    # Auto-extract cookies from a local browser profile (e.g. "chrome", "edge").
    # Disabled by default because container hosts (e.g. Render) typically do not have
    # browser profiles available.
    # Set to "auto" for local dev if you want yt-dlp to try a detected browser.
    YTDLP_COOKIES_BROWSER: str = ""

    # Gentle pacing to reduce cloud-IP throttling.
    # If set, yt-dlp will sleep between requests.
    YTDLP_SLEEP_INTERVAL: float = 1.0
    YTDLP_MAX_SLEEP_INTERVAL: float = 3.0
    YTDLP_SLEEP_INTERVAL_REQUESTS: int = 1

    # Retries (helps when YouTube rate-limits shared IPs)
    YTDLP_RETRIES: int = 5
    YTDLP_FRAGMENT_RETRIES: int = 5
    YTDLP_EXTRACTOR_RETRIES: int = 3

    # App-level backoff when we detect a bot-check / throttling response
    # (used in addition to yt-dlp's own retries)
    YTDLP_THROTTLE_BACKOFF_SECONDS: float = 30.0
    
    # Concurrency
    # Lower this if your server crashes/restarts (OOM kills).
    # Defaulting to 1 to be safer on free/shared cloud IPs.
    YTDLP_MAX_WORKERS: int = 1

    # Security (optional; required only if you add auth/session features)
    SECRET_KEY: str = "change_me_to_random_secret"

    # CLI/provider configuration
    DOWNLOAD_DIR: Path = Path("downloads")
    downloader: DownloaderSettings = DownloaderSettings()
    shopify: ShopifySettings = ShopifySettings()
    soundcloud: SoundCloudSettings = SoundCloudSettings()

    class Config:
        env_file = ".env"
        case_sensitive = True

    def ensure_download_dir(self) -> Path:
        self.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return self.DOWNLOAD_DIR


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Back-compat for CLI/providers and older imports
settings = get_settings()
