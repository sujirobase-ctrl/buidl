"""Filesystem and naming helpers shared across the package."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.config import (
    CONTENT_TYPE_EXTENSIONS,
    INVALID_CHAR_SUBSTITUTE,
    INVALID_PATH_CHARS,
    MAX_FILENAME_LENGTH,
    STATE_FILENAME,
    URLS_FILE,
)

EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f900-\U0001f9ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\u2600-\u26ff"
    "\u2700-\u27bf"
    "\U0001f1e6-\U0001f1ff"
    "\u2b00-\u2bff"
    "\u2190-\u21ff"
    "\u2300-\u23ff"
    "]+",
    flags=re.UNICODE,
)


def sanitize_name(name: str, *, allow_emojis: bool = False) -> str:
    """Turn arbitrary text into a filesystem-safe folder/file name."""
    if not name:
        return "untitled"

    cleaned = unicodedata.normalize("NFKC", name).strip()
    if not allow_emojis:
        cleaned = EMOJI_PATTERN.sub("", cleaned)

    for char in INVALID_PATH_CHARS:
        cleaned = cleaned.replace(char, INVALID_CHAR_SUBSTITUTE)

    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(rf"{re.escape(INVALID_CHAR_SUBSTITUTE)}{{2,}}", INVALID_CHAR_SUBSTITUTE, cleaned)
    cleaned = cleaned.strip(" .-")
    cleaned = cleaned[:MAX_FILENAME_LENGTH]
    return cleaned or "untitled"


def filename_from_url(url: str, fallback: str = "file") -> str:
    """Derive a filename from a URL path, ignoring the query string."""
    path = urlparse(url).path
    name = unquote(Path(path).name)
    return sanitize_name(name) if name else fallback


def extension_from_content_type(content_type: str | None) -> str:
    """Map a Content-Type header to a file extension."""
    value = (content_type or "").lower()
    for key, extension in CONTENT_TYPE_EXTENSIONS.items():
        if key in value:
            return extension
    return "bin"


def ensure_unique_path(path: Path) -> Path:
    """Return a non-colliding path by appending ' (n)' when needed."""
    if not path.exists():
        return path

    stem, suffix, parent = path.stem, path.suffix, path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def read_urls_file(path: str = URLS_FILE) -> list[str]:
    """Read non-empty, non-comment lines from the URLs file."""
    file_path = Path(path)
    if not file_path.exists():
        return []

    lines = file_path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def write_urls_file(urls: list[str], path: str = URLS_FILE) -> None:
    """Overwrite the URLs file (used to drop processed entries)."""
    Path(path).write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")


def load_state(folder: Path) -> dict:
    """Load the per-folder resume sidecar."""
    state_file = folder / STATE_FILENAME
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(folder: Path, state: dict) -> None:
    """Persist the per-folder resume sidecar."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / STATE_FILENAME).write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def matches_any(patterns: list[str], filename: str) -> bool:
    """Case-insensitive substring match used by --ignore / --include."""
    lowered = filename.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def format_size(num_bytes: float) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"
