"""Offline tests for the ported chunked download + rate limiter.

No network: a fake HTTP range server is mocked so the byte-range partition,
per-chunk resume and merge logic are exercised deterministically.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.downloaders.chunked import (
    DownloadConfig,
    compute_unit_ranges,
    save_file_with_chunks,
    should_use_parallel_download,
)
from src.downloaders.rate_limiter import RateLimiter


def test_compute_unit_ranges_covers_whole_file():
    n = 20 * 1024 * 1024  # 20 MB
    ranges = compute_unit_ranges(n, num_connections=2)
    # last unit ends at the final byte
    assert ranges[-1][1] == n - 1
    # contiguous & monotonic
    prev = -1
    for s, e in ranges:
        assert s == prev + 1
        assert e >= s
        prev = e
    assert prev == n - 1


def test_should_use_parallel_download_rules():
    assert should_use_parallel_download(10 * 1024 * 1024, 4, supports_range=True)
    assert not should_use_parallel_download(10 * 1024 * 1024, 1, supports_range=True)
    assert not should_use_parallel_download(1024, 4, supports_range=True)  # too small
    assert not should_use_parallel_download(10 * 1024 * 1024, 4, supports_range=False)


class _FakeRangeServer:
    """Mimics a host that honours byte-range requests on a fixed blob."""

    def __init__(self, blob: bytes, *, good_ranges=True):
        self.blob = blob
        self.calls = 0
        self.good_ranges = good_ranges

    def head(self, url, headers=None, timeout=10):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            @property
            def headers(self):
                return {"Accept-Ranges": "bytes", "Content-Length": str(len(self.blob))}
        R._blob = self.blob
        return R()

    def get(self, url, headers=None, stream=True, timeout=30):
        self.calls += 1
        rng = headers.get("Range", "")
        start, end = 0, len(self.blob) - 1
        if rng.startswith("bytes=") and self.good_ranges:
            spec = rng[len("bytes="):].split("-")
            start = int(spec[0])
            end = int(spec[1]) if spec[1] else len(self.blob) - 1
        chunk = self.blob[start:end + 1]
        outer = self
        class R:
            status_code = 206 if outer.good_ranges and rng else 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def raise_for_status(self): pass
            @property
            def headers(self):
                return {"Content-Type": "application/octet-stream"}
            def iter_content(self, chunk_size=1):
                yield chunk
        return R()


def _patch(monkey):
    import src.downloaders.chunked as c
    c.requests.head = monkey.head
    c.requests.get = monkey.get


def test_chunked_download_reassembles(tmp_path, monkeypatch):
    blob = bytes((i % 256) for i in range(10 * 1024 * 1024))  # 10 MB
    server = _FakeRangeServer(blob)
    _patch(server)
    target = tmp_path / "out.bin"
    cfg = DownloadConfig(
        content_length=len(blob), num_connections=4, headers={}, rate_limiter=None,
    )
    failed = save_file_with_chunks("http://x/out.bin", str(target), lambda p: None, cfg)
    assert not failed, "save_file_with_chunks should succeed"
    assert target.read_bytes() == blob
    # .partN sidecars cleaned up
    assert not list(tmp_path.glob("*.part*"))


def test_chunked_resume_skips_complete_units(tmp_path, monkeypatch):
    blob = bytes((i % 251) for i in range(10 * 1024 * 1024))
    server = _FakeRangeServer(blob)
    _patch(server)
    # Pre-create one chunk file already correct so it is skipped on resume.
    from src.downloaders.chunked import _chunk_path, _load_or_create_plan
    base = tmp_path / "out.bin"
    plan = _load_or_create_plan(base, len(blob), 4)
    first_path = _chunk_path(base, 0)
    s0, e0 = plan[0]
    first_path.write_bytes(blob[s0:e0 + 1])
    cfg = DownloadConfig(
        content_length=len(blob), num_connections=4, headers={}, rate_limiter=None,
    )
    failed = save_file_with_chunks("http://x/out.bin", str(base), lambda p: None, cfg)
    assert not failed
    assert base.read_bytes() == blob
    # the already-complete first chunk was not re-requested
    assert server.calls < 4  # would be 4 if every unit were fetched fresh


def test_rate_limiter_throttle():
    import time
    rl = RateLimiter(rate_bytes_per_sec=1024)  # 1 KB/s, bucket starts with 1 KB
    t0 = time.time()
    rl.consume(2048)  # 2 KB -> ~1s sleep (first KB is free from the prefilled bucket)
    dt = time.time() - t0
    assert dt >= 0.8, dt


def test_rate_limiter_disabled_is_noop():
    import time
    rl = RateLimiter(rate_bytes_per_sec=None)
    t0 = time.time()
    rl.consume(10_000_000)
    assert time.time() - t0 < 0.1


if __name__ == "__main__":
    import tempfile
    d = Path(tempfile.mkdtemp())
    test_compute_unit_ranges_covers_whole_file()
    test_should_use_parallel_download_rules()
    test_chunked_download_reassembles(d, None)
    test_chunked_resume_skips_complete_units(d, None)
    test_rate_limiter_throttle()
    test_rate_limiter_disabled_is_noop()
    print("chunked/rate-limiter tests — passed 6, failed 0")
