from playlist_downloader.models import Playlist, Track, _sanitize_filename, collect_track_stats


def test_sanitize_filename_removes_forbidden_chars():
    assert _sanitize_filename("Artist:/\\*") == "Artist-"


def test_collect_track_stats_counts_tracks():
    tracks = [Track(id="1", title="One", stream_url="https://example.com/1"), Track(id="2", title="Two", stream_url="https://example.com/2")]
    stats = collect_track_stats(tracks)
    assert stats["track_count"] == 2


def test_track_target_filename_builds_nested_path():
    track = Track(id="1", title="My Song", artist="Artist", stream_url="https://example.com/song.mp3")
    filename = track.target_filename("Playlist")
    assert "Playlist" in str(filename)
    assert filename.suffix == ".mp3"
