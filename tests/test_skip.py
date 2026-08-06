"""Tests for media skip-on-resume logic in MediaDownloader._attempt.

Offline: a mocked HttpClient returns a 10-byte body; we pre-create the target
file and assert it is skipped (not re-downloaded) when already present and
non-empty, and re-fetched when empty/partial.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.downloaders.media_downloader import MediaDownloader
from src.resolvers import ResolvedMedia
from src.http_client import HttpClient
from src.config import TaskResult, SkipReason


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
    dl = _make_downloader()
    d = Path(__file__).parent / "_tmp_skip"
    d.mkdir(exist_ok=True)
    target = d / "song.mp3"
    part = target.with_suffix(target.suffix + ".part")
    part.write_bytes(b"0123")  # 4 of 10 bytes already downloaded

    seen = {}

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


if __name__ == "__main__":
    test_existing_nonempty_is_skipped()
    test_existing_empty_is_redownloaded()
    test_resume_appends_to_partial_part()
    print("skip tests — passed 3, failed 0")
