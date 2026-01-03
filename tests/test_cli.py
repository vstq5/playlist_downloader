from playlist_downloader.cli import Provider, _detect_provider


def test_detect_provider_soundcloud():
    result = _detect_provider(Provider.AUTO, "https://soundcloud.com/user/playlist")
    assert result == Provider.SOUNDCLOUD


def test_detect_provider_shopify_when_auto():
    result = _detect_provider(Provider.AUTO, "https://my-store.myshopify.com/apps/playlist/handle")
    assert result == Provider.SHOPIFY


def test_detect_provider_respects_override():
    result = _detect_provider(Provider.SOUNDCLOUD, "https://any")
    assert result == Provider.SOUNDCLOUD
