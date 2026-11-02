"""Smoke-test the packaged engine used by the C#/.NET frontend."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.mock_forum import BASE, serve

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "windows-dotnet" / "Buidl.WinUI" / "Engine" / "buidl-engine.exe"


def events_of(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    """Decode the bridge JSON-lines response and surface stderr on failure."""
    if completed.returncode:
        raise RuntimeError(f"engine={completed.returncode}: {completed.stdout}\n{completed.stderr}")
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


def main() -> int:
    """Scan a local thread, then download every image returned by the filter."""
    if not ENGINE.is_file():
        raise FileNotFoundError(f"Build the packaged engine first: {ENGINE}")
    server = serve()
    try:
        with tempfile.TemporaryDirectory(prefix="buidl-dotnet-smoke-") as temporary:
            temp = Path(temporary)
            request_path = temp / "request.json"
            session_path = temp / "session.json"
            output = temp / "downloads"
            request_path.write_text(
                json.dumps(
                    {
                        "url": f"{BASE}/threads/test-thread.123/",
                        "output": str(output),
                        "all_pages": True,
                        "max_pages": 1,
                        "workers": 2,
                        "include": [],
                        "ignore": [],
                        "separate_posts": False,
                        "flat": False,
                    }
                ),
                encoding="utf-8",
            )
            scan = events_of(
                subprocess.run(
                    [str(ENGINE), "scan", "--request", str(request_path), "--session", str(session_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
            )
            result = next(event for event in scan if event["type"] == "scan")
            image_indices = [str(item["index"]) for item in result["items"] if item["kind"] == "Imagens"]
            if not image_indices:
                raise AssertionError("The image filter returned no files")
            events_of(
                subprocess.run(
                    [str(ENGINE), "download", "--session", str(session_path), "--indices", ",".join(image_indices)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
            )
            written = [path for path in output.rglob("*") if path.is_file() and not path.name.startswith(".")]
            if not written or any(path.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"} for path in written):
                raise AssertionError(f"The image filter downloaded unexpected files: {written}")
            print(f"PASS: {len(image_indices)} imagens filtradas; {len(written)} arquivos baixados")
            return 0
    finally:
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
