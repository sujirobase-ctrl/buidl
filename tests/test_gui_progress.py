"""Regression coverage for byte-level progress in the Qt interface."""

from __future__ import annotations

import queue

from gui_qt import GuiManager
from src.config import TaskResult
from src.downloaders import ThreadDownloader, ThreadOptions
from src.http_client import HttpClient
from src.preview import media_kind
from tests.mock_forum import BASE, serve


def _drain(events: queue.Queue) -> list[tuple]:
    drained = []
    while not events.empty():
        drained.append(events.get_nowait())
    return drained


def test_gui_manager_reports_partial_file_progress(tmp_path) -> None:
    events: queue.Queue = queue.Queue()
    manager = GuiManager(events, tmp_path / "gui.log")
    manager.add_overall_task("Thread de teste", 2)
    task_id = manager.add_task(0, total=100)
    manager.update_task(task_id, completed=25)

    transfers = [event for event in _drain(events) if event[0] == "transfer"]
    assert transfers[-1][3] == 0.25
    assert transfers[-1][4] == 1

    manager.update_task(task_id, completed=100)
    manager.update_summary(TaskResult.COMPLETED)
    transfers = [event for event in _drain(events) if event[0] == "transfer"]
    assert transfers[-1][3] == 1.0
    assert transfers[-1][4] == 0


def test_qt_manager_tracks_real_filtered_download(tmp_path) -> None:
    server = serve()
    events: queue.Queue = queue.Queue()
    manager = GuiManager(events, tmp_path / "gui.log")
    try:
        with HttpClient(max_retries=1) as client:
            downloader = ThreadDownloader(
                client,
                manager,
                ThreadOptions(
                    download_path=str(tmp_path / "downloads"),
                    all_pages=True,
                    workers=2,
                    max_retries=1,
                    delay=0,
                ),
            )
            prepared = downloader.prepare_thread(
                f"{BASE}/threads/test-thread.123/"
            )
            assert prepared is not None
            selected = {
                media.state_key
                for media, _folder in prepared.plan
                if media_kind(media) == "Imagens"
            }
            manager.reset_summary()
            assert downloader.download_prepared(prepared, selected) is False
    finally:
        server.shutdown()

    transfers = [event for event in _drain(events) if event[0] == "transfer"]
    final = transfers[-1]
    assert final[1] == {"completed": 4, "skipped": 0, "failed": 0}
    assert final[2] == 4
    assert final[3] == 4.0
