"""Tests for media skip-on-resume logic in MediaDownloader._attempt.

Offline: a mocked HttpClient returns a 10-byte body; we pre-create the target
file and assert it is skipped (not re-downloaded) when already present and
non-empty, and re-fetched when empty/partial.
"""
from __future__ import annotations

from pathlib import Path

from src.config import FailReason, SkipReason, TaskResult
from src.downloaders.media_downloader import MediaDownloader
from src.http_client import HttpClient
from src.resolvers import ResolvedMedia


class _FakeLive:
    def add_task(self, *a, **k): return 0
    def update_task(self, *a, **k): pass
    def update_log(self, *a, **k): pass


class _FakeResp:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    @property
    def status_code(self): return 200
    def raise_for_status(self): pass
    @property
    def headers(self):
        class H:
            def get(self, k, d=None):
                return {"Content-Type": "audio/mpeg", "Content-Length": "10"}.get(k, d)
        return H()
    def iter_content(self, chunk_size=1):
        yield b"0123456789"


def _make_downloader():
    client = HttpClient()
    client.session.get = lambda *a, **k: _FakeResp()
    return MediaDownloader(client, live_manager=_FakeLive())


def test_existing_nonempty_is_skipped(tmp_path: Path):
    dl = _make_downloader()
    d = tmp_path
    target = d / "song.mp3"
    # partial (not full) existing file must still be skipped on resume
    target.write_bytes(b"0123")
    out = dl._attempt(ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"), d, {}, 0)
    assert out.result is TaskResult.SKIPPED, out
    assert out.reason is SkipReason.ALREADY_DOWNLOADED, out
    target.unlink()


def test_existing_empty_is_redownloaded(tmp_path: Path):
    dl = _make_downloader()
    d = tmp_path
    target = d / "song.mp3"
    target.write_bytes(b"")  # 0-byte stub from a killed run -> must re-fetch
    out = dl._attempt(ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"), d, {}, 0)
    assert out.result is TaskResult.COMPLETED, out
    assert target.read_bytes() == b"0123456789"
    target.unlink()


def test_resume_appends_to_partial_part(tmp_path: Path):
    """A .part left by a killed run should be resumed, not restarted."""
    d = tmp_path
    target = d / "song.mp3"
    part = target.with_suffix(target.suffix + ".part")
    part.write_bytes(b"0123")  # 4 of 10 bytes already downloaded

    class _FakeRespResume:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        @property
        def status_code(self): return 206
        def raise_for_status(self): pass
        @property
        def headers(self):
            class H:
                def get(self, k, d=None):
                    # 206: remaining 6 bytes
                    return {"Content-Type": "audio/mpeg", "Content-Length": "6"}.get(k, d)
            return H()
        def iter_content(self, chunk_size=1):
            yield b"456789"  # the remaining bytes

    class _FakeLiveResume:
        def add_task(self, *a, **k): return 0
        def update_task(self, *a, **k): pass
        def update_log(self, *a, **k): pass

    client = HttpClient()
    client.session.get = lambda *a, **k: _FakeRespResume()
    dl2 = MediaDownloader(client, live_manager=_FakeLiveResume())
    out = dl2._attempt(ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"), d, {}, 0)
    assert out.result is TaskResult.COMPLETED, out
    assert target.read_bytes() == b"0123456789", target.read_bytes()
    assert not part.exists(), "stale .part should be gone"


def test_resume_restarts_when_server_ignores_range(tmp_path: Path):
    """A 200 response to Range contains the whole file and must replace .part."""
    target = tmp_path / "song.mp3"
    part = target.with_suffix(target.suffix + ".part")
    part.write_bytes(b"0123")

    dl = _make_downloader()
    out = dl._attempt(
        ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"),
        tmp_path,
        {},
        0,
    )

    assert out.result is TaskResult.COMPLETED
    assert target.read_bytes() == b"0123456789"


def test_same_filename_from_different_urls_gets_unique_paths(tmp_path: Path):
    dl = _make_downloader()
    first = dl._claim_target("http://a/song.mp3", tmp_path / "song.mp3")
    second = dl._claim_target("http://b/song.mp3", tmp_path / "song.mp3")

    assert first.name == "song.mp3"
    assert second.name == "song (1).mp3"


def test_incomplete_response_is_retried_and_not_promoted(tmp_path: Path):
    class _ShortResponse(_FakeResp):
        def iter_content(self, chunk_size=1):
            yield b"0123"

    client = HttpClient()
    calls = 0

    def get(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _ShortResponse()

    client.session.get = get
    downloader = MediaDownloader(client, live_manager=_FakeLive(), max_retries=1)
    outcome = downloader.download(
        ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"),
        tmp_path,
    )

    assert outcome.result is TaskResult.FAILED
    assert outcome.reason is FailReason.NETWORK_ERROR
    assert calls > 1
    assert not (tmp_path / "Audio" / "song.mp3").exists()
