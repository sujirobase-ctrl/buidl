"""Parallel byte-range chunked download with per-chunk resume.

Adapted in design from Lysagxra/BunkrDownloader (chunked download_utils). The
algorithm is host-agnostic: given a URL, request headers and a known content
length, it splits the file into many small byte-range work units, downloads them
concurrently, and reassembles them. A dropped connection only fails the unit it
was writing — the next run re-fetches just the missing units instead of the whole
file. This is what keeps multi-GB host files (filester/bunkr) from restarting
from zero every time the CDN throttles or resets the connection.
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import requests
from requests.exceptions import RequestException

from ..config import (
    CHUNK_BASE_DELAY,
    CHUNK_MAX_RETRIES,
    LARGE_FILE_CHUNK_SIZE,
    MAX_WORK_UNIT_SIZE,
    MIN_PARALLEL_SIZE,
    MIN_WORK_UNIT_SIZE,
    UNITS_PER_CONNECTION,
)
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)


@dataclass
class DownloadConfig:
    """Everything the chunked path needs for one file."""

    content_length: int
    num_connections: int
    headers: dict[str, str]
    rate_limiter: RateLimiter | None = None


@dataclass
class ChunkInfo:
    """Per-chunk context passed to the worker."""

    headers: dict[str, str]
    on_progress: callable  # (n_bytes: int) -> None
    rate_limiter: RateLimiter | None = None


@dataclass
class DownloadPlan:
    """Resolved partition of a file into byte ranges + their .partN paths."""

    ranges: list[tuple[int, int]]
    num_ranges: int
    chunk_paths: list[Path]
    expected_sizes: list[int]


def detect_range_support(url: str, headers: dict[str, str]) -> tuple[bool, int]:
    """HEAD the URL to learn whether it supports byte ranges and its size."""
    try:
        response = requests.head(url, headers=headers, timeout=10)
        response.raise_for_status()
        supports_range = response.headers.get("Accept-Ranges", "").lower() == "bytes"
        content_length = int(response.headers.get("Content-Length", -1))
    except (RequestException, ValueError):
        return False, -1
    return supports_range, content_length


def should_use_parallel_download(
    content_length: int,
    num_connections: int,
    *,
    supports_range: bool,
) -> bool:
    """Chunk only when the server allows ranges, the file is big, and >1 conn."""
    return (
        supports_range
        and content_length >= MIN_PARALLEL_SIZE
        and num_connections > 1
    )


def compute_unit_ranges(content_length: int, num_connections: int) -> list[tuple[int, int]]:
    """Split the file into many small units for work-stealing.

    Produces more units than worker threads; each sized between
    MIN_WORK_UNIT_SIZE and MAX_WORK_UNIT_SIZE. Idle threads pull the next pending
    unit, so a slow connection only delays its own next unit.
    """
    target_units = max(num_connections * UNITS_PER_CONNECTION, 1)
    raw_unit_size = content_length / target_units
    unit_size = max(MIN_WORK_UNIT_SIZE, min(int(raw_unit_size), MAX_WORK_UNIT_SIZE), 1)
    num_units = (content_length + unit_size - 1) // unit_size  # ceil
    ranges: list[tuple[int, int]] = []
    for indx in range(num_units):
        start_byte = indx * unit_size
        end_byte = (
            (start_byte + unit_size - 1) if indx < num_units - 1 else content_length - 1
        )
        ranges.append((start_byte, end_byte))
    return ranges


def _plan_path(base_path: Path) -> Path:
    return Path(f"{base_path}.parts")


def _load_or_create_plan(
    base_path: Path,
    content_length: int,
    num_connections: int,
) -> list[tuple[int, int]]:
    """Reuse a persisted partition so resume after changing --connections is safe."""
    plan_path = _plan_path(base_path)
    if plan_path.exists():
        try:
            data = json.loads(plan_path.read_text(encoding="utf-8"))
            if data.get("content_length") == content_length:
                return [tuple(pair) for pair in data["ranges"]]
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # corrupt -> recompute

    ranges = compute_unit_ranges(content_length, num_connections)
    try:
        plan_path.write_text(
            json.dumps({"content_length": content_length, "ranges": ranges}),
            encoding="utf-8",
        )
    except OSError:
        log.warning("Could not persist chunk plan for %s", base_path)
    return ranges


def _chunk_path(base_path: Path, index: int) -> Path:
    return base_path.with_suffix(f".part{index}")


def _attempt_chunk_once(
    url: str,
    byte_range: tuple[int, int],
    path: Path,
    chunk_info: ChunkInfo,
) -> bool:
    """Download one byte-range unit once. Returns True on failure."""
    start_byte, end_byte = byte_range
    expected = end_byte - start_byte + 1
    chunk_headers = {**chunk_info.headers, "Range": f"bytes={start_byte}-{end_byte}"}
    written = 0
    try:
        with requests.get(
            url,
            headers=chunk_headers,
            stream=True,
            timeout=30,
        ) as response:
            response.raise_for_status()
            with path.open("wb") as handle:
                for data in response.iter_content(chunk_size=LARGE_FILE_CHUNK_SIZE):
                    if data:
                        handle.write(data)
                        num_bytes = len(data)
                        if chunk_info.rate_limiter:
                            chunk_info.rate_limiter.consume(num_bytes)
                        written += num_bytes
                        chunk_info.on_progress(num_bytes)
        if path.exists() and path.stat().st_size == expected:
            return False
    except (RequestException, OSError):
        chunk_info.on_progress(-written)
        return True
    chunk_info.on_progress(-written)
    return True


def _download_single_chunk(
    url: str,
    byte_range: tuple[int, int],
    path: Path,
    chunk_info: ChunkInfo,
) -> bool:
    """Download one unit with internal retries; skip if already complete."""
    start_byte, end_byte = byte_range
    expected = end_byte - start_byte + 1
    if path.exists() and path.stat().st_size == expected:
        chunk_info.on_progress(expected)
        return False
    for attempt in range(1, CHUNK_MAX_RETRIES + 1):
        if not _attempt_chunk_once(url, byte_range, path, chunk_info):
            return False
        if attempt < CHUNK_MAX_RETRIES:
            time.sleep(CHUNK_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 1))
    return True


def _build_download_plan(
    base_path: Path,
    content_length: int,
    num_connections: int,
) -> DownloadPlan:
    ranges = _load_or_create_plan(base_path, content_length, num_connections)
    return DownloadPlan(
        ranges=ranges,
        num_ranges=len(ranges),
        chunk_paths=[_chunk_path(base_path, i) for i in range(len(ranges))],
        expected_sizes=[end - start + 1 for start, end in ranges],
    )


def download_chunks(
    url: str,
    base_path: Path,
    live_callback,  # callable(completed_pct: float) -> None
    config: DownloadConfig,
) -> tuple[list[Path], list[int], bool]:
    """Download all units in parallel; return (chunk_paths, sizes, any_failed)."""
    lock = threading.Lock()
    total_downloaded = [0]

    def on_progress(num_bytes: int) -> None:
        with lock:
            total_downloaded[0] += num_bytes
            completed = min((total_downloaded[0] / config.content_length) * 100, 100.0)
        live_callback(completed)

    any_failed = False
    plan = _build_download_plan(base_path, config.content_length, config.num_connections)
    max_workers = min(config.num_connections, plan.num_ranges)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _download_single_chunk,
                url,
                byte_range,
                path,
                ChunkInfo(
                    headers=config.headers,
                    on_progress=on_progress,
                    rate_limiter=config.rate_limiter,
                ),
            ): path
            for byte_range, path in zip(plan.ranges, plan.chunk_paths)
        }
        for future in as_completed(futures):
            if future.result():
                any_failed = True

    return plan.chunk_paths, plan.expected_sizes, any_failed


def verify_chunks(chunk_paths: list[Path], expected_sizes: list[int]) -> bool:
    """True when every chunk exists and matches its expected byte count."""
    return all(
        path.exists() and path.stat().st_size == size
        for path, size in zip(chunk_paths, expected_sizes)
    )


def merge_chunks(chunk_paths: list[Path], final_path: Path) -> None:
    """Concatenate ordered .partN files into the final destination."""
    staged = final_path.with_name(final_path.name + ".merge.part")
    with staged.open("wb") as destination:
        for chunk_path in chunk_paths:
            with chunk_path.open("rb") as chunk_file:
                shutil.copyfileobj(chunk_file, destination)
        destination.flush()
        os.fsync(destination.fileno())
    staged.replace(final_path)


def cleanup(chunk_paths: list[Path], base_path: Path) -> None:
    """Remove .partN files and the plan sidecar after a successful merge."""
    for path in [*chunk_paths, _plan_path(base_path)]:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            log.warning("Could not remove chunk file: %s", path)


def save_file_with_chunks(
    url: str,
    download_path: str,
    live_callback,  # callable(completed_pct: float) -> None
    config: DownloadConfig,
) -> bool:
    """Download via parallel byte-range chunks, resumable across runs.

    Returns True on failure (.partN files kept for resume), False on success.
    """
    base_path = Path(download_path)
    chunk_paths, expected_sizes, any_failed = download_chunks(
        url, base_path, live_callback, config,
    )
    if any_failed or not verify_chunks(chunk_paths, expected_sizes):
        return True
    merge_chunks(chunk_paths, base_path)
    cleanup(chunk_paths, base_path)
    return False
