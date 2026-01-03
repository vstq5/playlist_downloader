from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from .config import Settings, settings
from .downloader import download_playlist
from .providers import ShopifyPlaylistClient, SoundCloudPlaylistClient

app = typer.Typer(help="Download full playlists from Shopify metaobjects or SoundCloud public links.")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class Provider(str):
    SHOPIFY = "shopify"
    SOUNDCLOUD = "soundcloud"
    AUTO = "auto"


@app.command()
def download(
    playlist_url: str = typer.Argument(..., help="Share URL for the playlist"),
    provider: Provider = typer.Option(Provider.AUTO, case_sensitive=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Destination directory"),
    shopify_store: Optional[str] = typer.Option(None, help="Override Shopify store domain"),
    shopify_token: Optional[str] = typer.Option(None, help="Override Shopify private app access token"),
    soundcloud_client_id: Optional[str] = typer.Option(None, help="Override SoundCloud client id"),
    soundcloud_client_secret: Optional[str] = typer.Option(None, help="Override SoundCloud client secret"),
) -> None:
    """Download every track from a playlist URL."""

    resolved_provider = _detect_provider(provider, playlist_url)
    logger.info("Using provider %s", resolved_provider)
    playlist = _fetch_playlist(
        resolved_provider,
        playlist_url,
        settings,
        shopify_store,
        shopify_token,
        soundcloud_client_id,
        soundcloud_client_secret,
    )
    destination = output or settings.ensure_download_dir()
    target_dir = download_playlist(playlist, destination)
    typer.echo(f"Downloaded {playlist.track_count} tracks to {target_dir}")


def _detect_provider(provider: Provider, playlist_url: str) -> Provider:
    if provider != Provider.AUTO:
        return provider
    lowered = playlist_url.lower()
    if "soundcloud.com" in lowered:
        return Provider.SOUNDCLOUD
    if "shopify" in lowered or settings.shopify.store_domain:
        return Provider.SHOPIFY
    raise typer.BadParameter("Unable to determine provider from URL. Pass --provider explicitly.")


def _fetch_playlist(
    provider: Provider,
    playlist_url: str,
    cfg: Settings,
    shopify_store: Optional[str],
    shopify_token: Optional[str],
    sc_client_id: Optional[str],
    sc_client_secret: Optional[str],
):
    if provider == Provider.SHOPIFY:
        client = ShopifyPlaylistClient(store_domain=shopify_store, access_token=shopify_token)
        return client.fetch_playlist(playlist_url)
    if provider == Provider.SOUNDCLOUD:
        client = SoundCloudPlaylistClient(client_id=sc_client_id, client_secret=sc_client_secret)
        return client.fetch_playlist(playlist_url)
    raise typer.BadParameter(f"Unsupported provider {provider}")


if __name__ == "__main__":
    app()
