"""A small requests wrapper with retries, cookies and forum-friendly headers."""

from __future__ import annotations

import time
from http.cookiejar import LoadError, MozillaCookieJar
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.config import HTTP_TIMEOUT, RETRY_BACKOFF, USER_AGENT, RATE_429_BACKOFF


def _consume_retry_after(response: requests.Response | None) -> bool:
    """Sleep the server's ``Retry-After`` (seconds) if present; return True if we did.

    Used for 429/503 so we honour the CDN's own backoff window instead of our
    fixed exponential curve. Caps at 60s to avoid an absurd server value.
    """
    if response is None:
        return False
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return False
    try:
        time.sleep(min(int(retry_after), 60))
        return True
    except (TypeError, ValueError):
        return False


class HttpClient:
    """Thin session wrapper: GET html/json/bytes with bounded retries."""

    def __init__(
        self,
        cookies_file: str | None = None,
        user_agent: str = USER_AGENT,
        timeout: int = HTTP_TIMEOUT,
        max_retries: int = 3,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        self.timeout = timeout
        self.max_retries = max_retries

        if cookies_file:
            self.load_cookies(cookies_file)

    def load_cookies(self, cookies_file: str) -> None:
        """Load a Netscape-format cookies.txt (for login-gated forums).

        Session cookies exported from a browser carry `expires=0`, which
        http.cookiejar treats as *already expired*: `ignore_expires` only
        applies during load(), so copying such a cookie straight into the
        session makes requests silently drop it and every gated page comes
        back 403. Non-expiring cookies are therefore given a far-future
        expiry before being handed to the session.
        """
        path = Path(cookies_file)
        if not path.exists():
            msg = f"Cookies file not found: {cookies_file}"
            raise FileNotFoundError(msg)

        jar = MozillaCookieJar(str(path))
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
        except LoadError as error:
            msg = (
                f"Could not parse '{cookies_file}' as a Netscape cookies.txt "
                f"(fields must be TAB-separated): {error}"
            )
            raise ValueError(msg) from error

        far_future = int(time.time()) + 10 * 365 * 24 * 3600
        loaded = 0
        for cookie in jar:
            if not cookie.expires:
                cookie.expires = far_future
            cookie.discard = False
            self.session.cookies.set_cookie(cookie)
            loaded += 1

        if loaded == 0:
            msg = (
                f"No cookies found in '{cookies_file}'. Export it in "
                f"Netscape format with TAB-separated fields."
            )
            raise ValueError(msg)

    def get(self, url: str, **kwargs) -> requests.Response:  # noqa: ANN003
        """GET with retry/backoff on transient failures.

        HTTP 429 (Too Many Requests) gets special treatment: the server is
        rate-limiting us, so we back off *longer* than for a generic 5xx and
        honour its ``Retry-After`` header when present. CDNs like SimpCity's
        c3wi-b.cdn.cr emit 429 without Retry-After, so we fall back to an
        exponential backoff (RATE_429_BACKOFF ** attempt) capped at 60s.
        """
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("allow_redirects", True)

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, **kwargs)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}",
                        response=response,
                    )
            except requests.HTTPError as error:
                # Server returned a retryable status. Sleep by status, then retry.
                last_error = error
                status = getattr(error.response, "status_code", None)
                if attempt < self.max_retries - 1:
                    if status == 429:
                        waited = _consume_retry_after(error.response)
                        if not waited:
                            time.sleep(min(RATE_429_BACKOFF ** (attempt + 1), 60))
                    elif status == 503:
                        waited = _consume_retry_after(error.response)
                        if not waited:
                            time.sleep(RETRY_BACKOFF ** min(attempt, 4))
                    else:
                        time.sleep(RETRY_BACKOFF ** min(attempt, 4))
                continue
            except requests.RequestException as error:
                # Connection drop / timeout: short backoff.
                last_error = error
                if attempt < self.max_retries - 1:
                    time.sleep(RETRY_BACKOFF ** min(attempt, 4))
                continue
            else:
                return response

        msg = f"GET failed after {self.max_retries} attempts: {url} ({last_error})"
        raise requests.RequestException(msg)

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup:  # noqa: ANN003
        """GET and parse as HTML."""
        response = self.get(url, **kwargs)
        return BeautifulSoup(response.text, "html.parser")

    def get_json(self, url: str, **kwargs) -> dict:  # noqa: ANN003
        """GET and parse as JSON."""
        response = self.get(url, **kwargs)
        return response.json()

    def head(self, url: str, **kwargs) -> requests.Response:  # noqa: ANN003
        """HEAD request (used for size / range probing)."""
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("allow_redirects", True)
        return self.session.head(url, **kwargs)

    def close(self) -> None:
        """Close the underlying session."""
        self.session.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
