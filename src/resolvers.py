"""Resolve host page URLs into direct downloadable media URLs.

Python port of the `resolvers` array in ForumPostDownloader's main.js. Each
resolver takes a URL plus an HttpClient and returns a list of ResolvedMedia.

Resolvers are matched in order; the first whose pattern matches wins. Anything
unmatched falls through to `_resolve_direct`, which treats the URL as a direct
link when it already points at a media file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlencode

from bs4 import BeautifulSoup

from src.config import (
    ARCHIVE_EXTENSIONS,
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    USER_AGENT,
    VIDEO_EXTENSIONS,
)
from src.file_utils import filename_from_url, sanitize_name
from src.http_client import HttpClient

MEDIA_EXTENSIONS = (
    IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + AUDIO_EXTENSIONS + ARCHIVE_EXTENSIONS
)


@dataclass
class ResolvedMedia:
    """A concrete file to download."""

    url: str
    filename: str
    subfolder: str = ""
    headers: dict[str, str] | None = None


def is_direct_media(url: str) -> bool:
    """Whether the URL already points at a media file."""
    path = urlparse(url).path.lower()
    return path.endswith(MEDIA_EXTENSIONS)


def _soup_of(client: HttpClient, url: str) -> BeautifulSoup:
    return client.get_soup(url)


def _meta_content(soup: BeautifulSoup, *properties: str) -> str | None:
    for prop in properties:
        node = soup.find("meta", attrs={"property": prop}) or soup.find(
            "meta", attrs={"name": prop},
        )
        if node and node.get("content"):
            return node["content"]
    return None


# --- Individual resolvers ----------------------------------------------------


def _resolve_direct(url: str, _client: HttpClient) -> list[ResolvedMedia]:
    """Treat the URL as an already-direct media link."""
    if not is_direct_media(url):
        return []
    return [ResolvedMedia(url=url, filename=filename_from_url(url))]


def _resolve_nitter(url: str, _client: HttpClient) -> list[ResolvedMedia]:
    """Rewrite nitter proxy image URLs back to pbs.twimg.com."""
    rewritten = re.sub(
        r"https?://nitter\.[^/]+/pic/(orig/)?media%2F(.+)",
        r"https://pbs.twimg.com/media/\2",
        url,
        flags=re.IGNORECASE,
    )
    return [ResolvedMedia(url=rewritten, filename=filename_from_url(rewritten))]


def _resolve_imagevenue(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """Follow the interstitial page to the full-size image."""
    soup = _soup_of(client, url)
    node = soup.select_one(".col-md-12 > a > img") or soup.select_one("#main-image")
    if node is None or not node.get("src"):
        return []
    src = urljoin(url, node["src"])
    return [ResolvedMedia(url=src, filename=filename_from_url(src))]


def _resolve_meta_image(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """Generic image-host resolver via og:image / twitter:image."""
    soup = _soup_of(client, url)
    src = _meta_content(soup, "og:image", "twitter:image")

    if not src:
        node = (
            soup.select_one("#image-viewer-container img")
            or soup.select_one(".image-viewer img")
            or soup.select_one("img.centred")
            or soup.select_one("link[rel='image_src']")
        )
        if node is not None:
            src = node.get("src") or node.get("href")

    if not src:
        return []

    src = urljoin(url, src)
    src = re.sub(r"\.md(\.[a-z0-9]{2,4})$", r"\1", src)  # strip thumbnail marker
    src = re.sub(r"\.th(\.[a-z0-9]{2,4})$", r"\1", src)
    return [ResolvedMedia(url=src, filename=filename_from_url(src))]


def _resolve_postimg(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """postimg.cc single image."""
    soup = _soup_of(client, url)
    node = soup.select_one("#main-image") or soup.select_one("a#download")
    src = None
    if node is not None:
        src = node.get("src") or node.get("href")
    if not src:
        src = _meta_content(soup, "og:image")
    if not src:
        return []
    src = urljoin(url, src).split("?")[0]
    return [ResolvedMedia(url=src, filename=filename_from_url(src))]


def _resolve_pixhost(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """pixhost.to thumbnails map directly to the image server."""
    if "/thumbs/" in url or re.match(r"https?://t\d*\.pixhost\.to/", url):
        direct = url.replace("/thumbs/", "/images/")
        direct = re.sub(r"https?://t(\d*)\.pixhost\.to", r"https://img\1.pixhost.to", direct)
        return [
            ResolvedMedia(
                url=direct,
                filename=filename_from_url(direct),
                headers={"Referer": "https://pixhost.to/"},
            ),
        ]
    return _resolve_meta_image(url, client)


def _resolve_imgbox(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """imgbox thumbnails and single pages."""
    if re.match(r"https?://(thumbs|images)\d*\.imgbox\.com/", url):
        direct = re.sub(r"https?://thumbs(\d*)\.imgbox\.com", r"https://images\1.imgbox.com", url)
        direct = direct.replace("_t.", "_o.")
        return [ResolvedMedia(url=direct, filename=filename_from_url(direct))]
    return _resolve_meta_image(url, client)


def _resolve_gallery(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """Generic album page: collect item links, then resolve each one."""
    soup = _soup_of(client, url)
    folder = sanitize_name(
        (soup.select_one("h1") or soup.select_one("title")).get_text(strip=True)
        if (soup.select_one("h1") or soup.select_one("title"))
        else "album",
    )

    candidates: list[str] = []
    for anchor in soup.select("a[href]"):
        href = urljoin(url, anchor["href"])
        if is_direct_media(href):
            candidates.append(href)

    for img in soup.select("img[src]"):
        src = urljoin(url, img["src"])
        src = re.sub(r"\.(md|th)(\.[a-z0-9]{2,4})$", r"\2", src)
        if is_direct_media(src):
            candidates.append(src)

    seen: set[str] = set()
    resolved: list[ResolvedMedia] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(
            ResolvedMedia(
                url=candidate,
                filename=filename_from_url(candidate),
                subfolder=folder,
            ),
        )
    return resolved


def _resolve_bunkr(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """bunkr file (/f/) or album (/a/) pages -> signed CDN URLs.

    bunkr does not expose a direct media link in markup. The download button
    carries a numeric data-id; the real URL is minted at click time via
    POST /api/_001_v2 (returns mediafiles + path) and then signed through
    https://glb-apisign.cdn.cr/sign?path=... (returns token + ex). We replicate
    that flow here; the resolved URL is a real binary, not the HTML interstitial.
    """
    match = re.search(r"bunkr+(\.[a-z]{2,6})/(a|v|f|d)/([\w\-]+)", url, re.IGNORECASE)
    if not match:
        # already-direct CDN link (e.g. cdn*.bunkr or i*.bunkr)
        if is_direct_media(url) and re.search(r"(cdn|i)\d*\.bunkr", url, re.IGNORECASE):
            return [ResolvedMedia(url=url, filename=filename_from_url(url),
                                  headers={"Referer": "https://bunkr.site/"})]
        return []

    kind, slug = match.group(2), match.group(3)
    origin = f"https://bunkr{match.group(1)}"

    def _sign_one(file_id: str, folder: str) -> list[ResolvedMedia]:
        # Metadata API lives on dl.bunkr.cr regardless of which host served the
        # page (bunkr.cr / bunkr.ph both 404 on their own origin's /api/_001_v2).
        try:
            meta = client.session.post(
                "https://dl.bunkr.cr/api/_001_v2",
                json={"id": file_id},
                headers={"Content-Type": "application/json", "Referer": "https://bunkr.site/"},
                timeout=client.timeout,
            ).json()
            if not isinstance(meta, dict):
                return []
        except (*requests_exceptions(), KeyError, ValueError):
            return []
        mediafiles = meta.get("mediafiles")
        path = meta.get("path")
        if not mediafiles or not path:
            return []
        raw = mediafiles.rstrip("/") + "/" + path.lstrip("/")
        from urllib.parse import quote
        try:
            sign = client.session.get(
                "https://glb-apisign.cdn.cr/sign?path=" + quote(path, safe=""),
                timeout=client.timeout,
            ).json()
        except (*requests_exceptions(), KeyError, ValueError):
            return []
        token = sign.get("token")
        ex = sign.get("ex")
        if not token or not ex:
            return []
        signed = f"{raw}?token={token}&ex={ex}"
        original = meta.get("original")
        if original:
            signed += "&n=" + quote(original)
        return [
            ResolvedMedia(
                url=signed,
                filename=sanitize_name(original) or filename_from_url(signed),
                subfolder=folder,
                headers={"Referer": "https://bunkr.site/"},
            ),
        ]

    if kind == "a":
        soup = _soup_of(client, url)
        folder = sanitize_name(
            soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else "album",
        )
        items: list[ResolvedMedia] = []
        seen: set[str] = set()
        for anchor in soup.select('a[href*="/f/"], a[href*="/v/"], a[href*="/d/"]'):
            item_url = urljoin(url, anchor["href"])
            m = re.search(r"/(f|v|d)/([\w\-]+)", item_url)
            if not m:
                continue
            # each album item is a file page; extract its numeric id
            page = _soup_of(client, item_url)
            btn = page.select_one("#download-btn[data-id]")
            nums = re.findall(r"/file/(\d+)", str(page))
            file_id = btn.get("data-id") if btn else (nums[0] if nums else m.group(2))
            for media in _sign_one(file_id, folder):
                if media.url in seen:
                    continue
                seen.add(media.url)
                items.append(media)
        return items

    # single file page: numeric id lives in /file/<digits> (data-id absent on
    # the lightweight page); fall back to the slug if nothing matches.
    soup = _soup_of(client, url)
    btn = soup.select_one("#download-btn[data-id]")
    nums = re.findall(r"/file/(\d+)", str(soup))
    file_id = btn.get("data-id") if btn else (nums[0] if nums else slug)
    return _sign_one(file_id, "bunkr")


def _resolve_cyberdrop(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """cyberdrop album/file pages."""
    if re.search(r"fs-\d+\.cyberdrop", url):
        return [ResolvedMedia(url=url, filename=filename_from_url(url))]

    soup = _soup_of(client, url)

    if "/a/" in url:
        folder = sanitize_name(
            soup.select_one("h1#title").get_text(strip=True)
            if soup.select_one("h1#title")
            else "album",
        )
        items: list[ResolvedMedia] = []
        for anchor in soup.select("a.image[href]"):
            item_url = urljoin(url, anchor["href"])
            for media in _resolve_cyberdrop(item_url, client):
                media.subfolder = folder
                items.append(media)
        return items

    node = soup.select_one("#file[href], a#downloadBtn[href], video source[src]")
    src = node.get("href") or node.get("src") if node else _meta_content(soup, "og:image")
    if not src:
        return []
    src = urljoin(url, src)
    return [ResolvedMedia(url=src, filename=filename_from_url(src))]


def _resolve_pixeldrain(url: str, _client: HttpClient) -> list[ResolvedMedia]:
    """pixeldrain uses a stable API path."""
    match = re.search(r"pixeldrain\.com/([lu])/(\w+)", url)
    if not match:
        return []
    kind, file_id = match.groups()
    if kind == "u":
        return [
            ResolvedMedia(
                url=f"https://pixeldrain.com/api/file/{file_id}?download",
                filename=file_id,
            ),
        ]
    return [
        ResolvedMedia(
            url=f"https://pixeldrain.com/api/list/{file_id}/zip",
            filename=f"{file_id}.zip",
        ),
    ]


def _resolve_erome(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """erome albums expose direct media in the markup."""
    soup = _soup_of(client, url)
    title = soup.select_one("h1, .col-sm-12 h1")
    folder = sanitize_name(title.get_text(strip=True) if title else "erome")

    items: list[ResolvedMedia] = []
    seen: set[str] = set()
    for node in soup.select("div.media-group img[data-src], div.media-group source[src]"):
        src = node.get("data-src") or node.get("src")
        if not src:
            continue
        src = urljoin(url, src)
        if src in seen:
            continue
        seen.add(src)
        items.append(
            ResolvedMedia(
                url=src,
                filename=filename_from_url(src),
                subfolder=folder,
                headers={"Referer": "https://www.erome.com/"},
            ),
        )
    return items


def _resolve_filester(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """filester.me folder (/f/) or file (/d/) pages.

    The page is an SPA: a folder's file list lives in plain markup, but each
    file's CDN URL is minted per-request via POST /v2/api/public/download with
    the file slug (mirrors js/file_dl.js). We replicate that flow here.
    """
    match = re.search(r"filester\.me/(?:f|d)/([\w\-]+)", url)
    if not match:
        return []
    kind, slug = match.group(0).split("/")[1], match.group(1)

    folder = "filester"
    slugs: list[tuple[str, str]] = []  # (slug, display_name)

    if kind == "f":
        soup = _soup_of(client, url)
        folder_node = soup.select_one("h1, title")
        folder = sanitize_name(
            folder_node.get_text(strip=True) if folder_node else "filester",
        )
        for item in soup.select("div.file-item"):
            onclick = item.get("onclick", "")
            m = re.search(r"href=['\"]?(/d/[\w\-]+)", onclick)
            if not m:
                continue
            slugs.append((m.group(1).split("/")[-1], item.get("data-name", "")))
    else:
        slugs.append((slug, ""))

    if not slugs:
        return []

    headers = {
        "Content-Type": "application/json",
        "Referer": "https://filester.me/",
    }
    items: list[ResolvedMedia] = []
    seen: set[str] = set()

    for fslug, fname in slugs:
        try:
            resp = client.session.post(
                "https://filester.me/v2/api/public/download",
                json={"file_slug": fslug},
                headers=headers,
                timeout=client.timeout,
            ).json()
        except (*requests_exceptions(), KeyError, ValueError):
            continue

        if not resp.get("success") or not resp.get("file") or not resp.get("token"):
            continue

        server = resp.get("server") or "https://p1.filester.me"
        name = resp.get("name") or fname
        query = {"token": resp["token"], "download": "true"}
        if name:
            query["n"] = name
        direct = f"{server}/v2/{resp['file']}?{urlencode(query)}"

        if direct in seen:
            continue
        seen.add(direct)
        items.append(
            ResolvedMedia(
                url=direct,
                filename=sanitize_name(name) or filename_from_url(direct),
                subfolder=folder,
                headers={"Referer": "https://filester.me/"},
            ),
        )
    return items


def _resolve_gofile(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """gofile needs a guest token plus an API call."""
    match = re.search(r"gofile\.io/d/(\w+)", url)
    if not match:
        return []
    content_id = match.group(1)

    try:
        account = client.session.post(
            "https://api.gofile.io/accounts",
            timeout=client.timeout,
        ).json()
        token = account["data"]["token"]

        response = client.session.get(
            f"https://api.gofile.io/contents/{content_id}",
            params={"wt": "4fd6sg89d7s6"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=client.timeout,
        ).json()
    except (*requests_exceptions(), KeyError, json.JSONDecodeError):
        return []

    data = response.get("data", {})
    folder = sanitize_name(data.get("name", content_id))
    children = data.get("children", {}) or {}

    items: list[ResolvedMedia] = []
    for child in children.values():
        if child.get("type") != "file" or not child.get("link"):
            continue
        items.append(
            ResolvedMedia(
                url=child["link"],
                filename=sanitize_name(child.get("name", "")) or filename_from_url(child["link"]),
                subfolder=folder,
                headers={"Cookie": f"accountToken={token}", "Referer": "https://gofile.io/"},
            ),
        )
    return items


def _resolve_redgifs(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """redgifs exposes an public API for HD mp4s."""
    match = re.search(r"redgifs\.com/(?:ifr|watch)/(\w+)", url, re.IGNORECASE)
    if not match:
        return []
    gif_id = match.group(1).lower()

    try:
        auth = client.get_json("https://api.redgifs.com/v2/auth/temporary")
        token = auth.get("token")
        response = client.session.get(
            f"https://api.redgifs.com/v2/gifs/{gif_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=client.timeout,
        ).json()
    except (*requests_exceptions(), KeyError, json.JSONDecodeError):
        return []

    urls = response.get("gif", {}).get("urls", {})
    src = urls.get("hd") or urls.get("sd")
    if not src:
        return []
    return [
        ResolvedMedia(
            url=src,
            filename=f"{gif_id}.mp4",
            headers={"Referer": "https://www.redgifs.com/"},
        ),
    ]


def _resolve_saint(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """saint.to embed pages carry a <source> tag."""
    soup = _soup_of(client, url)
    node = soup.select_one("video source[src], source[src]")
    src = node.get("src") if node else _meta_content(soup, "og:video")
    if not src:
        return []
    src = urljoin(url, src)
    return [
        ResolvedMedia(
            url=src,
            filename=filename_from_url(src),
            headers={"Referer": url},
        ),
    ]


def _resolve_imgur(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """imgur direct links and single pages."""
    if re.match(r"https?://i\.imgur\.(com|io)/", url):
        return [ResolvedMedia(url=url, filename=filename_from_url(url))]
    return _resolve_meta_image(url, client)


def _resolve_turbo(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """turbo.cr embed pages hand the real file to a signed URL via /api/sign.

    The embed page runs `fetch('/api/sign?v=<id>')` and gets back JSON with a
    time-limited `url` (token + exp params on turbocdn.st). We replicate that so
    the downloader can grab the mp4 directly.
    """
    match = re.search(r"turbo\.cr/(?:embed/)?([\w\-]+)", url)
    if not match:
        return []
    video_id = match.group(1)

    try:
        resp = client.session.get(
            f"https://turbo.cr/api/sign?v={video_id}",
            headers={
                "User-Agent": USER_AGENT,
                "Referer": f"https://turbo.cr/embed/{video_id}",
                "Accept": "application/json",
            },
            timeout=client.timeout,
        ).json()
    except (*requests_exceptions(), json.JSONDecodeError):
        return []

    signed = resp.get("url")
    if not signed or not resp.get("success"):
        return []

    return [
        ResolvedMedia(
            url=signed,
            filename=resp.get("filename") or f"{video_id}.mp4",
            headers={"Referer": "https://turbo.cr/"},
        ),
    ]


def _resolve_goodbox(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """goonbox.cr image/album host (common on SimpCity).

    Mirrors ForumPostDownloader: /img/<id> -> GET /api/images/<id> (JSON with
    image.original_url); /a/<slug> -> paginated /api/albums/<slug>/images.
    """
    if "/a/" in url:
        match = re.search(r"goonbox\.cr/a/([\w\-]+)", url)
        if not match:
            return []
        slug = match.group(1)
        items: list[ResolvedMedia] = []
        seen: set[str] = set()
        page = 1
        while True:
            try:
                resp = client.session.get(
                    f"https://goonbox.cr/api/albums/{slug}/images",
                    params={"page": page},
                    headers={"Referer": url, "Accept": "application/json"},
                    timeout=client.timeout,
                ).json()
            except (*requests_exceptions(), json.JSONDecodeError):
                break
            imgs = (resp.get("images") or []) if isinstance(resp, dict) else []
            if not imgs:
                break
            for img in imgs:
                src = img.get("original_url") or img.get("url")
                if src and src not in seen:
                    seen.add(src)
                    items.append(
                        ResolvedMedia(
                            url=src,
                            filename=filename_from_url(src),
                            subfolder=f"goonbox_{slug}",
                        )
                    )
            last = (resp.get("pagination") or {}).get("last_page")
            if not last or page >= int(last):
                break
            page += 1
        return items

    match = re.search(r"goonbox\.cr/img/([\w\-]+)", url)
    if not match:
        return []
    img_id = match.group(1)
    try:
        resp = client.session.get(
            f"https://goonbox.cr/api/images/{img_id}",
            headers={"Referer": url, "Accept": "application/json"},
            timeout=client.timeout,
        ).json()
    except (*requests_exceptions(), json.JSONDecodeError):
        return []
    src = (resp.get("image") or {}).get("original_url") or resp.get("original_url")
    if not src:
        return []
    return [ResolvedMedia(url=src, filename=filename_from_url(src))]


def _resolve_box(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """box.com shared file links.

    The public share page redirects to a download URL; the final URL carries
    the real file. Mirrors ForumPostDownloader's @connect box.com / boxcloud.com.
    """
    try:
        resp = client.session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=client.timeout,
            allow_redirects=True,
        )
    except requests_exceptions():
        return []
    final = resp.url
    # Box serves the file via a /download URL or a content-disposition; prefer final.
    if any(final.lower().endswith(ext) for ext in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + ARCHIVE_EXTENSIONS):
        return [ResolvedMedia(url=final, filename=filename_from_url(final))]
    # Try the explicit download endpoint.
    dl = url.rstrip("/") + "/download"
    try:
        r2 = client.session.head(dl, headers={"User-Agent": USER_AGENT}, timeout=client.timeout, allow_redirects=True)
        if r2.status_code < 400 and "content-disposition" in r2.headers:
            return [ResolvedMedia(url=r2.url, filename=filename_from_url(r2.url))]
    except requests_exceptions():
        pass
    return []


def _resolve_pomf2(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """pomf2.lain.la and similar pomf clones — direct file host.

    The /f/<id> or /<id> page exposes the real file at /data/<id>.ext or via a
    download link. Fall back to treating the URL itself if it ends in an ext.
    """
    try:
        resp = client.session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=client.timeout,
            allow_redirects=True,
        )
    except requests_exceptions():
        return []
    final = resp.url
    if any(final.lower().endswith(ext) for ext in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + ARCHIVE_EXTENSIONS):
        return [ResolvedMedia(url=final, filename=filename_from_url(final))]
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if any(h.lower().endswith(ext) for ext in IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + ARCHIVE_EXTENSIONS):
            full = h if h.startswith("http") else urljoin(url, h)
            return [ResolvedMedia(url=full, filename=filename_from_url(full))]
    return []


def requests_exceptions():  # noqa: ANN201
    """Lazy import to keep the exception tuple in one place."""
    import requests

    return (requests.RequestException, ValueError)


# --- Registry ----------------------------------------------------------------

RESOLVERS: list[tuple[str, object]] = [
    (r"nitter\.[^/]+/pic/", _resolve_nitter),
    (r"imagevenue\.com", _resolve_imagevenue),
    (r"(cdn|i|stream)\d*\.bunkr|bunkrr?\.|bunkrrr\.org|bunkr-cache\.se|apidl\.bunkr\.ru|get\.bunkrr\.su|bunkr\.(ac|ax|black|cat|ci|cr|fi|is|media|nu|red|ru|se|si|site|pk|ph|ps|sk|ws)", _resolve_bunkr),
    (r"cyberdrop\.(me|to|cc|nl|cloud|ch|cr)|fs-\d+\.cyberdrop|cyberfile\.(su|me)", _resolve_cyberdrop),
    (r"pixeldrain\.com/[lu]/", _resolve_pixeldrain),
    (r"erome\.com/a/", _resolve_erome),
    (r"filester\.(me|sh|si|gg)/(f|d)/", _resolve_filester),
    (r"gofile\.io/d/", _resolve_gofile),
    (r"redgifs\.com/(ifr|watch)/", _resolve_redgifs),
    (r"saint\d?\.(to|su|pk|cr)", _resolve_saint),
    (r"imgur\.(com|io)", _resolve_imgur),
    (r"turbo\.cr/(?:embed/)?[\w\-]+|turbocdn\.st", _resolve_turbo),
    (r"goonbox\.cr/(?:img|a)/", _resolve_goodbox),
    (r"(postimg|pixxxels)\.cc", _resolve_postimg),
    (r"pixhost\.to", _resolve_pixhost),
    (r"imgbox\.com", _resolve_imgbox),
    (r"ibb\.co/album/|jpg\d?\.\w+/a/|jpg\d?\.(fish|fishing|pet|su|homes|church)/a/|pixl\.(li|is)/album/|img\.kiwi/album/", _resolve_gallery),
    (r"ibb\.co|jpg\d?\.(church|fish|fishing|pet|su|homes)|pixl\.(li|is)|img\.kiwi|imagebam\.com",
     _resolve_meta_image),
    (r"box\.com|boxcloud\.com", _resolve_box),
    (r"pomf2?\.lain\.la|pomf\.lain\.la", _resolve_pomf2),
    (r"coomer\.(st|party|su)|kemono\.(cr|su|party)", _resolve_direct),
    (r"cuckcapital\.cr|scdn\.st|cache8\.st|cdn\.cr|simp\d?\.cuckcapital\.cr", _resolve_direct),
    (r"onlyfans\.com|pbs\.twimg\.com|media\.tumblr\.com|reddit\.com|twitter\.com", _resolve_direct),
    (r"pornhub\.com|spankbang\.com|sb-cd\.com|xvideos\.com|rule34\.xxx|noodlemagazine\.com|pvvstream\.pro", _resolve_direct),
]


def resolve(url: str, client: HttpClient) -> list[ResolvedMedia]:
    """Resolve a single host URL into concrete downloadable media."""
    for pattern, resolver in RESOLVERS:
        if re.search(pattern, url, re.IGNORECASE):
            try:
                resolved = resolver(url, client)  # type: ignore[operator]
            except Exception:  # noqa: BLE001 - a broken host must not kill the run
                resolved = []
            if resolved:
                return resolved
            break

    return _resolve_direct(url, client)
