"""Render and exercise the responsive Qt desktop UI without network access."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from gui_qt import BuidlWindow
from src import preview_qt
from src.downloaders import PreparedThread
from src.preview_qt import PreviewDialog
from src.qt_theme import apply_theme
from src.resolvers import ResolvedMedia


def pump(app: QApplication, seconds: float = 0.2) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def fixture_thumbnail(media, _cookies, stop):
    if stop.is_set() or media.filename.endswith(".zip"):
        return None
    image = Image.new("RGB", (360, 200), "#293B63")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, 342, 182), radius=18, outline="#9184FF", width=3)
    draw.text((34, 88), media.filename, fill="white")
    return image


def inside(parent, child) -> bool:
    return (
        child.x() >= 0
        and child.y() >= 0
        and child.x() + child.width() <= parent.width()
        and child.y() + child.height() <= parent.height()
    )


def run() -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_theme(app, True)
    preview_qt.fetch_thumbnail = fixture_thumbnail

    window = BuidlWindow()
    window.resize(760, 600)
    window.show()
    pump(app)
    assert window._breakpoint == "compact"
    assert window.scroll.horizontalScrollBar().maximum() == 0
    assert all(inside(window.actions, button) for button in window.action_buttons)
    (ROOT / "build").mkdir(exist_ok=True)
    window.grab().save(str(ROOT / "build" / "qa-qt-main-compact-1.5.0.png"))
    window.resize(1240, 820)
    pump(app)
    assert window._breakpoint == "expanded"
    assert window.scroll.horizontalScrollBar().maximum() == 0

    root = ROOT / "Downloads" / "Thread de demonstração"
    items = [
        ResolvedMedia(
            f"https://media.example/Photo-{index:02}.jpg",
            f"Photo-{index:02}.jpg",
            post_label=f"post-{index // 4 + 1}",
        )
        for index in range(12)
    ]
    items += [
        ResolvedMedia(
            "https://media.example/video.mp4",
            "Vídeo exclusivo.mp4",
            post_label="post-4",
        ),
        ResolvedMedia(
            "https://media.example/pack.zip",
            "Coleção completa.zip",
            post_label="post-4",
        ),
    ]
    prepared = PreparedThread(
        "Thread de demonstração — escolha o que baixar",
        root,
        [(item, root) for item in items],
        4,
    )
    decisions = []
    dialog = PreviewDialog(
        window, prepared, None, decisions.append, lambda: decisions.append("cancel")
    )
    dialog.resize(720, 620)
    dialog.show()
    pump(app, 0.8)
    assert dialog._last_columns == 2
    assert all(inside(dialog.actions, button) for button in dialog.action_buttons)
    dialog.grab().save(str(ROOT / "build" / "qa-qt-gallery-compact-1.5.0.png"))
    dialog._set_kind("Vídeos")
    pump(app)
    assert dialog._filtered() == [12]
    assert dialog.filtered_button.text() == "Baixar resultados do filtro (1)"
    dialog.filtered_button.click()
    pump(app)
    assert decisions == [{items[12].state_key}]

    window.close()
    pump(app)
    print(
        "QT GUI PASS: DPI-aware shell, compact/expanded reflow, gallery and filtered download"
    )


if __name__ == "__main__":
    run()
