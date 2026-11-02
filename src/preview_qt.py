"""Responsive Qt 6 gallery and bounded video preview for Windows."""

from __future__ import annotations

import math
import queue
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from PIL import Image
from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.downloaders import PreparedThread
from src.preview import PreviewSelection, fetch_thumbnail, media_kind, thumbnail_source
from src.video_preview import VideoPreview, fetch_video_preview

PAGE_SIZE = 18
KIND_FILTERS = (
    ("Todos", "Todos"),
    ("Imagens", "Só fotos"),
    ("Vídeos", "Só vídeos"),
    ("Áudios", "Áudios"),
    ("Arquivos", "Outros"),
)


def _pixmap(image: Image.Image) -> QPixmap:
    converted = image.convert("RGBA")
    data = converted.tobytes("raw", "RGBA")
    qt_image = QImage(
        data,
        converted.width,
        converted.height,
        converted.width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()
    return QPixmap.fromImage(qt_image)


class VideoPreviewDialog(QDialog):
    """Play a short in-memory preview without coupling it to download state."""

    def __init__(self, parent, media, cookies_file, cover, cached, pool, on_result):
        super().__init__(parent)
        self.media = media
        self.cookies_file = cookies_file
        self.cover = cover
        self.result = cached or VideoPreview()
        self.pool = pool
        self.on_result = on_result
        self.stop_event = threading.Event()
        self.results: queue.Queue = queue.Queue()
        self.frame_index = 0
        self.playing = False
        self.future = None

        self.setWindowTitle("BUIDL — Prévia do vídeo")
        self.setMinimumSize(520, 410)
        self.resize(720, 540)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(media.filename or "Vídeo")
        title.setProperty("role", "section")
        title.setWordWrap(True)
        layout.addWidget(title)
        self.screen = QLabel("▶\nPrévia indisponível")
        self.screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screen.setMinimumSize(320, 220)
        self.screen.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.screen.setProperty("subtle", True)
        layout.addWidget(self.screen, 1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "muted")
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        self.play_button = QPushButton("Reproduzir")
        self.play_button.clicked.connect(self._toggle)
        self.retry_button = QPushButton("Tentar novamente")
        self.retry_button.clicked.connect(self._load)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.close)
        actions.addWidget(self.play_button)
        actions.addWidget(self.retry_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(80)
        self.poll_timer.timeout.connect(self._poll)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._tick)
        if self.result.frames:
            self._accept(self.result)
        else:
            self._show_frame(cover)
            self._load()

    def _load(self) -> None:
        if self.future is not None and not self.future.done():
            return
        self.stop_event = threading.Event()
        self.status.setText("Carregando um trecho curto e sem áudio…")
        self.retry_button.setEnabled(False)
        self.future = self.pool.submit(self._fetch)
        self.poll_timer.start()

    def _fetch(self) -> None:
        try:
            result = fetch_video_preview(self.media, self.cookies_file, self.stop_event)
        except Exception:  # noqa: BLE001 - preview failures never fail downloads
            result = VideoPreview()
        if not self.stop_event.is_set():
            self.results.put(result)

    def _poll(self) -> None:
        try:
            result = self.results.get_nowait()
        except queue.Empty:
            return
        self.poll_timer.stop()
        self._accept(result)
        self.on_result(result)

    def _accept(self, result: VideoPreview) -> None:
        self.result = result
        self.frame_index = 0
        self.retry_button.setEnabled(True)
        if result.frames:
            self.status.setText(
                result.message or "Trecho de até 6 segundos · sem áudio"
            )
            self.play_button.setEnabled(True)
            self.playing = True
            self._tick()
        else:
            self.playing = False
            self.play_button.setEnabled(False)
            self.status.setText(
                "Prévia indisponível neste host. O arquivo ainda pode ser baixado."
            )
            self._show_frame(self.cover)

    def _show_frame(self, frame) -> None:
        if frame is None:
            return
        pixmap = _pixmap(frame)
        target = self.screen.size() - QSize(16, 16)
        self.screen.setPixmap(
            pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.screen.setText("")

    def _toggle(self) -> None:
        if not self.result.frames:
            return
        self.playing = not self.playing
        self.play_button.setText("Pausar" if self.playing else "Reproduzir")
        if self.playing:
            self._tick()
        else:
            self.play_timer.stop()

    def _tick(self) -> None:
        if not self.playing or not self.result.frames:
            return
        self._show_frame(self.result.frames[self.frame_index])
        self.frame_index = (self.frame_index + 1) % len(self.result.frames)
        self.play_button.setText("Pausar")
        self.play_timer.start(round(1000 / self.result.fps))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.result.frames:
            self._show_frame(self.result.frames[max(0, self.frame_index - 1)])
        elif self.cover is not None:
            self._show_frame(self.cover)

    def closeEvent(self, event) -> None:
        self.stop_event.set()
        self.poll_timer.stop()
        self.play_timer.stop()
        event.accept()


class MediaCard(QFrame):
    def __init__(self, index, media, selected, on_toggle, on_video):
        super().__init__()
        self.index = index
        self.media = media
        self.setProperty("card", True)
        self.setMinimumWidth(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        kind = media_kind(media)
        self.checkbox = QCheckBox(f"{kind}  ·  {media.post_label or 'Arquivo'}")
        self.checkbox.setChecked(selected)
        self.checkbox.toggled.connect(lambda value: on_toggle(index, value))
        layout.addWidget(self.checkbox)
        self.preview = QLabel(
            "Carregando prévia…"
            if thumbnail_source(media)
            else (
                "▶\nVídeo · abra a prévia"
                if kind == "Vídeos"
                else f"{kind}\nSem prévia"
            )
        )
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(150)
        self.preview.setProperty("subtle", True)
        layout.addWidget(self.preview)
        name = QLabel(media.filename or "Nome disponível ao iniciar o download")
        name.setWordWrap(True)
        name.setMinimumHeight(38)
        layout.addWidget(name)
        source = media.origin_url or media.state_key
        host = urlparse(source).hostname or "link"
        origin = QPushButton(f"Abrir origem  ·  {host}")
        origin.setToolTip(source)
        origin.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(source)))
        layout.addWidget(origin)
        if kind == "Vídeos":
            video = QPushButton("▶  Prévia do vídeo")
            video.setProperty("primary", True)
            video.clicked.connect(lambda: on_video(index))
            layout.addWidget(video)

    def show_image(self, image) -> None:
        if image is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(
                "Prévia indisponível\nO arquivo ainda pode ser baixado"
            )
            return
        pixmap = _pixmap(image)
        self.preview.setPixmap(
            pixmap.scaled(
                360,
                190,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.preview.setText("")


class PreviewDialog(QDialog):
    """Adaptive media gallery with filter-first download actions."""

    def __init__(
        self,
        parent,
        prepared: PreparedThread,
        cookies_file,
        on_confirm,
        on_cancel,
        *,
        session=None,
        on_refresh=None,
    ):
        super().__init__(parent)
        self.prepared = prepared
        self.model = PreviewSelection([media for media, _ in prepared.plan])
        self.session = session
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.on_refresh = on_refresh
        self.cookies_file = cookies_file
        if session is not None:
            self.model.selected = session.selected
        self.page = session.page if session is not None else 0
        self.cache = session.thumbnails if session is not None else OrderedDict()
        self.videos = session.videos if session is not None else OrderedDict()
        self.pool = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="buidl-preview"
        )
        self.video_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="buidl-video"
        )
        self.results: queue.Queue = queue.Queue()
        self.futures = []
        self.page_stop = threading.Event()
        self.generation = 0
        self.cards: list[MediaCard] = []
        self.card_by_index: dict[int, MediaCard] = {}
        self.video_dialog = None
        self._completed = False
        self._last_columns = 0

        self.setWindowTitle("BUIDL — Visualizar e escolher")
        self.setMinimumSize(720, 560)
        self.resize(1120, 800)
        self.setModal(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(10)
        title = QLabel(prepared.title)
        title.setProperty("role", "title")
        title.setWordWrap(True)
        root.addWidget(title)
        subtitle = QLabel(
            f"{len(prepared.plan)} arquivos encontrados · {prepared.post_count} posts\n"
            "Filtre o conteúdo e baixe os resultados diretamente ou monte uma seleção."
        )
        subtitle.setWordWrap(True)
        subtitle.setProperty("role", "muted")
        root.addWidget(subtitle)

        filter_card = QFrame()
        filter_card.setProperty("card", True)
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        search_row = QHBoxLayout()
        self.search = QLineEdit(session.query if session is not None else "")
        self.search.setPlaceholderText("Buscar por nome, post ou host…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar na galeria")
        self.search.textChanged.connect(self._filter_changed)
        search_row.addWidget(self.search, 1)
        if on_refresh is not None:
            refresh = QPushButton("Atualizar thread")
            refresh.clicked.connect(self._refresh)
            search_row.addWidget(refresh)
        filter_layout.addLayout(search_row)
        kinds = QHBoxLayout()
        kinds.addWidget(QLabel("Mostrar:"))
        self.kind_group = QButtonGroup(self)
        self.kind_group.setExclusive(True)
        self.kind_buttons = {}
        active = session.kind if session is not None else "Todos"
        for kind, label in KIND_FILTERS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("filter", True)
            button.setMinimumWidth(86)
            button.setChecked(kind == active)
            button.clicked.connect(
                lambda _checked=False, value=kind: self._set_kind(value)
            )
            self.kind_group.addButton(button)
            self.kind_buttons[kind] = button
            kinds.addWidget(button)
        kinds.addStretch(1)
        filter_layout.addLayout(kinds)
        root.addWidget(filter_card)

        selection = QHBoxLayout()
        mark = QPushButton("Marcar resultados")
        mark.clicked.connect(lambda: self._select_results(True))
        unmark = QPushButton("Desmarcar resultados")
        unmark.clicked.connect(lambda: self._select_results(False))
        self.selection_label = QLabel()
        self.selection_label.setProperty("role", "muted")
        selection.addWidget(mark)
        selection.addWidget(unmark)
        selection.addStretch(1)
        selection.addWidget(self.selection_label)
        root.addLayout(selection)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery = QWidget()
        self.gallery.setObjectName("appRoot")
        self.gallery_layout = QGridLayout(self.gallery)
        self.gallery_layout.setContentsMargins(2, 2, 8, 2)
        self.gallery_layout.setSpacing(10)
        self.scroll.setWidget(self.gallery)
        root.addWidget(self.scroll, 1)

        page_row = QHBoxLayout()
        self.previous = QPushButton("←  Anterior")
        self.previous.clicked.connect(lambda: self._change_page(-1))
        self.next = QPushButton("Próxima  →")
        self.next.clicked.connect(lambda: self._change_page(1))
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setProperty("role", "muted")
        page_row.addWidget(self.previous)
        page_row.addWidget(self.page_label, 1)
        page_row.addWidget(self.next)
        root.addLayout(page_row)
        destination = QLabel(f"Destino: {prepared.root}")
        destination.setWordWrap(True)
        destination.setProperty("role", "muted")
        root.addWidget(destination)

        self.actions = QWidget()
        self.actions_layout = QGridLayout(self.actions)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        self.back_button = QPushButton("Voltar sem baixar")
        self.back_button.clicked.connect(self.reject)
        self.all_button = QPushButton(f"Baixar tudo ({len(prepared.plan)})")
        self.all_button.clicked.connect(lambda: self._confirm(None))
        self.filtered_button = QPushButton("Baixar resultados do filtro")
        self.filtered_button.setProperty("primary", True)
        self.filtered_button.clicked.connect(self._confirm_filtered)
        self.selected_button = QPushButton("Baixar selecionados")
        self.selected_button.clicked.connect(self._confirm_selected)
        self.action_buttons = (
            self.back_button,
            self.all_button,
            self.filtered_button,
            self.selected_button,
        )
        root.addWidget(self.actions)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(80)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start()
        self._render_page()
        QTimer.singleShot(0, self._restore_scroll)

    @property
    def kind(self) -> str:
        for value, button in self.kind_buttons.items():
            if button.isChecked():
                return value
        return "Todos"

    def _filtered(self) -> list[int]:
        return self.model.filtered_indices(self.search.text(), self.kind)

    def _set_kind(self, kind: str) -> None:
        self.kind_buttons[kind].setChecked(True)
        self._filter_changed()

    def _filter_changed(self) -> None:
        self.page = 0
        self._render_page()

    def _change_page(self, delta: int) -> None:
        self.page += delta
        self._render_page()

    def _select_results(self, enabled: bool) -> None:
        self.model.select(self._filtered(), enabled)
        for card in self.cards:
            card.checkbox.blockSignals(True)
            card.checkbox.setChecked(card.media.state_key in self.model.selected)
            card.checkbox.blockSignals(False)
        self._update_selection()

    def _toggle(self, index: int, enabled: bool) -> None:
        self.model.select([index], enabled)
        self._update_selection()

    def _update_selection(self) -> None:
        filtered = self._filtered()
        visible = {self.model.items[index].state_key for index in filtered}
        count = len(self.model.selected)
        hidden = count - len(self.model.selected & visible)
        self.selection_label.setText(
            f"{count} selecionados" + (f" · {hidden} fora do filtro" if hidden else "")
        )
        self.filtered_button.setText(f"Baixar resultados do filtro ({len(filtered)})")
        self.filtered_button.setEnabled(bool(filtered))
        self.selected_button.setText(f"Baixar selecionados ({count})")
        self.selected_button.setEnabled(bool(count))

    def _clear_cards(self) -> None:
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.cards.clear()
        self.card_by_index.clear()

    def _render_page(self) -> None:
        self.page_stop.set()
        for future in self.futures:
            future.cancel()
        self.futures.clear()
        self.page_stop = threading.Event()
        self.generation += 1
        self._clear_cards()
        indices = self._filtered()
        pages = max(1, math.ceil(len(indices) / PAGE_SIZE))
        self.page = max(0, min(self.page, pages - 1))
        self.page_label.setText(
            f"Página {self.page + 1} / {pages}  ·  {len(indices)} resultados"
        )
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled(self.page + 1 < pages)
        visible = indices[self.page * PAGE_SIZE : (self.page + 1) * PAGE_SIZE]
        for index in visible:
            media = self.model.items[index]
            card = MediaCard(
                index,
                media,
                media.state_key in self.model.selected,
                self._toggle,
                self._open_video,
            )
            self.cards.append(card)
            self.card_by_index[index] = card
            if index in self.cache:
                card.show_image(self.cache[index])
                self.cache.move_to_end(index)
            elif thumbnail_source(media):
                self.futures.append(
                    self.pool.submit(
                        self._fetch,
                        self.generation,
                        index,
                        media,
                        self.page_stop,
                    )
                )
        if not visible:
            empty = QLabel("Nenhum arquivo corresponde a este filtro.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(180)
            empty.setProperty("role", "muted")
            self.cards.append(empty)  # type: ignore[arg-type]
        self._last_columns = 0
        self._reflow_cards()
        self.scroll.verticalScrollBar().setValue(0)
        self._update_selection()

    def _reflow_cards(self) -> None:
        width = max(1, self.scroll.viewport().width())
        columns = 1 if width < 560 else 2 if width < 880 else 3
        self._reflow_actions(width)
        if columns == self._last_columns and self.gallery_layout.count() == len(
            self.cards
        ):
            return
        self._last_columns = columns
        for card in self.cards:
            self.gallery_layout.removeWidget(card)
        for slot, card in enumerate(self.cards):
            self.gallery_layout.addWidget(card, slot // columns, slot % columns)
        for column in range(3):
            self.gallery_layout.setColumnStretch(column, 1 if column < columns else 0)
        self.gallery_layout.setRowStretch(
            max(1, math.ceil(len(self.cards) / columns)), 1
        )

    def _reflow_actions(self, width: int) -> None:
        for button in self.action_buttons:
            self.actions_layout.removeWidget(button)
        if width < 820:
            for slot, button in enumerate(self.action_buttons):
                self.actions_layout.addWidget(button, slot // 2, slot % 2)
        else:
            for column, button in enumerate(self.action_buttons):
                self.actions_layout.addWidget(button, 0, column)
            self.actions_layout.setColumnStretch(0, 1)

    def _fetch(self, generation, index, media, stop) -> None:
        thumbnail = fetch_thumbnail(media, self.cookies_file, stop)
        if not stop.is_set():
            self.results.put((generation, index, thumbnail))

    def _poll(self) -> None:
        try:
            while True:
                generation, index, thumbnail = self.results.get_nowait()
                if generation != self.generation:
                    continue
                self.cache[index] = thumbnail
                while len(self.cache) > 96:
                    self.cache.popitem(last=False)
                card = self.card_by_index.get(index)
                if card is not None:
                    card.show_image(thumbnail)
        except queue.Empty:
            pass

    def _open_video(self, index: int) -> None:
        if self.video_dialog is not None and self.video_dialog.isVisible():
            self.video_dialog.raise_()
            self.video_dialog.activateWindow()
            return
        self.video_dialog = VideoPreviewDialog(
            self,
            self.model.items[index],
            self.cookies_file,
            self.cache.get(index),
            self.videos.get(index),
            self.video_pool,
            lambda result: self._video_ready(index, result),
        )
        self.video_dialog.show()

    def _video_ready(self, index: int, result: VideoPreview) -> None:
        self.videos[index] = result
        self.videos.move_to_end(index)
        while len(self.videos) > 2:
            self.videos.popitem(last=False)
        if result.frames:
            cover = result.frames[0].copy()
            cover.thumbnail((360, 190))
            self.cache[index] = cover
            card = self.card_by_index.get(index)
            if card is not None:
                card.show_image(cover)

    def _confirm(self, keys: set[str] | None) -> None:
        self._completed = True
        self._save_session()
        self._shutdown()
        self.accept()
        self.on_confirm(keys)

    def _confirm_filtered(self) -> None:
        keys = {self.model.items[index].state_key for index in self._filtered()}
        if keys:
            self._confirm(keys)

    def _confirm_selected(self) -> None:
        keys = set(self.model.selected)
        if keys:
            self._confirm(keys)

    def _refresh(self) -> None:
        self._completed = True
        self._save_session()
        self._shutdown()
        self.accept()
        if self.on_refresh is not None:
            self.on_refresh()

    def _restore_scroll(self) -> None:
        if self.session is not None:
            maximum = self.scroll.verticalScrollBar().maximum()
            self.scroll.verticalScrollBar().setValue(
                round(maximum * self.session.scroll)
            )

    def _save_session(self) -> None:
        if self.session is None:
            return
        self.session.page = self.page
        self.session.query = self.search.text()
        self.session.kind = self.kind
        maximum = self.scroll.verticalScrollBar().maximum()
        self.session.scroll = (
            self.scroll.verticalScrollBar().value() / maximum if maximum else 0.0
        )

    def _shutdown(self) -> None:
        self.poll_timer.stop()
        self.page_stop.set()
        if self.video_dialog is not None:
            self.video_dialog.close()
        self.video_pool.shutdown(wait=False, cancel_futures=True)
        self.pool.shutdown(wait=False, cancel_futures=True)

    def reject(self) -> None:
        if not self._completed:
            self._completed = True
            self._save_session()
            self._shutdown()
            super().reject()
            self.on_cancel()
        else:
            super().reject()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._reflow_cards)

    def closeEvent(self, event) -> None:
        if not self._completed:
            self.reject()
            event.ignore()
        else:
            event.accept()
