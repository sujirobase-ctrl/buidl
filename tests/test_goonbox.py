"""Offline contract tests for the goonbox resolver and host matcher."""

from __future__ import annotations

from src.parsers.host_parser import parse_hosts
from src.resolvers import resolve


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class _Session:
    def get(self, url: str, **kwargs) -> _Response:
        if "/api/images/good" in url:
            return _Response(
                {"image": {"original_url": "https://cdn.example/media/photo.jpg"}},
            )
        if "/api/albums/album/images" in url and kwargs.get("params") == {"page": 1}:
            return _Response(
                {
                    "images": [
                        {"original_url": "https://cdn.example/media/one.jpg"},
                        {"original_url": "https://cdn.example/media/two.png"},
                    ],
                    "pagination": {"last_page": 1},
                },
            )
        return _Response({})


class _Client:
    timeout = 30
    session = _Session()


def test_goonbox_host_is_detected() -> None:
    matches = parse_hosts('<a href="https://goonbox.cr/img/good">x</a>')
    assert any("goonbox.cr" in match.url for match in matches)


def test_goonbox_image_resolves_offline() -> None:
    items = resolve("https://goonbox.cr/img/good", _Client())
    assert len(items) == 1
    assert items[0].filename == "photo.jpg"


def test_goonbox_album_resolves_offline() -> None:
    items = resolve("https://goonbox.cr/a/album", _Client())
    assert {item.filename for item in items} == {"one.jpg", "two.png"}
    assert all(item.subfolder == "goonbox_album" for item in items)


def test_goonbox_unknown_image_is_safe() -> None:
    assert resolve("https://goonbox.cr/img/missing", _Client()) == []
