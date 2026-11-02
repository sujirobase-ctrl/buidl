"""JSON-lines bridge used by the optional C#/.NET 10 WinUI frontend."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from src.config import TaskResult
from src.downloaders import PreparedThread, ThreadDownloader, ThreadOptions
from src.http_client import HttpClient
from src.preview import media_kind
from src.resolvers import ResolvedMedia


def emit(event_type: str, **payload) -> None:
    print(json.dumps({"type": event_type, **payload}, ensure_ascii=False), flush=True)


class BridgeManager:
    """Minimal live-manager implementation which emits machine-readable events."""

    def __init__(self) -> None:
        self.total = 0
        self.completed = 0
        self.skipped = 0
        self.failed = 0
        self._task_id = 0

    def add_overall_task(self, description: str, num_tasks: int) -> None:
        self.total = num_tasks
        emit("plan", title=description, total=num_tasks)

    def add_task(self, current_task: int = 0, total: int = 100) -> int:
        del current_task, total
        self._task_id += 1
        return self._task_id

    def update_task(self, task_id: int, completed=None, advance: int = 0, *, visible=True) -> None:
        del task_id, completed, advance, visible

    def update_log(self, *, event: str, details: str, verbose_only: bool = False) -> None:
        if not verbose_only:
            emit("log", event=event, message=details)

    def update_summary(self, task_result: TaskResult, reason=None) -> None:
        del reason
        name = getattr(task_result, "name", str(task_result)).casefold()
        if "complete" in name:
            self.completed += 1
        elif "skip" in name:
            self.skipped += 1
        else:
            self.failed += 1
        emit(
            "progress",
            completed=self.completed,
            skipped=self.skipped,
            failed=self.failed,
            total=self.total,
        )


def options_from(request: dict) -> ThreadOptions:
    return ThreadOptions(
        download_path=request.get("output") or str(Path.home() / "Downloads"),
        max_pages=max(int(request.get("max_pages", 1)), 1),
        all_pages=bool(request.get("all_pages", True)),
        include=list(request.get("include") or []),
        ignore=list(request.get("ignore") or []),
        workers=max(int(request.get("workers", 2)), 1),
        separate_posts=bool(request.get("separate_posts", False)),
        flat=bool(request.get("flat", False)),
    )


def scan(request_path: Path, session_path: Path) -> int:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    manager = BridgeManager()
    with HttpClient(cookies_file=request.get("cookies") or None) as client:
        prepared = ThreadDownloader(client, manager, options_from(request)).prepare_thread(request["url"])
    if prepared is None:
        emit("error", message="A thread não retornou arquivos. Verifique a URL, sessão e permissões.")
        return 2
    session = {
        "request": request,
        "title": prepared.title,
        "root": str(prepared.root),
        "post_count": prepared.post_count,
        "plan": [
            {"media": asdict(media), "folder": str(folder)}
            for media, folder in prepared.plan
        ],
    }
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps(session, ensure_ascii=False), encoding="utf-8")
    items = [
        {
            "index": index,
            "name": media.filename,
            "kind": media_kind(media),
            "post": media.post_label,
            "host": urlparse(media.origin_url or media.state_key).hostname or "",
        }
        for index, (media, _) in enumerate(prepared.plan)
    ]
    emit(
        "scan",
        title=prepared.title,
        posts=prepared.post_count,
        count=len(items),
        items=items,
    )
    return 0


def download(session_path: Path, indices_text: str) -> int:
    session = json.loads(session_path.read_text(encoding="utf-8"))
    plan = [
        (ResolvedMedia(**entry["media"]), Path(entry["folder"]))
        for entry in session["plan"]
    ]
    prepared = PreparedThread(
        session["title"], Path(session["root"]), plan, int(session["post_count"])
    )
    indices = {
        int(value) for value in indices_text.split(",") if value.strip()
    }
    if any(index < 0 or index >= len(plan) for index in indices):
        emit("error", message="A seleção não pertence à análise atual.")
        return 2
    selected = {plan[index][0].state_key for index in indices}
    manager = BridgeManager()
    request = session["request"]
    with HttpClient(cookies_file=request.get("cookies") or None) as client:
        failed = ThreadDownloader(client, manager, options_from(request)).download_prepared(
            prepared, selected
        )
    emit("done", failed=bool(failed), output=str(prepared.root))
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="buidl-engine")
    commands = parser.add_subparsers(dest="command", required=True)
    scan_parser = commands.add_parser("scan")
    scan_parser.add_argument("--request", type=Path, required=True)
    scan_parser.add_argument("--session", type=Path, required=True)
    download_parser = commands.add_parser("download")
    download_parser.add_argument("--session", type=Path, required=True)
    download_parser.add_argument("--indices", required=True)
    return parser.parse_args()


def main() -> int:
    # The C# process reader always consumes JSON Lines as UTF-8, independent of
    # the user's legacy Windows console code page.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    try:
        if args.command == "scan":
            return scan(args.request, args.session)
        return download(args.session, args.indices)
    except Exception as error:  # noqa: BLE001 - process boundary must return JSON
        emit("error", message=str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
