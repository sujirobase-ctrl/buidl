"""Offline tests for the bunkr resolver (_resolve_bunkr).

Mocks HttpClient so no network is touched. Locks the sign flow:
  page HTML -> numeric id -> POST /api/_001_v2 -> GET sign -> signed CDN URL.
"""
from __future__ import annotations

import sys
import os
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from src.resolvers import _resolve_bunkr

FILE_PAGE = (
    '<html><body>'
    '<a id="download-btn" href="#" data-id="33864542">Download</a>'
    '<script>var x = "/file/33864542";</script>'
    '</body></html>'
)
ALBUM_PAGE = (
    '<html><body><h1>My Album</h1>'
    '<a href="/f/AAAA1111"></a><a href="/f/BBBB2222"></a>'
    '</body></html>'
)
FILE_A = '<html><body><script>var x = "/file/11111111";</script></body></html>'
FILE_B = '<html><body><script>var x = "/file/22222222";</script></body></html>'


class _FakeResp:
    def __init__(self, text="", json_data=None):
        self.text = text
        self._json = json_data
    def json(self):
        return self._json


class _FakeSession:
    def __init__(self, by_id, sign_data):
        self._by_id = by_id
        self._sign = sign_data

    def get(self, url, **_):
        if "/a/" in url:
            return _FakeResp(text=ALBUM_PAGE)
        if "/f/AAAA1111" in url:
            return _FakeResp(text=FILE_A)
        if "/f/BBBB2222" in url:
            return _FakeResp(text=FILE_B)
        if "glb-apisign.cdn.cr/sign" in url:
            return _FakeResp(json_data=self._sign)
        return _FakeResp(text=FILE_PAGE)

    def post(self, url, json=None, **_):
        fid = (json or {}).get("id", "")
        return _FakeResp(json_data=self._by_id.get(fid))


class _FakeClient:
    def __init__(self, by_id, sign_data):
        self.session = _FakeSession(by_id, sign_data)
        self.timeout = 30
    def get_soup(self, url):
        if "/a/" in url: return BeautifulSoup(ALBUM_PAGE, "html.parser")
        if "/f/AAAA1111" in url: return BeautifulSoup(FILE_A, "html.parser")
        if "/f/BBBB2222" in url: return BeautifulSoup(FILE_B, "html.parser")
        return BeautifulSoup(FILE_PAGE, "html.parser")


def _meta(mediafiles, path, original):
    return {"mediafiles": mediafiles, "path": path, "original": original}


def test_single_file_page():
    client = _FakeClient(
        {"33864542": _meta("https://c5bu-b.cdn.cr", "/storage/media/x.mp3", "song.mp3")},
        {"token": "tok", "ex": "999"},
    )
    out = _resolve_bunkr("https://bunkr.cr/f/rmQx9qv75gNZa", client)
    assert len(out) == 1, out
    m = out[0]
    assert m.filename == "song.mp3"
    assert m.url.startswith("https://c5bu-b.cdn.cr/storage/media/x.mp3?token=tok&ex=999")
    assert "n=song.mp3" in m.url
    assert m.subfolder == "bunkr"


def test_album_expands_all_items():
    client = _FakeClient(
        {
            "11111111": _meta("https://c1.cdn.cr", "/a.mp3", "A.mp3"),
            "22222222": _meta("https://c2.cdn.cr", "/b.mp4", "B.mp4"),
        },
        {"token": "t", "ex": "1"},
    )
    out = _resolve_bunkr("https://bunkr.cr/a/2geD5FrR", client)
    assert len(out) == 2, out
    names = sorted(m.filename for m in out)
    assert names == ["A.mp3", "B.mp4"], names
    for m in out:
        assert m.subfolder == "My Album"
        assert "token=" in m.url and "ex=" in m.url


def test_failed_meta_returns_empty():
    client = _FakeClient({}, {"token": "t", "ex": "1"})
    # ids 33864542 / 1111.. not in by_id -> post returns {} -> no mediafiles
    assert _resolve_bunkr("https://bunkr.cr/f/rmQx9qv75gNZa", client) == []


if __name__ == "__main__":
    test_single_file_page()
    test_album_expands_all_items()
    test_failed_meta_returns_empty()
    print("bunkr tests — passed 3, failed 0")
