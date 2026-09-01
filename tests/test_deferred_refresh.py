"""Regression tests for short-lived URL refresh and stable resume state."""

from __future__ import annotations

from bs4 import BeautifulSoup

import src.downloaders.thread_downloader as thread_module
import src.resolvers as resolvers
from src.config import FailReason, TaskResult
from src.downloaders.media_downloader import DownloadOutcome
from src.downloaders.thread_downloader import ThreadDownloader, ThreadOptions
from src.resolvers import ResolvedMedia, refresh_media, resolve


class _Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


class _Session:
    def __init__(self):
        self.posts = 0
        self.gets = 0

    def post(self, _url, json=None, **_kwargs):
        self.posts += 1
        slug = (json or {}).get("file_slug", "")
        return _Response(
            {
                "success": True,
                "file": f"{slug}.zip",
                "name": "Fresh archive.zip",
                "server": "https://fsc2.cdn.cr",
                "token": f"token-{self.posts}",
            }
        )

    def get(self, url, **_kwargs):
        self.gets += 1
        if "/api/sign" in url:
            return _Response(
                {
                    "success": True,
                    "url": f"https://dl100.turbocdn.st/video.mov?token={self.gets}",
                    "original_filename": "Fresh video.mov",
                }
            )
        return _Response({}, status=404)


class _Client:
    timeout = 30

    def __init__(self):
        self.session = _Session()


def test_filester_token_is_created_only_when_worker_refreshes():
    client = _Client()
    queued = resolve("https://filester.me/d/ABC123", client)

    assert len(queued) == 1
    assert queued[0].resolver == "filester"
    assert queued[0].state_key == "https://filester.me/d/ABC123"
    assert client.session.posts == 0

    fresh = refresh_media(queued[0], client)
    assert fresh is not None
    assert client.session.posts == 1
    assert fresh.filename == "Fresh archive.zip"
    assert "token=token-1" in fresh.url
    assert fresh.state_key == queued[0].state_key


def test_turbo_signing_is_deferred_and_repeatable():
    client = _Client()
    queued = resolve("https://turbo.cr/v/VIDEO1", client)

    assert queued[0].resolver == "turbo"
    assert client.session.gets == 0
    first = refresh_media(queued[0], client)
    second = refresh_media(queued[0], client)

    assert first is not None and second is not None
    assert first.url != second.url
    assert client.session.gets == 2


def test_turbo_album_preserves_video_cover_without_signing(monkeypatch):
    soup = BeautifulSoup('<h1>Album</h1><a href="/v/abc"><img data-src="/cover.jpg"></a>', "html.parser")
    monkeypatch.setattr(resolvers, "_soup_of", lambda *_args: soup)
    client = _Client()
    queued = resolve("https://turbo.cr/a/album", client)
    assert len(queued) == 1
    assert queued[0].thumbnail_url == "https://turbo.cr/cover.jpg"
    assert client.session.gets == 0


class _Manager:
    def add_task(self, *_args, **_kwargs):
        return 1

    def update_task(self, *_args, **_kwargs):
        pass

    def update_summary(self, *_args, **_kwargs):
        pass

    def update_log(self, **_kwargs):
        pass


def _bare_thread_downloader() -> ThreadDownloader:
    downloader = ThreadDownloader.__new__(ThreadDownloader)
    downloader.options = ThreadOptions(workers=1, delay=99)
    downloader.live_manager = _Manager()
    downloader.client = object()
    return downloader


def test_completed_legacy_state_skips_before_queue_delay(tmp_path, monkeypatch):
    downloader = _bare_thread_downloader()

    class _NeverDownload:
        def download(self, *_args, **_kwargs):
            raise AssertionError("completed item reached downloader")

    downloader.downloader = _NeverDownload()
    monkeypatch.setattr(
        thread_module.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("delay ran before cache")),
    )
    media = ResolvedMedia(url="https://host/already.jpg", filename="already.jpg")

    assert not downloader._run_downloads(
        [(media, tmp_path)],
        {media.url: "completed"},
        tmp_path,
    )


def test_failed_renewable_download_gets_a_new_url(tmp_path, monkeypatch):
    downloader = _bare_thread_downloader()
    downloader.options.delay = 0
    source = "https://filester.me/d/RETRY"
    media = ResolvedMedia(
        url=source,
        filename="placeholder",
        source_url=source,
        resolver="filester",
    )
    refreshes = []

    def _refresh(original, _client):
        refreshes.append(original.state_key)
        return ResolvedMedia(
            url=f"https://fsc2.cdn.cr/file.zip?token={len(refreshes)}",
            filename="file.zip",
            source_url=source,
            resolver="filester",
        )

    target = tmp_path / "file.zip"

    class _Downloader:
        def __init__(self):
            self.calls = 0

        def download(self, _media, _folder, _index):
            self.calls += 1
            if self.calls == 1:
                return DownloadOutcome(
                    TaskResult.FAILED,
                    FailReason.HTTP_ERROR,
                    message="HTTP 403",
                )
            target.write_bytes(b"ok")
            return DownloadOutcome(TaskResult.COMPLETED, path=target)

    downloader.downloader = _Downloader()
    monkeypatch.setattr(thread_module, "refresh_media", _refresh)
    state = {}

    assert not downloader._run_downloads([(media, tmp_path)], state, tmp_path)
    assert len(refreshes) == 2
    assert state[source]["status"] == "completed"
    assert state[source]["size"] == 2


def test_fileditch_equivalent_is_counted_as_redundant_mirror(tmp_path):
    downloader = _bare_thread_downloader()
    downloader.options.delay = 0

    class _NeverDownload:
        def download(self, *_args, **_kwargs):
            raise AssertionError("redundant Fileditch mirror reached the network")

    downloader.downloader = _NeverDownload()
    existing = (
        tmp_path
        / "filester"
        / "Photos"
        / "Qiandai以宇 - Undressing Collection (All Parts).zip"
    )
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"complete archive")
    source = (
        "https://fileditchfiles.st/beta21/hash/"
        "Qiandai%E4%BB%A5%E5%AE%87_-_Undressing_Collection_%28All_Parts%29.zip"
    )
    media = ResolvedMedia(
        url=source,
        filename="Qiandai以宇_-_Undressing_Collection_(All_Parts).zip",
    )
    state = {}

    assert not downloader._run_downloads([(media, tmp_path)], state, tmp_path)
    assert state[source]["status"] == "completed"
    assert state[source]["path"] == existing.relative_to(tmp_path).as_posix()


def test_truncated_fileditch_name_matches_long_common_suffix():
    assert ThreadDownloader._mirror_names_equivalent(
        "06...andai以宇_-_Rabbit_Hole_Miku_Cosplay_Videos.zip",
        "Qiandai以宇 - Rabbit Hole Miku Cosplay Videos.zip",
    )
    assert not ThreadDownloader._mirror_names_equivalent(
        "unrelated archive.zip",
        "Qiandai以宇 - Rabbit Hole Miku Cosplay Videos.zip",
    )
