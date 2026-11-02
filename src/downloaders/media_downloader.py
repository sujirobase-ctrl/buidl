"""Stream a resolved media file to disk, driving the Rich progress bar."""

from __future__ import annotations

import threading
import time
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.config import (
    AUDIO_EXTENSIONS,
    CHUNK_SIZE,
    RATE_429_BACKOFF,
    RETRY_BACKOFF,
    VIDEO_EXTENSIONS,
    FailReason,
    SkipReason,
    TaskResult,
)
from src.file_utils import (
    extension_from_content_type,
    sanitize_name,
)

from .chunked import (
    DownloadConfig,
    detect_range_support,
    save_file_with_chunks,
    should_use_parallel_download,
)
from .rate_limiter import RateLimiter


@dataclass
class DownloadOutcome:
    """Result of a single file download."""

    result: TaskResult
    reason: SkipReason | FailReason | None = None
    path: Path | None = None
    message: str = ""


class MediaDownloader:
    """Download one file with retries, resume-awareness and progress reporting."""

    def __init__(
        self,
        client,  # noqa: ANN001 - HttpClient
        live_manager,  # noqa: ANN001 - LiveManager
        max_retries: int = 5,
        *,
        dry_run: bool = False,
        num_connections: int = 1,
        rate_limiter: RateLimiter | None = None,
        cancel_event=None,
    ) -> None:
        self.client = client
        self.live_manager = live_manager
        self.max_retries = max_retries
        self.dry_run = dry_run
        self.num_connections = max(1, num_connections)
        self.rate_limiter = rate_limiter
        self.cancel_event = cancel_event
        self._claim_lock = threading.Lock()
        self._claimed_by_url: dict[str, Path] = {}
        self._claimed_paths: set[Path] = set()

    def download(
        self,
        media,  # noqa: ANN001 - ResolvedMedia
        destination_folder: Path,
        task_index: int = 0,
    ) -> DownloadOutcome:
        """Fetch one media item into destination_folder."""
        folder = destination_folder
        if media.subfolder:
            folder = folder / sanitize_name(media.subfolder)

        # Sort each file into Audio/ Videos/ or Photos/ by media type. The
        # directory is only physically created when a file is written below, so
        # a category folder only appears when the thread actually contains that
        # type (per user request: "if there are no videos, just leave the Photos
        # folder" and "when any audio is found, create an Audio folder").
        _ext = Path(media.filename or media.url).suffix.lower()
        if _ext in AUDIO_EXTENSIONS:
            category = "Audio"
        elif _ext in VIDEO_EXTENSIONS:
            category = "Videos"
        else:
            category = "Photos"
        folder = folder / category

        if self.dry_run:
            self.live_manager.update_log(
                event="Dry run",
                details=f"Would download {media.url}",
            )
            return DownloadOutcome(TaskResult.SKIPPED, SkipReason.DRY_RUN)

        folder.mkdir(parents=True, exist_ok=True)
        headers = dict(media.headers or {})

        last_error = ""
        last_status: int | None = None
        for attempt in range(self.max_retries + 1):
            if self.cancel_event is not None and self.cancel_event.is_set():
                return DownloadOutcome(TaskResult.FAILED, FailReason.NETWORK_ERROR, message="Download cancelado; partes preservadas")
            try:
                outcome = self._attempt(media, folder, headers, task_index)
                if outcome.reason is not FailReason.NETWORK_ERROR:
                    return outcome
                last_error = outcome.message
                if attempt < self.max_retries:
                    time.sleep(RETRY_BACKOFF ** min(attempt, 4))
            except requests.HTTPError as error:
                # 429 means the CDN is rate-limiting us by IP — back off harder
                # than a generic network error so we don't extend the ban.
                status = getattr(getattr(error, "response", None), "status_code", None)
                last_status = status
                last_error = str(error)
                if status in (401, 403, 404, 410):
                    return DownloadOutcome(
                        TaskResult.FAILED,
                        FailReason.HTTP_ERROR,
                        message=f"HTTP {status}",
                    )
                if attempt < self.max_retries:
                    if status == 429:
                        retry_after = getattr(error.response, "headers", {}).get("Retry-After", "")
                        try:
                            backoff = min(max(float(retry_after), 0), 60)
                        except ValueError:
                            backoff = min(RATE_429_BACKOFF ** (attempt + 1), 60)
                        if self.cancel_event is not None:
                            self.cancel_event.wait(backoff)
                        else:
                            time.sleep(backoff)
                    else:
                        time.sleep(RETRY_BACKOFF ** min(attempt, 4))
            except requests.RequestException as error:
                # Connection drop / timeout: short backoff.
                last_error = str(error)
                if attempt < self.max_retries:
                    time.sleep(RETRY_BACKOFF ** min(attempt, 4))
            except OSError as error:
                return DownloadOutcome(
                    TaskResult.FAILED,
                    FailReason.WRITE_ERROR,
                    message=str(error),
                )

        return DownloadOutcome(
            TaskResult.FAILED,
            FailReason.HTTP_ERROR if last_status else FailReason.NETWORK_ERROR,
            message=f"HTTP {last_status}" if last_status else last_error,
        )

    # Private helpers
    def _attempt(
        self,
        media,  # noqa: ANN001
        folder: Path,
        headers: dict[str, str],
        task_index: int,
    ) -> DownloadOutcome:
        timeout = (self.client.timeout, max(self.client.timeout, 60))

        # When parallel chunks are requested, probe range support up front via
        # HEAD. If the host allows byte ranges and the file is large enough we
        # go straight to the chunked path (it fetches content-type-free ranges
        # and is resilient to mid-file drops). Otherwise we fall through to the
        # single-stream path below, which opens a full GET.
        if self.num_connections > 1:
            supports_range, content_length = detect_range_support(media.url, headers)
            if should_use_parallel_download(
                content_length, self.num_connections, supports_range=supports_range,
            ):
                filename = sanitize_name(media.filename or "file")
                target = folder / filename
                claimed_by_other = self._is_claimed_by_other(media.state_key, target)
                if (
                    not media.force_unique
                    and not claimed_by_other
                    and target.exists()
                    and target.stat().st_size > 0
                ):
                    return DownloadOutcome(
                        TaskResult.SKIPPED, SkipReason.ALREADY_DOWNLOADED, path=target,
                    )
                target = self._claim_target(media.state_key, target)
                task_id = self.live_manager.add_task(task_index, total=100)

                def _cb(pct: float) -> None:
                    self.live_manager.update_task(task_id, completed=pct)

                failed = save_file_with_chunks(
                    media.url,
                    str(target),
                    _cb,
                    DownloadConfig(
                        content_length=content_length,
                        num_connections=self.num_connections,
                        headers=headers,
                        rate_limiter=self.rate_limiter,
                    ),
                )
                if not failed:
                    return DownloadOutcome(TaskResult.COMPLETED, path=target)
                # Persistent chunk failure -> fall through to single-stream so
                # the outer retry budget still applies.

        with self.client.get(
            media.url,
            headers=headers,
            stream=True,
            timeout=timeout,
        ) as response:
            if response.status_code == 404:
                return DownloadOutcome(
                    TaskResult.FAILED,
                    FailReason.HTTP_ERROR,
                    message="HTTP 404",
                )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            # Hosts sometimes answer a 200 with an HTML error/login page
            # instead of the file. Saving that as a ".bin" pollutes the
            # output, so reject non-media responses up front.
            if "text/html" in content_type or "application/xhtml" in content_type:
                reason = (
                    FailReason.NETWORK_ERROR
                    if (urlparse(media.url).hostname or "").casefold() == "i.redd.it"
                    else FailReason.HTTP_ERROR
                )
                return DownloadOutcome(
                    TaskResult.FAILED,
                    reason,
                    message=f"Got HTML ({content_type}) instead of a file",
                )

            filename = self._final_filename(media, response)
            target = folder / filename

            # Resume / skip logic. A previous run that fully completed a file
            # leaves a non-empty target on disk; re-downloading it wastes
            # bandwidth (and for multi-GB files is very expensive), so we skip
            # any existing non-empty file regardless of whether the server
            # reports a matching Content-Length. The only case we re-fetch is a
            # 0-byte stub left behind by an interrupted run, which we overwrite
            # in place rather than renaming to "name (1)".
            claimed_by_other = self._is_claimed_by_other(media.state_key, target)
            if not media.force_unique and not claimed_by_other and target.exists():
                existing = target.stat().st_size
                if existing > 0:
                    return DownloadOutcome(
                        TaskResult.SKIPPED,
                        SkipReason.ALREADY_DOWNLOADED,
                        path=target,
                    )
                target.unlink()  # 0-byte stub -> overwrite

            target = self._claim_target(media.state_key, target)

            # === Single-stream path (fallback) =============================
            # Resume an interrupted .part: if a previous attempt wrote bytes
            # before the connection dropped, ask the server for the remaining
            # range and append. Servers without Range support return 200 (full
            # body) and we restart cleanly via "wb".
            temp_path = target.with_suffix(target.suffix + ".part")
            resume_pos = temp_path.stat().st_size if temp_path.exists() else 0
            get_headers = dict(headers)
            if resume_pos:
                get_headers["Range"] = f"bytes={resume_pos}-"
            if resume_pos:
                with self.client.get(
                    media.url,
                    headers=get_headers,
                    stream=True,
                    timeout=timeout,
                ) as resume_resp:
                    if resume_resp.status_code == 206:
                        return self._stream_to_file(
                            resume_resp, temp_path, resume_pos, task_index,
                        )
                    if resume_resp.status_code == 200:
                        temp_path.unlink(missing_ok=True)
                        return self._stream_to_file(
                            resume_resp, temp_path, 0, task_index,
                        )
                    # Server refused the range; use the fresh GET opened above.
                    temp_path.unlink(missing_ok=True)

            return self._stream_to_file(response, temp_path, 0, task_index)

    def _stream_to_file(
        self,
        response,  # noqa: ANN001 - requests.Response
        temp_path: Path,
        resume_pos: int,
        task_index: int,
    ) -> DownloadOutcome:
        total = int(response.headers.get("Content-Length") or 0) + resume_pos
        mode = "ab" if resume_pos else "wb"
        downloaded = resume_pos
        task_id = self.live_manager.add_task(task_index, total=total or 100)
        try:
            with temp_path.open(mode) as handle:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if self.cancel_event is not None and self.cancel_event.is_set():
                        return DownloadOutcome(TaskResult.FAILED, FailReason.NETWORK_ERROR, message="Download cancelado; partes preservadas")
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.live_manager.update_task(task_id, completed=downloaded)
                    else:
                        self.live_manager.update_task(task_id, advance=1)
                handle.flush()
                os.fsync(handle.fileno())
        except (requests.RequestException, OSError) as error:
            return DownloadOutcome(
                TaskResult.FAILED,
                FailReason.NETWORK_ERROR if isinstance(error, requests.RequestException)
                else FailReason.WRITE_ERROR,
                message=str(error),
            )

        content_encoding = response.headers.get("Content-Encoding", "").lower()
        if total and content_encoding in ("", "identity") and downloaded != total:
            return DownloadOutcome(
                TaskResult.FAILED,
                FailReason.NETWORK_ERROR,
                message=(
                    f"Incomplete response: expected {total} bytes, "
                    f"received {downloaded}"
                ),
            )

        temp_path.replace(target_path := temp_path.with_name(
            temp_path.name[: -len(".part")] if temp_path.name.endswith(".part") else temp_path.name,
        ))
        return DownloadOutcome(TaskResult.COMPLETED, path=target_path)

    def _claim_target(self, media_url: str, target: Path) -> Path:
        """Reserve a collision-free output path across concurrent workers."""
        with self._claim_lock:
            claimed = self._claimed_by_url.get(media_url)
            if claimed is not None:
                return claimed

            candidate = target
            counter = 1
            while candidate in self._claimed_paths or candidate.exists():
                candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
                counter += 1

            self._claimed_by_url[media_url] = candidate
            self._claimed_paths.add(candidate)
            return candidate

    def _is_claimed_by_other(self, media_url: str, target: Path) -> bool:
        with self._claim_lock:
            return (
                target in self._claimed_paths
                and self._claimed_by_url.get(media_url) != target
            )

    @staticmethod
    def _final_filename(media, response: requests.Response) -> str:  # noqa: ANN001
        filename = sanitize_name(media.filename or "")

        disposition = response.headers.get("Content-Disposition", "")
        if not filename and "filename=" in disposition:
            raw = disposition.split("filename=")[-1].strip('";\' ')
            filename = sanitize_name(raw)

        if not filename:
            filename = "file"

        if "." not in filename:
            extension = extension_from_content_type(response.headers.get("Content-Type"))
            filename = f"{filename}.{extension}"

        return filename
