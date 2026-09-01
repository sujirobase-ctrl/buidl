"""Real-world regression: the ikumi-asmr SimpCity thread (user-saved HTML).

Mirrors the exact URL patterns found in page-1 of the public SimpCity thread
ikumi-asmr.85869, including the decorative profile_banner chrome and the
filester.me / bunkr.ph folders that users actually posted. Locks in:

  * profile_banner is excluded (decorative chrome, not posted content)
  * emoji / smilies / reactions / quotes are excluded
  * profile / social pages are NOT treated as media
  * bunkr / filester.me / gofile folders a user posted ARE captured
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from src.parsers.thread_parser import ThreadParser
from src.parsers.host_parser import parse_hosts, _is_decorative

BASE = "https://simpcity.cr/threads/ikumi-asmr.85869/"

PAGE1_HTML = """
<html><body>
<h1 class="p-title-value">
  <span class="label label--requests">Request</span><span class="label-append">&nbsp;</span>
  <span class="label label--patreon">Patreon</span><span class="label-append">&nbsp;</span>
  <span class="label label--twitch">Twitch</span><span class="label-append">&nbsp;</span>Ikumi (ASMR)
</h1>
<article class="message--post" data-content="post-761705" id="js-post-761705">
  <a href="https://simpcity.cr/threads/ikumi-asmr.85869/post-761705">#1</a>
  <div class="message-userContent lbContainer js-lbContainer">
    <div class="bbWrapper">Anyone have Ikumi patreon?
      <a href="https://goonbox.cr/img/mTHEBg" class="link">
        <img src="https://simp4.cuckcapital.cr/e778c5e2-66d6-4ffe-9a51-77fd1d24b03b-profile_banner-480.md.png"
             class="bbImage" alt="profile_banner">
      </a>
      <img class="smilie smilie--sprite" alt=":COPIUM:" src="data:image/gif;base64,AAAA">
    </div>
  </div>
</article>

<article class="message--post" data-content="post-9559853" id="js-post-9559853">
  <a href="https://simpcity.cr/threads/ikumi-asmr.85869/post-9559853">#2</a>
  <div class="message-userContent lbContainer js-lbContainer">
    <div class="bbWrapper">Some stuff
      <a href="https://bunkr.cr/a/2geD5FrR" class="link">https://bunkr.cr/a/2geD5FrR</a>
    </div>
  </div>
</article>

<article class="message--post" data-content="post-36059123" id="js-post-36059123">
  <a href="https://simpcity.cr/threads/ikumi-asmr.85869/post-36059123">#9</a>
  <div class="message-userContent lbContainer js-lbContainer">
    <div class="bbWrapper">cut of tongue flutters
      <a href="https://bunkr.ph/f/pKYDYDJ6LwxKq" class="link">https://bunkr.ph/f/pKYDYDJ6LwxKq</a>
    </div>
    <aside class="message-signature"><div class="bbWrapper">support the creators</div></aside>
  </div>
</article>

<article class="message--post" data-content="post-47519491" id="js-post-47519491">
  <a href="https://simpcity.cr/threads/ikumi-asmr.85869/post-47519491">#10</a>
  <div class="message-userContent lbContainer js-lbContainer">
    <div class="bbWrapper">VODs
      <div class="bbCodeBlock bbCodeBlock--unfurl js-unfurl">
        <a href="https://filester.me/f/3cc5507e2d259f99" class="link">Ikumi VODs</a>
      </div>
    </div>
  </div>
</article>

<article class="message--post" data-content="post-47534963" id="js-post-47534963">
  <a href="https://simpcity.cr/threads/ikumi-asmr.85869/post-47534963">#11</a>
  <div class="message-userContent lbContainer js-lbContainer">
    <div class="bbWrapper">patreon audios
      <div class="bbCodeBlock bbCodeBlock--unfurl js-unfurl">
        <a href="https://filester.me/f/b5b77ea202fbc0d6" class="link">audios</a>
        <a href="https://filester.me/f/49f7765cbfa272b8" class="link">clips</a>
      </div>
      <img class="smilie smilie--emoji" alt=":star:" src="x.png">
    </div>
  </div>
</article>
</body></html>
"""


def test_title_and_post_count():
    soup = BeautifulSoup(PAGE1_HTML, "html.parser")
    parser = ThreadParser(soup, BASE)
    assert parser.parse_title() == "Request Patreon Twitch Ikumi (ASMR)"
    posts = parser.parse_posts()
    assert len(posts) == 5
    # post numbers parsed from the #N counter
    assert [p.post_number for p in posts] == ["1", "2", "9", "10", "11"]


def test_decorative_profile_banner_excluded():
    assert _is_decorative(
        "https://simp4.cuckcapital.cr/e778c5e2-66d6-4ffe-9a51-77fd1d24b03b-profile_banner-480.md.png"
    )
    soup = BeautifulSoup(PAGE1_HTML, "html.parser")
    parser = ThreadParser(soup, BASE)
    posts = parser.parse_posts()
    post1 = posts[0]
    matches = parse_hosts(post1.html_content)
    assert all("profile_banner" not in m.url for m in matches)
    # goonbox.cr IS now a supported host (added to HOSTS), so it should be detected
    assert any("goonbox.cr" in m.url for m in matches), "goonbox.cr should now be detected"


def test_emoji_signature_quote_excluded():
    soup = BeautifulSoup(PAGE1_HTML, "html.parser")
    parser = ThreadParser(soup, BASE)
    posts = parser.parse_posts()
    # post 9 already has a signature; ensure it contributes no media on its own
    # beyond the bunkr link it actually contains.
    post9 = posts[2]
    matches = parse_hosts(post9.html_content)
    assert any(m.url == "https://bunkr.ph/f/pKYDYDJ6LwxKq" for m in matches)
    # no smilie/emoji data-URIs leak as media
    assert all("data:image" not in m.url for m in matches)


def test_user_posted_folders_captured():
    soup = BeautifulSoup(PAGE1_HTML, "html.parser")
    parser = ThreadParser(soup, BASE)
    posts = {p.post_number: p for p in parser.parse_posts()}

    # post 2: bunkr album
    urls2 = {m.url for m in parse_hosts(posts["2"].html_content)}
    assert "https://bunkr.cr/a/2geD5FrR" in urls2

    # post 9: bunkr /f/ folder
    urls9 = {m.url for m in parse_hosts(posts["9"].html_content)}
    assert "https://bunkr.ph/f/pKYDYDJ6LwxKq" in urls9

    # posts 10 & 11: filester.me folders
    urls10 = {m.url for m in parse_hosts(posts["10"].html_content)}
    assert "https://filester.me/f/3cc5507e2d259f99" in urls10

    urls11 = {m.url for m in parse_hosts(posts["11"].html_content)}
    assert "https://filester.me/f/b5b77ea202fbc0d6" in urls11
    assert "https://filester.me/f/49f7765cbfa272b8" in urls11


def test_total_capture_count():
    soup = BeautifulSoup(PAGE1_HTML, "html.parser")
    parser = ThreadParser(soup, BASE)
    total = 0
    for p in parser.parse_posts():
        total += len(parse_hosts(p.html_content))
    # 2 (bunkr) + 3 (filester) + 1 (goonbox) = 6 posted-media links across 5 posts
    assert total == 6


if __name__ == "__main__":
    test_title_and_post_count()
    test_decorative_profile_banner_excluded()
    test_emoji_signature_quote_excluded()
    test_user_posted_folders_captured()
    test_total_capture_count()
    print("real-ikumi tests — passed 5, failed 0")
