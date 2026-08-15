from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

from gui import BuidlApp, GuiManager
from src.config import FailReason, TaskResult
from src.downloaders.media_downloader import DownloadOutcome
from src.downloaders.thread_downloader import ThreadDownloader, ThreadOptions
from src.resolvers import ResolvedMedia


def test_gui_manager_emits_plan_and_progress(tmp_path) -> None:
    events = queue.Queue()
    manager = GuiManager(events, tmp_path / "gui.log")

    manager.add_overall_task("Example", 2)
    manager.update_summary(TaskResult.COMPLETED)
    manager.update_summary(TaskResult.SKIPPED)

    assert events.get_nowait() == ("plan", "Example", 2)
    first = events.get_nowait()
    second = events.get_nowait()
    assert first[0] == "progress"
    assert first[1]["completed"] == 1
    assert second[1] == {"completed": 1, "skipped": 1, "failed": 0}


def test_gui_manager_emits_failure_details(tmp_path) -> None:
    events = queue.Queue()
    manager = GuiManager(events, tmp_path / "gui.log")

    manager.update_log(
        event="Download failed",
        details="photo.jpg — arquivo não encontrado (404)\nURL: https://host/photo.jpg",
    )

    log_event = events.get_nowait()
    failure_event = events.get_nowait()
    assert log_event[0] == "log"
    assert failure_event[0] == "failure"
    assert "photo.jpg" in failure_event[3]
    assert "404" in failure_event[3]


@pytest.mark.parametrize("value", ["0", "-1", "text"])
def test_gui_rejects_invalid_positive_integers(value: str) -> None:
    with pytest.raises(ValueError):
        BuidlApp._positive_int(value, "Workers")


def test_cancel_event_stops_new_downloader_work() -> None:
    cancel_event = threading.Event()
    cancel_event.set()
    downloader = ThreadDownloader.__new__(ThreadDownloader)
    downloader.options = ThreadOptions(cancel_event=cancel_event)

    assert downloader._cancelled()
    assert not downloader._wait_until_runnable()


def test_pause_event_allows_work_when_set() -> None:
    pause_event = threading.Event()
    pause_event.set()
    downloader = ThreadDownloader.__new__(ThreadDownloader)
    downloader.options = ThreadOptions(pause_event=pause_event)

    assert downloader._wait_until_runnable()


def test_gui_download_path_is_used_as_exact_root(tmp_path) -> None:
    downloader = ThreadDownloader.__new__(ThreadDownloader)
    downloader.options = ThreadOptions(
        custom_path="ignored-base",
        download_path=str(tmp_path / "My Media"),
    )

    assert downloader._download_root() == Path(tmp_path / "My Media")


def test_thread_downloader_logs_and_persists_each_failed_item(tmp_path) -> None:
    class Manager:
        def __init__(self) -> None:
            self.logs = []

        def update_summary(self, *_args) -> None:
            pass

        def update_log(self, **kwargs) -> None:
            self.logs.append(kwargs)

    class FailedDownloader:
        @staticmethod
        def download(*_args):
            return DownloadOutcome(
                TaskResult.FAILED,
                FailReason.HTTP_ERROR,
                message="HTTP 404",
            )

    manager = Manager()
    downloader = ThreadDownloader.__new__(ThreadDownloader)
    downloader.options = ThreadOptions(workers=1)
    downloader.live_manager = manager
    downloader.downloader = FailedDownloader()
    state = {}
    media = ResolvedMedia(url="https://host/missing.jpg", filename="missing.jpg")

    failed = downloader._run_downloads([(media, tmp_path)], state, tmp_path)

    assert failed
    assert state[media.url]["status"] == "failed"
    assert state[media.url]["reason"] == "HTTP_ERROR"
    assert "404" in state[media.url]["message"]
    detail = next(item for item in manager.logs if item["event"] == "Download failed")
    assert "missing.jpg" in detail["details"]
    assert media.url in detail["details"]
