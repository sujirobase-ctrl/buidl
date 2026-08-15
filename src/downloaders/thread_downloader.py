"""Orchestrate a whole thread: parse pages, resolve hosts, download everything."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from src.config import FailReason, SkipReason, TaskResult, download_root
from src.error_summary import summarize_error
from src.file_utils import load_state, matches_any, sanitize_name, save_state
from src.parsers import ParsedPost, ThreadParser, parse_hosts
from src.resolvers import ResolvedMedia, resolve

from .media_downloader import MediaDownloader
from .rate_limiter import RateLimiter

LOGIN_WALL_MARKERS = (
    "you must be logged in",
    "log in or register",
    "please log in to view",
    "you do not have permission",
    "register to view",
    "sign up to view",
)


def looks_like_login_wall(soup) -> bool:  # noqa: ANN001
    """Heuristic: did the forum serve a login/permission page instead of posts?

    Only consulted when a page yielded zero posts, so it needs to separate a
    real login wall from an ordinary empty page. Deliberately conservative:
    matching is limited to the page body text and a visible login form, and
    the markers are full phrases — a thread merely *titled* something like
    "Members Only" must not trip it.
    """
    if soup.select_one("form[action*='login/login'], form.js-loginForm"):
        return True

    body = soup.select_one(".p-body-main, .p-body, body") or soup
    text = body.get_text(" ", strip=True).lower()[:4000]
    return any(marker in text for marker in LOGIN_WALL_MARKERS)


@dataclass
class ThreadOptions:
    """Runtime options for a thread download."""

    custom_path: str | None = None
    download_path: str | None = None
    max_pages: int = 1
    all_pages: bool = False
    post_ids: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    workers: int = 3
    max_retries: int = 5
    delay: float = 0.0
    connections: int = 1
    rate_limit: float | None = None
    dry_run: bool = False
    separate_posts: bool = False
    flat: bool = False
    clean_part: bool = False
    cancel_event: threading.Event | None = None
    pause_event: threading.Event | None = None


class ThreadDownloader:
    """Walk a forum thread and download every media item it references."""

    def __init__(
        self,
        client,  # noqa: ANN001 - HttpClient
        live_manager,  # noqa: ANN001 - LiveManager
        options: ThreadOptions,
    ) -> None:
        self.client = client
        self.live_manager = live_manager
        self.options = options
        self.rate_limiter = RateLimiter(options.rate_limit)
        self.downloader = MediaDownloader(
            client,
            live_manager,
            max_retries=options.max_retries,
            dry_run=options.dry_run,
            num_connections=options.connections,
            rate_limiter=self.rate_limiter,
        )

    def download_thread(self, url: str) -> bool:
        """Download a whole thread. Returns True when something failed."""
        pages = self._collect_pages(url)
        if self._cancelled():
            self._log_cancelled()
            return True
        if not pages:
            self.live_manager.update_log(
                event="Empty thread",
                details=f"No posts parsed from {url}",
            )
            return True

        title, posts = pages
        root = self._download_root() / sanitize_name(title)
        state = load_state(root)

        media_plan = self._build_plan(posts, root)
        if self._cancelled():
            self._log_cancelled()
            return True
        if not media_plan:
            self.live_manager.update_log(
                event="Nothing to download",
                details=f"No supported hosts found in {title}",
            )
            return False

        self.live_manager.add_overall_task(title, num_tasks=len(media_plan))
        self.live_manager.update_log(
            event="Thread parsed",
            details=f"{title} — {len(posts)} posts, {len(media_plan)} files",
        )

        had_failure = self._run_downloads(media_plan, state, root)
        if self._cancelled():
            self._log_cancelled()
        self._report_leftover_parts(root)
        return had_failure or self._cancelled()

    def _cancelled(self) -> bool:
        event = self.options.cancel_event
        return bool(event and event.is_set())

    def _download_root(self) -> Path:
        """Return the exact media root requested by a GUI or the CLI default."""
        if self.options.download_path:
            return Path(self.options.download_path)
        return download_root(self.options.custom_path)

    def _wait_until_runnable(self) -> bool:
        """Wait while paused and return False as soon as cancellation is requested."""
        pause_event = self.options.pause_event
        while pause_event is not None and not pause_event.is_set():
            if self._cancelled():
                return False
            pause_event.wait(0.2)
        return not self._cancelled()

    def _log_cancelled(self) -> None:
        self.live_manager.update_log(
            event="Cancelled",
            details="The operation was cancelled by the user.",
        )

    def _report_leftover_parts(self, root: Path) -> None:
        """Warn about (and optionally delete) orphaned .part temp files.

        A .part is an incomplete download interrupted by a network error. They
        are intentionally kept so the next run can resume from the bytes
        already written, but the user should be told they exist — previously
        they silently littered the output folder and looked like a filtering
        bug. With ``--clean-part`` they are removed at the end of the run.
        """
        if self.options.dry_run:
            return
        parts = [p for p in root.rglob("*.part") if p.is_file()]
        if not parts:
            return

        total_bytes = sum(p.stat().st_size for p in parts)
        size_mb = total_bytes / (1024 * 1024)
        if self.options.clean_part:
            removed = 0
            for part in parts:
                try:
                    part.unlink()
                    removed += 1
                except OSError:
                    pass
            self.live_manager.update_log(
                event="Cleaned .part",
                details=(
                    f"Removed {removed}/{len(parts)} incomplete temp file(s) "
                    f"({size_mb:.1f} MB). Re-run without --clean-part to keep "
                    "them for resume."
                ),
            )
        else:
            self.live_manager.update_log(
                event="Incomplete files left",
                details=(
                    f"{len(parts)} file(s) ({size_mb:.1f} MB) are incomplete "
                    ".part downloads interrupted by a network error. They are "
                    "kept for resume on the next run; add --clean-part to delete "
                    "them, or re-run to finish downloading."
                ),
            )

    # Private helpers
    def _collect_pages(self, url: str) -> tuple[str, list[ParsedPost]] | None:
        posts: list[ParsedPost] = []
        title = ""
        current = url
        pages_left = 10_000 if self.options.all_pages else max(self.options.max_pages, 1)

        while current and pages_left > 0:
            if not self._wait_until_runnable():
                break
            try:
                response = self.client.get(current)
            except Exception as error:  # noqa: BLE001
                self.live_manager.update_log(
                    event="Page error",
                    details=f"{current}: {error}",
                )
                break

            if response.status_code in (401, 403):
                self.live_manager.update_log(
                    event="Access denied",
                    details=(
                        f"HTTP {response.status_code} for {current} — this forum "
                        "requires a logged-in session. Re-run with a cookies file "
                        "(--cookies path/to/cookies.txt) exported from a browser "
                        "where you are logged in."
                    ),
                )
                break

            if response.status_code >= 400:
                self.live_manager.update_log(
                    event="Page error",
                    details=f"HTTP {response.status_code} for {current}",
                )
                break

            from bs4 import BeautifulSoup  # noqa: PLC0415

            soup = BeautifulSoup(response.text, "html.parser")
            parser = ThreadParser(soup, current)
            if not title:
                title = parser.parse_title()

            page_posts = parser.parse_posts()

            if not page_posts and looks_like_login_wall(soup):
                self.live_manager.update_log(
                    event="Login required",
                    details=(
                        f"{current} returned a login/permission page instead of "
                        "posts. Supply a cookies file from a logged-in browser "
                        "session (--cookies path/to/cookies.txt)."
                    ),
                )
                break

            posts.extend(page_posts)
            self.live_manager.update_log(
                event="Page parsed",
                details=f"{current} — {len(page_posts)} posts",
            )

            pages_left -= 1
            current = parser.next_page_url() if pages_left > 0 else None

        if not posts:
            return None
        return title or "thread", posts

    def _build_plan(
        self,
        posts: list[ParsedPost],
        root: Path,
    ) -> list[tuple[ResolvedMedia, Path]]:
        plan: list[tuple[ResolvedMedia, Path]] = []
        seen: set[str] = set()
        posts_with_links = 0
        unresolved_hosts = 0

        selected = [
            post
            for post in posts
            if not self.options.post_ids
            or post.post_id in self.options.post_ids
            or post.post_number in self.options.post_ids
        ]

        for post in selected:
            if not self._wait_until_runnable():
                break
            matches = parse_hosts(post.html_content)
            if not matches:
                continue

            posts_with_links += 1
            destination = root
            if self.options.separate_posts and not self.options.flat:
                destination = root / sanitize_name(post.label)

            for match in matches:
                if not self._wait_until_runnable():
                    break
                resolved = resolve(match.url, self.client)
                self.live_manager.update_log(
                    event="Resolved",
                    details=(
                        f"[{match.name}] {match.url} -> "
                        f"{len(resolved)} file(s)"
                    ),
                    verbose_only=True,
                )
                if not resolved:
                    unresolved_hosts += 1

                for media in resolved:
                    if self.options.flat:
                        media.subfolder = ""
                    key = media.url
                    if key in seen:
                        self.live_manager.update_log(
                            event="Duplicate",
                            details=f"Already queued: {key}",
                            verbose_only=True,
                        )
                        continue
                    seen.add(key)

                    if not self._passes_filters(media.filename or media.url):
                        self.live_manager.update_log(
                            event="Filtered",
                            details=f"Excluded by --ignore/--include: {media.filename or key}",
                            verbose_only=True,
                        )
                        continue

                    self.live_manager.update_log(
                        event="Queued",
                        details=f"{media.filename or key} <- {media.url}",
                        verbose_only=True,
                    )
                    plan.append((media, destination))

        self._warn_if_session_looks_stale(
            posts=len(selected),
            posts_with_links=posts_with_links,
            unresolved_hosts=unresolved_hosts,
            planned=len(plan),
        )
        return plan

    def _warn_if_session_looks_stale(
        self,
        *,
        posts: int,
        posts_with_links: int,
        unresolved_hosts: int,
        planned: int,
    ) -> None:
        """Flag the "parsed fine but produced nothing" shape of an expired login.

        A 403 is caught upfront, but a session that lapses mid-run (or a forum
        that hides attachments from guests) still returns readable post HTML —
        just with the media links stripped. That looks like success everywhere
        except the file count, so it is called out explicitly here.
        """
        if posts == 0:
            return

        if posts_with_links == 0:
            self.live_manager.update_log(
                event="No media links",
                details=(
                    f"Parsed {posts} posts but none contained a supported host "
                    "link. If this thread should have attachments, your session "
                    "may have expired or the forum hides media from guests — "
                    "re-export cookies.txt and retry with --reset-cookies."
                ),
            )
            return

        if planned == 0 and unresolved_hosts:
            self.live_manager.update_log(
                event="All hosts unresolved",
                details=(
                    f"Found host links in {posts_with_links} posts but resolved "
                    f"0 files ({unresolved_hosts} host pages returned nothing). "
                    "The hosts may require a login, be rate-limiting, or have "
                    "changed layout. Run with --verbose to see each attempt."
                ),
            )
            return

        # Media links exist but most hosts produced nothing: partial breakage.
        if posts_with_links and unresolved_hosts >= max(3, posts_with_links // 2):
            self.live_manager.update_log(
                event="Many unresolved hosts",
                details=(
                    f"{unresolved_hosts} host links resolved to no files while "
                    f"{planned} were queued. Possible expired session or rate "
                    "limiting — check the log and consider --reset-cookies."
                ),
            )

    def _passes_filters(self, filename: str) -> bool:
        if self.options.ignore and matches_any(self.options.ignore, filename):
            self.live_manager.update_summary(TaskResult.SKIPPED, SkipReason.IGNORED_EXTENSION)
            return False
        if self.options.include and not matches_any(self.options.include, filename):
            self.live_manager.update_summary(TaskResult.SKIPPED, SkipReason.NOT_INCLUDED)
            return False
        return True

    @staticmethod
    def _cached_file_is_complete(cached: object, root: Path) -> bool:
        """Trust only state entries whose on-disk path and size still match."""
        if cached == "completed":
            # Legacy entries had no path/size to validate. Let MediaDownloader
            # inspect the destination once, then upgrade the state entry.
            return False
        if not isinstance(cached, dict) or cached.get("status") != "completed":
            return False

        relative_path = cached.get("path")
        expected_size = cached.get("size")
        if not isinstance(relative_path, str) or not isinstance(expected_size, int):
            return False

        root_resolved = root.resolve()
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            return False
        return candidate.is_file() and candidate.stat().st_size == expected_size > 0

    @staticmethod
    def _completed_state(path: Path, root: Path) -> dict[str, object]:
        """Build a verifiable, root-relative resume entry for a completed file."""
        return {
            "status": "completed",
            "path": path.resolve().relative_to(root.resolve()).as_posix(),
            "size": path.stat().st_size,
        }

    def _run_downloads(
        self,
        plan: list[tuple[ResolvedMedia, Path]],
        state: dict,
        root: Path,
    ) -> bool:
        had_failure = False
        workers = max(1, self.options.workers)

        def job(index: int, media: ResolvedMedia, folder: Path):  # noqa: ANN202
            if not self._wait_until_runnable():
                return None
            # A small delay between file starts keeps rate-limiting CDNs
            # (filester, bunkr) happy when several workers run in parallel.
            if self.options.delay:
                wait = self.options.delay * ((index % max(1, workers)) + 1)
                cancel_event = self.options.cancel_event
                if cancel_event is not None:
                    if cancel_event.wait(wait):
                        return None
                else:
                    time.sleep(wait)
            if not self._wait_until_runnable():
                return None
            cached = state.get(media.url)
            if self._cached_file_is_complete(cached, root) and not self.options.dry_run:
                self.live_manager.update_summary(
                    TaskResult.SKIPPED,
                    SkipReason.ALREADY_DOWNLOADED,
                )
                self.live_manager.update_task(
                    self.live_manager.add_task(index, total=1),
                    completed=1,
                )
                return None
            return self.downloader.download(media, folder, index)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(job, index, media, folder): media
                for index, (media, folder) in enumerate(plan)
            }

            for future in as_completed(futures):
                media = futures[future]
                try:
                    outcome = future.result()
                except Exception as error:  # noqa: BLE001
                    had_failure = True
                    self.live_manager.update_summary(TaskResult.FAILED, FailReason.UNRESOLVED)
                    message = summarize_error(str(error))
                    self.live_manager.update_log(
                        event="Unexpected error",
                        details=(
                            f"{media.filename or 'arquivo sem nome'} — {message}\n"
                            f"URL: {media.url}"
                        ),
                    )
                    state[media.url] = {
                        "status": "failed",
                        "filename": media.filename or "",
                        "reason": FailReason.UNRESOLVED.name,
                        "message": message,
                    }
                    continue

                if outcome is None:
                    continue

                self.live_manager.update_summary(outcome.result, outcome.reason)
                if (
                    outcome.path
                    and outcome.result in (TaskResult.COMPLETED, TaskResult.SKIPPED)
                    and outcome.reason in (None, SkipReason.ALREADY_DOWNLOADED)
                ):
                    state[media.url] = self._completed_state(outcome.path, root)
                if outcome.result is TaskResult.FAILED:
                    had_failure = True
                    message = self._failure_message(outcome.reason, outcome.message)
                    state[media.url] = {
                        "status": "failed",
                        "filename": media.filename or "",
                        "reason": (
                            outcome.reason.name
                            if outcome.reason is not None
                            else "UNKNOWN"
                        ),
                        "message": message,
                    }
                    self.live_manager.update_log(
                        event="Download failed",
                        details=(
                            f"{media.filename or 'arquivo sem nome'} — {message}\n"
                            f"URL: {media.url}"
                        ),
                    )
                elif outcome.result is TaskResult.SKIPPED:
                    state[media.url] = {"status": outcome.result.name.lower()}
                elif outcome.result is TaskResult.COMPLETED and outcome.path:
                    self.live_manager.update_log(
                        event="Downloaded",
                        details=outcome.path.name,
                    )

        if not self.options.dry_run:
            save_state(root, state)

        return had_failure

    @staticmethod
    def _failure_message(reason, raw_message: str) -> str:  # noqa: ANN001
        """Return a useful Portuguese explanation for a failed media item."""
        if reason is FailReason.WRITE_ERROR:
            return f"erro ao gravar no disco: {raw_message or 'motivo desconhecido'}"
        if reason is FailReason.UNRESOLVED:
            return "não foi possível resolver o link do arquivo"
        if reason in (FailReason.HTTP_ERROR, FailReason.NETWORK_ERROR):
            return summarize_error(raw_message)
        if raw_message:
            return summarize_error(raw_message)
        return "falha desconhecida"
