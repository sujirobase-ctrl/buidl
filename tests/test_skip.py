"""Tests for media skip-on-resume logic in MediaDownloader._attempt.

Offline: a mocked HttpClient returns a 10-byte body; we pre-create the target
file and assert it is skipped (not re-downloaded) when already present and
non-empty, and re-fetched when empty/partial.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import SkipReason, TaskResult
from src.downloaders.media_downloader import MediaDownloader
from src.http_client import HttpClient
from src.resolvers import ResolvedMedia, _resolve_direct


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


def test_existing_nonempty_is_skipped():
    dl = _make_downloader()
    d = Path(__file__).parent / "_tmp_skip"
    d.mkdir(exist_ok=True)
    target = d / "song.mp3"
    # partial (not full) existing file must still be skipped on resume
    target.write_bytes(b"0123")
    out = dl._attempt(ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"), d, {}, 0)
    assert out.result is TaskResult.SKIPPED, out
    assert out.reason is SkipReason.ALREADY_DOWNLOADED, out
    target.unlink()


def test_existing_empty_is_redownloaded():
    dl = _make_downloader()
    d = Path(__file__).parent / "_tmp_skip"
    d.mkdir(exist_ok=True)
    target = d / "song.mp3"
    target.write_bytes(b"")  # 0-byte stub from a killed run -> must re-fetch
    out = dl._attempt(ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"), d, {}, 0)
    assert out.result is TaskResult.COMPLETED, out
    assert target.read_bytes() == b"0123456789"
    target.unlink()


def test_resume_appends_to_partial_part():
    """A .part left by a killed run should be resumed, not restarted."""
    d = Path(__file__).parent / "_tmp_skip"
    d.mkdir(exist_ok=True)
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
    target.unlink()


def test_reddit_html_interstitial_is_retried(tmp_path, monkeypatch):
    class _Response:
        status_code = 200

        def __init__(self, content_type, body):
            self._content_type = content_type
            self._body = body

        def __enter__(self): return self
        def __exit__(self, *a): pass
        def raise_for_status(self): pass

        @property
        def headers(self):
            return {
                "Content-Type": self._content_type,
                "Content-Length": str(len(self._body)),
            }

        def iter_content(self, chunk_size=1):
            yield self._body

    responses = iter(
        [
            _Response("text/html; charset=utf-8", b"temporary block"),
            _Response("image/jpeg", b"jpeg bytes"),
        ]
    )
    client = HttpClient()
    client.session.get = lambda *a, **k: next(responses)
    downloader = MediaDownloader(client, live_manager=_FakeLive(), max_retries=1)
    media = _resolve_direct("https://i.redd.it/drfy08tqb89g1.jpeg", client)[0]
    monkeypatch.setattr("src.downloaders.media_downloader.time.sleep", lambda _seconds: None)

    outcome = downloader.download(media, tmp_path)

    assert outcome.result is TaskResult.COMPLETED
    assert (tmp_path / "Photos" / "drfy08tqb89g1.jpeg").read_bytes() == b"jpeg bytes"


def test_resume_restarts_when_server_ignores_range():
    dl = _make_downloader()
    d = Path(__file__).parent / "_tmp_skip"
    d.mkdir(exist_ok=True)
    target = d / "song.mp3"
    part = target.with_suffix(target.suffix + ".part")
    part.write_bytes(b"0123")

    out = dl._attempt(
        ResolvedMedia(url="http://x/song.mp3", filename="song.mp3"),
        d,
        {},
        0,
    )

    assert out.result is TaskResult.COMPLETED
    assert target.read_bytes() == b"0123456789"
    target.unlink()


def test_same_filename_from_two_urls_gets_unique_targets():
    dl = _make_downloader()
    d = Path(__file__).parent / "_tmp_skip"
    d.mkdir(exist_ok=True)
    first = d / "song.mp3"
    second = d / "song (1).mp3"
    first.unlink(missing_ok=True)
    second.unlink(missing_ok=True)

    one = dl._attempt(
        ResolvedMedia(url="http://x/one", filename="song.mp3"), d, {}, 0,
    )
    two = dl._attempt(
        ResolvedMedia(url="http://x/two", filename="song.mp3"), d, {}, 1,
    )

    assert one.result is TaskResult.COMPLETED
    assert two.result is TaskResult.COMPLETED
    assert first.read_bytes() == b"0123456789"
    assert second.read_bytes() == b"0123456789"
    first.unlink()
    second.unlink()


if __name__ == "__main__":
    test_existing_nonempty_is_skipped()
    test_existing_empty_is_redownloaded()
    test_resume_appends_to_partial_part()
    print("skip tests — passed 3, failed 0")
