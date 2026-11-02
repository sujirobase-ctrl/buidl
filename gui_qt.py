"""Modern, DPI-aware Qt 6 desktop interface for BUIDL."""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src import __version__
from src.config import INTER_FILE_DELAY, MAX_RETRIES, MAX_WORKERS, TaskResult
from src.downloaders import ThreadDownloader, ThreadOptions
from src.file_utils import redact_sensitive_urls
from src.http_client import HttpClient
from src.managers.log_manager import LoggerTable
from src.managers.summary_manager import SummaryManager
from src.preview import PreviewCommand, PreviewSession, preview_fingerprint
from src.preview_qt import PreviewDialog
from src.qt_theme import apply_theme

APP_NAME = "BUIDL"
FAILURE_EVENTS = {
    "Download failed",
    "Unexpected error",
    "Page error",
    "Access denied",
    "Login required",
}


class GuiManager:
    """Translate downloader callbacks into queue messages safe for Qt's UI thread."""

    def __init__(self, events: queue.Queue, log_file: Path) -> None:
        self.events = events
        self.logger = LoggerTable(log_file=str(log_file), verbose=False)
        self.summary = SummaryManager()
        self.total = 0
        self.title = ""
        self._task_id = 0
        self._tasks: dict[int, dict[str, float | bool]] = {}
        self._last_transfer_emit = 0.0
        self._lock = threading.Lock()
        self.start_time = time.monotonic()

    def start(self) -> None:
        self.update_log(event="Iniciado", details="Preparando o download.")

    def stop(self) -> None:
        elapsed = time.monotonic() - self.start_time
        counts = self._counts()
        self.update_log(
            event="Resumo",
            details=(
                f"Concluídos: {counts['completed']} | Ignorados: {counts['skipped']} | "
                f"Falhas: {counts['failed']}"
            ),
        )
        self.events.put(("manager_stopped", elapsed, counts))

    def add_overall_task(self, description: str, num_tasks: int) -> None:
        self.title = description
        self.total = num_tasks
        self.events.put(("plan", description, num_tasks))

    def add_task(self, current_task: int = 0, total: int = 100) -> int:
        del current_task
        with self._lock:
            self._task_id += 1
            task_id = self._task_id
            self._tasks[task_id] = {
                "completed": 0.0,
                "total": max(float(total), 1.0),
                "visible": True,
            }
            transfer = self._transfer_event_unlocked()
        self.events.put(transfer)
        return task_id

    def update_task(
        self, task_id: int, completed=None, advance: int = 0, *, visible=True
    ) -> None:
        transfer = None
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if completed is not None:
                task["completed"] = max(float(completed), 0.0)
            elif advance:
                task["completed"] = max(
                    float(task["completed"]) + float(advance), 0.0
                )
            task["visible"] = bool(visible)
            now = time.monotonic()
            finished = float(task["completed"]) >= float(task["total"])
            if finished or now - self._last_transfer_emit >= 0.08:
                self._last_transfer_emit = now
                transfer = self._transfer_event_unlocked()
        if transfer is not None:
            self.events.put(transfer)

    def update_log(
        self, *, event: str, details: str, verbose_only: bool = False
    ) -> None:
        with self._lock:
            recorded = self.logger.log(
                event, details, disable_ui=False, verbose_only=verbose_only
            )
        if recorded:
            stamp = time.strftime("%H:%M:%S")
            safe_details = redact_sensitive_urls(details)
            self.events.put(("log", stamp, event, safe_details))
            if event in FAILURE_EVENTS:
                self.events.put(("failure", stamp, event, safe_details))

    def update_summary(self, task_result: TaskResult, reason=None) -> None:
        with self._lock:
            self.summary.update_result(task_result, reason)
            counts = self._counts_unlocked()
            transfer = self._transfer_event_unlocked(counts)
        self.events.put(("progress", counts, self.total))
        self.events.put(transfer)

    def _counts(self) -> dict[str, int]:
        with self._lock:
            return self._counts_unlocked()

    def reset_summary(self) -> None:
        with self._lock:
            self.summary = SummaryManager()
            self.total = 0
            self._tasks.clear()
            self._last_transfer_emit = 0.0
        self.events.put(("progress", self._counts(), 0))

    def _counts_unlocked(self) -> dict[str, int]:
        return {
            "completed": self.summary.get_result_count(TaskResult.COMPLETED),
            "skipped": self.summary.get_result_count(TaskResult.SKIPPED),
            "failed": self.summary.get_result_count(TaskResult.FAILED),
        }

    def _transfer_event_unlocked(self, counts=None) -> tuple:
        counts = counts or self._counts_unlocked()
        task_units = sum(
            min(float(task["completed"]) / float(task["total"]), 1.0)
            for task in self._tasks.values()
        )
        completed_units = float(sum(counts.values()))
        visible_tasks = sum(
            1
            for task in self._tasks.values()
            if bool(task["visible"])
            and float(task["completed"]) < float(task["total"])
        )
        return (
            "transfer",
            counts,
            self.total,
            max(completed_units, task_units),
            visible_tasks,
        )


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("card", True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    return frame, layout


def _label(text: str, role: str | None = None) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    return label


class PathField(QFrame):
    def __init__(self, title: str, value: str, choose):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        caption = _label(title, "muted")
        layout.addWidget(caption)
        row = QHBoxLayout()
        self.entry = QLineEdit(value)
        self.entry.setClearButtonEnabled(True)
        button = QPushButton("Escolher…")
        button.clicked.connect(choose)
        row.addWidget(self.entry, 1)
        row.addWidget(button)
        layout.addLayout(row)


class MetricCard(QFrame):
    def __init__(self, title: str, role: str):
        super().__init__()
        self.setProperty("subtle", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        value = _label("0")
        value.setStyleSheet("font-size: 18pt; font-weight: 700;")
        value.setProperty("role", role)
        layout.addWidget(value)
        layout.addWidget(_label(title, "muted"))
        self.value = value


class BuidlWindow(QMainWindow):
    """Single-scroll responsive shell; no action is placed outside a layout."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Media Downloader")
        self.setMinimumSize(760, 600)
        self.resize(1180, 820)
        self.events: queue.Queue = queue.Queue()
        self.worker_thread = None
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.running = False
        self.started_at = 0.0
        self.total_files = 0
        self.last_counts = {"completed": 0, "skipped": 0, "failed": 0}
        self.failures: list[tuple[str, str, str]] = []
        self.current_log_file = Path.cwd() / "buidl-gui.log"
        self.preview_dialog = None
        self.selection_queue: queue.Queue = queue.Queue()
        self.preview_phase = False
        self.preview_session = None
        self.active_preview_key: tuple = ()
        self.dark = True
        self._view_mode = "home"
        self._breakpoint = None
        self._build_ui()
        self._load_defaults()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(80)
        self.poll_timer.timeout.connect(self._poll_events)
        self.poll_timer.start()
        QTimer.singleShot(0, self._apply_breakpoint)

    def _build_ui(self) -> None:
        shell = QWidget()
        shell.setObjectName("appRoot")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        command_bar = QWidget()
        command_bar.setProperty("subtle", True)
        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(14, 8, 14, 8)
        command_layout.setSpacing(8)
        mark = _label("▦", "danger")
        mark.setStyleSheet("font-size: 16pt; font-weight: 700;")
        command_layout.addWidget(mark)
        command_layout.addWidget(_label("BUIDL", "section"))
        for title in ("Arquivo", "Editar", "Downloads", "Ajuda"):
            menu_button = QPushButton(title)
            menu_button.setProperty("menu", True)
            if title == "Downloads":
                menu_button.clicked.connect(lambda: self._show_activity())
            elif title == "Ajuda":
                menu_button.clicked.connect(self._show_about)
            else:
                menu_button.clicked.connect(self._focus_new_download)
            command_layout.addWidget(menu_button)
        command_layout.addStretch(1)
        appearance_button = QPushButton("✧")
        appearance_button.setProperty("menu", True)
        appearance_button.setToolTip("Alternar tema")
        appearance_button.clicked.connect(self._toggle_theme)
        command_layout.addWidget(appearance_button)
        shell_layout.addWidget(command_bar)

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self.nav_panel = QFrame()
        self.nav_panel.setProperty("card", True)
        self.nav_panel.setFixedWidth(220)
        nav_layout = QVBoxLayout(self.nav_panel)
        nav_layout.setContentsMargins(10, 18, 10, 12)
        nav_layout.setSpacing(4)
        nav_layout.addWidget(_label("DOWNLOADS", "muted"))
        self.nav_buttons = []
        for text in ("Tudo", "Novo download", "Progresso", "Atividade"):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setProperty("nav", True)
            self.nav_buttons.append(button)
            nav_layout.addWidget(button)
        self.nav_buttons[0].setChecked(True)
        self.nav_buttons[0].clicked.connect(lambda: self._activate_nav(0, None))
        self.nav_buttons[1].clicked.connect(self._focus_new_download)
        self.nav_buttons[2].clicked.connect(
            lambda: self._activate_nav(2, self.progress_card)
        )
        self.nav_buttons[3].clicked.connect(
            lambda: self._activate_nav(3, self.log_card)
        )
        nav_layout.addStretch(1)
        open_nav = QPushButton("Abrir pasta")
        open_nav.setProperty("nav", True)
        open_nav.clicked.connect(self._open_downloads)
        nav_layout.addWidget(open_nav)
        workspace_layout.addWidget(self.nav_panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root = QWidget()
        root.setObjectName("appRoot")
        scroll.setWidget(root)
        workspace_layout.addWidget(scroll, 1)
        shell_layout.addWidget(workspace, 1)
        self.setCentralWidget(shell)
        self.scroll = scroll
        page = QVBoxLayout(root)
        page.setContentsMargins(24, 20, 24, 24)
        page.setSpacing(12)

        self.home_panel = QWidget()
        home_layout = QVBoxLayout(self.home_panel)
        home_layout.setContentsMargins(24, 28, 24, 24)
        home_layout.setSpacing(14)
        home_mark = _label("▦", "danger")
        home_mark.setStyleSheet("font-size: 34pt; font-weight: 700;")
        home_layout.addWidget(home_mark)
        home_title = _label("Baixar mídia", "title")
        home_title.setStyleSheet("font-size: 23pt; font-weight: 650;")
        home_layout.addWidget(home_title)
        home_text = _label(
            "Adicione uma thread para baixar fotos, vídeos, áudios e arquivos.",
            "muted",
        )
        home_text.setWordWrap(True)
        home_layout.addWidget(home_text)
        home_layout.addSpacing(18)
        home_add = QPushButton("＋  Adicionar download")
        home_add.setProperty("link", True)
        home_add.clicked.connect(self._focus_new_download)
        home_layout.addWidget(home_add, 0, Qt.AlignmentFlag.AlignLeft)
        home_settings = QPushButton("⚙  Configurações")
        home_settings.setProperty("link", True)
        home_settings.clicked.connect(self._focus_new_download)
        home_layout.addWidget(home_settings, 0, Qt.AlignmentFlag.AlignLeft)
        home_layout.addStretch(1)
        page.addWidget(self.home_panel)

        self.header = QWidget()
        self.header_layout = QGridLayout(self.header)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setHorizontalSpacing(10)
        self.header_layout.setVerticalSpacing(8)
        self.brand = QWidget()
        brand = QVBoxLayout(self.brand)
        brand.setContentsMargins(0, 0, 0, 0)
        title = _label("↓  Baixar mídia", "title")
        title.setAccessibleName("BUIDL Media Downloader")
        brand.addWidget(title)
        subtitle = _label(
            f"Adicione uma thread para baixar fotos, vídeos e arquivos  ·  v{__version__}",
            "muted",
        )
        subtitle.setWordWrap(True)
        brand.addWidget(subtitle)
        self.status_label = _label("●  Pronto", "success")
        self.theme_button = QPushButton("☀  Tema claro")
        self.theme_button.clicked.connect(self._toggle_theme)
        page.addWidget(self.header)

        settings_card, settings_layout = _card()
        self.settings_card = settings_card
        heading = _label("Adicionar download", "section")
        settings_layout.addWidget(heading)
        intro = _label(
            "Cole a URL, escolha o destino e ajuste apenas o que precisar.", "muted"
        )
        intro.setWordWrap(True)
        settings_layout.addWidget(intro)
        self.settings_tabs = QTabWidget()
        self.basic_tab = QWidget()
        self.advanced_tab = QWidget()
        self.settings_tabs.addTab(self.basic_tab, "Principal")
        self.settings_tabs.addTab(self.advanced_tab, "Avançado")
        settings_layout.addWidget(self.settings_tabs)
        self._build_basic()
        self._build_advanced()
        page.addWidget(settings_card)

        progress_card, progress_layout = _card()
        self.progress_card = progress_card
        progress_header = QHBoxLayout()
        self.progress_title = _label("Aguardando um download", "section")
        self.progress_title.setWordWrap(True)
        self.progress_text = _label("0 / 0", "muted")
        progress_header.addWidget(self.progress_title, 1)
        progress_header.addWidget(self.progress_text)
        progress_layout.addLayout(progress_header)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        progress_layout.addWidget(self.progress)
        page.addWidget(progress_card)

        self.body = QWidget()
        self.body_layout = QGridLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(12)
        self.metrics_card, metrics_layout = _card()
        metrics_layout.addWidget(_label("Resumo", "section"))
        metrics_grid = QGridLayout()
        self.completed_metric = MetricCard("Concluídos", "success")
        self.skipped_metric = MetricCard("Ignorados", "warning")
        self.failed_metric = MetricCard("Falhas", "danger")
        self.elapsed_metric = MetricCard("Tempo", "muted")
        self.elapsed_metric.value.setText("00:00")
        for slot, metric in enumerate(
            (
                self.completed_metric,
                self.skipped_metric,
                self.failed_metric,
                self.elapsed_metric,
            )
        ):
            metrics_grid.addWidget(metric, slot // 2, slot % 2)
        metrics_layout.addLayout(metrics_grid)
        self.failure_button = QPushButton("Ver falhas")
        self.failure_button.setEnabled(False)
        self.failure_button.clicked.connect(self._show_failures)
        metrics_layout.addWidget(self.failure_button)
        self.log_card, log_layout = _card()
        log_header = QHBoxLayout()
        log_header.addWidget(_label("Atividade", "section"))
        log_header.addStretch(1)
        self.open_log_button = QPushButton("Abrir log")
        self.open_log_button.clicked.connect(self._open_log)
        log_header.addWidget(self.open_log_button)
        log_layout.addLayout(log_header)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(170)
        self.log_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        log_layout.addWidget(self.log_box)
        page.addWidget(self.body)

        self.actions = QWidget()
        self.actions_layout = QGridLayout(self.actions)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        self.open_button = QPushButton("Abrir pasta")
        self.open_button.clicked.connect(self._open_downloads)
        self.preview_button = QPushButton("Visualizar e escolher")
        self.preview_button.clicked.connect(lambda: self._start_download(preview=True))
        self.pause_button = QPushButton("Pausar")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.start_button = QPushButton("Baixar tudo")
        self.start_button.setProperty("primary", True)
        self.start_button.clicked.connect(self._start_download)
        self.action_buttons = (
            self.open_button,
            self.preview_button,
            self.pause_button,
            self.cancel_button,
            self.start_button,
        )
        page.addWidget(self.actions)
        page.addStretch(1)
        self._show_home()

    def _build_basic(self) -> None:
        layout = QVBoxLayout(self.basic_tab)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(10)
        layout.addWidget(_label("URL DA THREAD", "muted"))
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("https://…")
        self.url_entry.setClearButtonEnabled(True)
        layout.addWidget(self.url_entry)
        self.paths = QWidget()
        self.paths_layout = QGridLayout(self.paths)
        self.paths_layout.setContentsMargins(0, 0, 0, 0)
        self.paths_layout.setSpacing(10)
        self.cookies_field = PathField("COOKIES (OPCIONAL)", "", self._choose_cookies)
        self.output_field = PathField(
            "SALVAR EM", str(Path.cwd() / "Downloads"), self._choose_output
        )
        self.cookies_entry = self.cookies_field.entry
        self.output_entry = self.output_field.entry
        layout.addWidget(self.paths)
        self.basic_options = QWidget()
        self.basic_options_layout = QGridLayout(self.basic_options)
        self.basic_options_layout.setContentsMargins(0, 0, 0, 0)
        self.basic_options_layout.setSpacing(8)
        self.all_pages = QCheckBox("Todas as páginas")
        self.all_pages.setChecked(True)
        self.separate_posts = QCheckBox("Separar posts")
        self.flat = QCheckBox("Ignorar subpastas de álbuns")
        self.dry_run = QCheckBox("Somente analisar")
        self.basic_option_widgets = (
            self.all_pages,
            self.separate_posts,
            self.flat,
            self.dry_run,
        )
        layout.addWidget(self.basic_options)

    def _number_field(self, title: str, widget: QWidget) -> QWidget:
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(_label(title, "muted"))
        layout.addWidget(widget)
        return frame

    def _build_advanced(self) -> None:
        layout = QVBoxLayout(self.advanced_tab)
        layout.setContentsMargins(4, 12, 4, 4)
        self.advanced_grid_widget = QWidget()
        self.advanced_grid = QGridLayout(self.advanced_grid_widget)
        self.advanced_grid.setContentsMargins(0, 0, 0, 0)
        self.advanced_grid.setSpacing(10)
        self.workers_entry = QSpinBox()
        self.workers_entry.setRange(1, 32)
        self.workers_entry.setValue(MAX_WORKERS)
        self.connections_entry = QSpinBox()
        self.connections_entry.setRange(1, 16)
        self.connections_entry.setValue(1)
        self.retries_entry = QSpinBox()
        self.retries_entry.setRange(0, 30)
        self.retries_entry.setValue(MAX_RETRIES)
        self.pages_entry = QSpinBox()
        self.pages_entry.setRange(1, 10000)
        self.pages_entry.setValue(1)
        self.delay_entry = QDoubleSpinBox()
        self.delay_entry.setRange(0, 3600)
        self.delay_entry.setDecimals(1)
        self.delay_entry.setValue(INTER_FILE_DELAY)
        self.rate_entry = QDoubleSpinBox()
        self.rate_entry.setRange(0, 100000)
        self.rate_entry.setDecimals(1)
        self.rate_entry.setSpecialValueText("Sem limite")
        self.advanced_fields = (
            self._number_field("DOWNLOADS SIMULTÂNEOS", self.workers_entry),
            self._number_field("CONEXÕES POR ARQUIVO", self.connections_entry),
            self._number_field("TENTATIVAS", self.retries_entry),
            self._number_field("LIMITE DE PÁGINAS", self.pages_entry),
            self._number_field("INTERVALO (S)", self.delay_entry),
            self._number_field("LIMITE (MB/S)", self.rate_entry),
        )
        layout.addWidget(self.advanced_grid_widget)
        filters = QGridLayout()
        self.include_entry = QLineEdit()
        self.include_entry.setPlaceholderText("jpg, nome, host…")
        self.ignore_entry = QLineEdit()
        self.ignore_entry.setPlaceholderText("webp, thumb, sample…")
        filters.addWidget(_label("INCLUIR", "muted"), 0, 0)
        filters.addWidget(_label("IGNORAR", "muted"), 0, 1)
        filters.addWidget(self.include_entry, 1, 0)
        filters.addWidget(self.ignore_entry, 1, 1)
        layout.addLayout(filters)

    def _load_defaults(self) -> None:
        cookie = Path.cwd() / "cookies.txt"
        if cookie.is_file():
            self.cookies_entry.setText(str(cookie))

    def _scroll_to(self, widget: QWidget) -> None:
        self.scroll.ensureWidgetVisible(widget, 0, 18)

    def _activate_nav(self, index: int, widget: QWidget | None) -> None:
        if index == 1:
            self._view_mode = "configure"
            self.home_panel.hide()
            self.header.hide()
            self.settings_card.show()
            self.progress_card.hide()
            self.body.hide()
            self.actions.show()
        else:
            self._show_activity()
        for button in self.nav_buttons:
            button.setChecked(False)
        self.nav_buttons[index].setChecked(True)
        if widget is None:
            self.scroll.verticalScrollBar().setValue(0)
        else:
            self._scroll_to(widget)

    def _focus_new_download(self) -> None:
        self._activate_nav(1, self.settings_card)
        self.settings_tabs.setCurrentIndex(0)
        self.url_entry.setFocus()

    def _show_home(self) -> None:
        self._view_mode = "home"
        self.home_panel.show()
        self.header.hide()
        self.settings_card.hide()
        self.progress_card.hide()
        self.body.hide()
        self.actions.hide()
        self.nav_panel.hide()

    def _show_activity(self) -> None:
        self._view_mode = "activity"
        self.home_panel.hide()
        self.header.show()
        self.settings_card.hide()
        self.progress_card.show()
        self.body.show()
        self.actions.show()
        self.nav_panel.setVisible(self._breakpoint == "expanded")

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "Sobre o BUIDL",
            f"BUIDL {__version__}\nDownloader de fotos, vídeos, áudios e arquivos.",
        )

    def _toggle_theme(self) -> None:
        self.dark = not self.dark
        apply_theme(QApplication.instance(), self.dark)
        self.theme_button.setText("☀  Tema claro" if self.dark else "☾  Tema escuro")

    def _choose_cookies(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Selecione cookies.txt", "", "Cookies (*.txt);;Todos (*)"
        )
        if selected:
            self.cookies_entry.setText(selected)

    def _choose_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecione a pasta base")
        if selected:
            self.output_entry.setText(selected)

    @staticmethod
    def _csv(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    def _apply_breakpoint(self) -> None:
        width = self.width()
        breakpoint = (
            "compact" if width < 820 else "medium" if width < 1080 else "expanded"
        )
        if breakpoint == self._breakpoint:
            return
        self._breakpoint = breakpoint
        self.nav_panel.setVisible(
            breakpoint == "expanded" and self._view_mode == "activity"
        )
        for widget in (self.brand, self.status_label, self.theme_button):
            self.header_layout.removeWidget(widget)
        if breakpoint == "compact":
            self.header_layout.addWidget(self.brand, 0, 0, 1, 2)
            self.header_layout.addWidget(self.status_label, 1, 0)
            self.header_layout.addWidget(self.theme_button, 1, 1)
        else:
            self.header_layout.addWidget(self.brand, 0, 0)
            self.header_layout.addWidget(self.status_label, 0, 1)
            self.header_layout.addWidget(self.theme_button, 0, 2)
            self.header_layout.setColumnStretch(0, 1)
        for widget in (self.cookies_field, self.output_field):
            self.paths_layout.removeWidget(widget)
        if breakpoint == "compact":
            self.paths_layout.addWidget(self.cookies_field, 0, 0)
            self.paths_layout.addWidget(self.output_field, 1, 0)
        else:
            self.paths_layout.addWidget(self.cookies_field, 0, 0)
            self.paths_layout.addWidget(self.output_field, 0, 1)
        columns = 1 if breakpoint == "compact" else 3
        for slot, widget in enumerate(self.advanced_fields):
            self.advanced_grid.removeWidget(widget)
            self.advanced_grid.addWidget(widget, slot // columns, slot % columns)
        option_columns = (
            1 if breakpoint == "compact" else 2 if breakpoint == "medium" else 3
        )
        for slot, widget in enumerate(self.basic_option_widgets):
            self.basic_options_layout.removeWidget(widget)
            self.basic_options_layout.addWidget(
                widget, slot // option_columns, slot % option_columns
            )
        for widget in (self.metrics_card, self.log_card):
            self.body_layout.removeWidget(widget)
        if breakpoint == "expanded":
            self.body_layout.addWidget(self.metrics_card, 0, 0)
            self.body_layout.addWidget(self.log_card, 0, 1)
            self.body_layout.setColumnStretch(0, 0)
            self.body_layout.setColumnStretch(1, 1)
            self.metrics_card.setMaximumWidth(310)
        else:
            self.metrics_card.setMaximumWidth(16777215)
            self.body_layout.addWidget(self.metrics_card, 0, 0)
            self.body_layout.addWidget(self.log_card, 1, 0)
        for button in self.action_buttons:
            self.actions_layout.removeWidget(button)
        if breakpoint == "compact":
            positions = ((0, 0), (0, 1), (1, 0), (1, 1))
            for button, (row, column) in zip(
                self.action_buttons[:-1], positions, strict=True
            ):
                self.actions_layout.addWidget(button, row, column)
            self.actions_layout.addWidget(self.start_button, 2, 0, 1, 2)
        else:
            for column, button in enumerate(self.action_buttons[:3]):
                self.actions_layout.addWidget(button, 0, column)
            self.actions_layout.addWidget(self.cancel_button, 1, 0)
            self.actions_layout.addWidget(self.start_button, 1, 1, 1, 2)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_breakpoint)

    def _set_status(self, text: str, role: str) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("role", role)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _start_download(self, *, preview: bool = False) -> None:
        if self.running:
            return
        url = self.url_entry.text().strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            QMessageBox.critical(
                self, "Verifique os campos", "Informe uma URL HTTP(S) válida."
            )
            return
        cookie_value = self.cookies_entry.text().strip()
        if cookie_value and not Path(cookie_value).is_file():
            QMessageBox.critical(
                self, "Verifique os campos", "O arquivo de cookies não existe."
            )
            return
        output_value = self.output_entry.text().strip()
        if not output_value:
            QMessageBox.critical(
                self, "Verifique os campos", "Selecione uma pasta base."
            )
            return

        self.cancel_event.clear()
        self.selection_queue = queue.Queue()
        self.preview_phase = preview
        self.pause_event.set()
        self.running = True
        self._show_activity()
        self.started_at = time.monotonic()
        self.total_files = 0
        self.last_counts = {"completed": 0, "skipped": 0, "failed": 0}
        self.failures.clear()
        self._set_running_ui(True)
        self._clear_log()
        self.progress.setRange(0, 0)
        self.progress_title.setText("Analisando páginas e resolvendo links…")
        self.progress_text.setText("Preparando")
        self._set_status("●  Em execução", "warning")
        rate_limit = self.rate_entry.value() or None
        options = ThreadOptions(
            download_path=output_value,
            max_pages=self.pages_entry.value(),
            all_pages=self.all_pages.isChecked(),
            ignore=self._csv(self.ignore_entry.text()),
            include=self._csv(self.include_entry.text()),
            workers=self.workers_entry.value(),
            max_retries=self.retries_entry.value(),
            delay=self.delay_entry.value(),
            connections=self.connections_entry.value(),
            rate_limit=rate_limit * 1024 * 1024 if rate_limit else None,
            dry_run=self.dry_run.isChecked(),
            separate_posts=self.separate_posts.isChecked(),
            flat=self.flat.isChecked(),
            cancel_event=self.cancel_event,
            pause_event=self.pause_event,
        )
        log_file = Path(output_value) / "buidl-gui.log"
        cached = None
        if preview:
            try:
                self.active_preview_key = preview_fingerprint(
                    url, cookie_value or None, options
                )
            except OSError as error:
                self._finish_download(True, False)
                QMessageBox.critical(self, "Não foi possível ler as opções", str(error))
                return
            if self.preview_session is not None:
                if self.preview_session.fingerprint == self.active_preview_key:
                    cached = self.preview_session.prepared
                    self.failures.extend(self.preview_session.warnings)
                    self.progress_title.setText("Reabrindo galeria já carregada…")
                else:
                    self.preview_session = None
        self.current_log_file = log_file
        self.worker_thread = threading.Thread(
            target=self._download_worker,
            args=(
                url,
                cookie_value or None,
                options,
                log_file,
                preview,
                self.selection_queue,
                cached,
            ),
            daemon=True,
            name="buidl-download",
        )
        self.worker_thread.start()

    def _download_worker(
        self,
        url,
        cookies_file,
        options,
        log_file,
        preview=False,
        decisions=None,
        cached=None,
    ) -> None:
        manager = GuiManager(self.events, log_file)
        client = None
        failed = True
        try:
            manager.start()
            client = HttpClient(cookies_file=cookies_file)
            downloader = ThreadDownloader(client, manager, options)
            if not preview:
                failed = downloader.download_thread(url)
            else:
                prepared = (
                    cached if cached is not None else downloader.prepare_thread(url)
                )
                if cached is not None:
                    manager.update_log(
                        event="Galeria reutilizada",
                        details="Lista mantida nesta sessão; sem nova busca da thread.",
                    )
                while (
                    prepared is not None
                    and prepared.plan
                    and not self.cancel_event.is_set()
                ):
                    self.events.put(("preview_ready", prepared, cookies_file))
                    while not self.cancel_event.is_set():
                        try:
                            keys = decisions.get(timeout=0.2)
                        except queue.Empty:
                            continue
                        break
                    if self.cancel_event.is_set():
                        break
                    if keys is PreviewCommand.REFRESH:
                        manager.reset_summary()
                        prepared = downloader.prepare_thread(url)
                        continue
                    manager.reset_summary()
                    failed = downloader.download_prepared(prepared, keys)
                    break
                if (
                    prepared is not None
                    and not prepared.plan
                    and not self.cancel_event.is_set()
                ):
                    self.events.put(
                        (
                            "fatal",
                            "Nenhum arquivo disponível para visualizar. Confira os filtros e o log.",
                        )
                    )
        except Exception as error:  # noqa: BLE001
            manager.update_log(event="Erro inesperado", details=str(error))
            self.events.put(("fatal", str(error)))
        finally:
            if client is not None:
                client.close()
            manager.stop()
            self.events.put(("done", failed, self.cancel_event.is_set()))

    def _poll_events(self) -> None:
        try:
            for _ in range(200):
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    _, stamp, name, details = event
                    self._append_log(stamp, name, details)
                elif kind == "failure":
                    _, stamp, name, details = event
                    self.failures.append((stamp, name, details))
                elif kind == "plan":
                    _, title, total = event
                    self.total_files = total
                    self.progress.setRange(0, 1000)
                    self.progress.setValue(0)
                    self.progress_title.setText(title)
                    self.progress_text.setText(f"0 / {total}")
                elif kind == "progress":
                    _, counts, total = event
                    self._update_counts(counts, total)
                elif kind == "transfer":
                    _, counts, total, units, active = event
                    self._update_counts(
                        counts,
                        total,
                        progress_units=units,
                        active_tasks=active,
                    )
                elif kind == "manager_stopped":
                    _, elapsed, counts = event
                    self._update_counts(counts, self.total_files)
                    self.elapsed_metric.value.setText(self._format_elapsed(elapsed))
                elif kind == "fatal":
                    QMessageBox.critical(self, "Falha no download", event[1])
                elif kind == "done":
                    _, failed, cancelled = event
                    self._finish_download(failed, cancelled)
                elif kind == "preview_ready":
                    _, prepared, cookies_file = event
                    if self.cancel_event.is_set():
                        continue
                    if (
                        self.preview_session is None
                        or self.preview_session.prepared is not prepared
                    ):
                        self.preview_session = PreviewSession(
                            prepared,
                            self.active_preview_key,
                            warnings=list(self.failures),
                        )
                    self.progress.setRange(0, 1000)
                    self.progress.setValue(0)
                    self.progress_title.setText(
                        "Prévia pronta — escolha os arquivos na galeria"
                    )
                    self.progress_text.setText(f"{len(prepared.plan)} encontrados")
                    self._set_status("●  Aguardando seleção", "warning")
                    self.pause_button.setEnabled(False)
                    self.preview_dialog = PreviewDialog(
                        self,
                        prepared,
                        cookies_file,
                        self._confirm_selection,
                        self._cancel_preview,
                        session=self.preview_session,
                        on_refresh=self._refresh_preview,
                    )
                    self.preview_dialog.show()
        except queue.Empty:
            pass
        if self.running:
            self.elapsed_metric.value.setText(
                self._format_elapsed(time.monotonic() - self.started_at)
            )

    def _confirm_selection(self, keys: set[str] | None) -> None:
        self.preview_dialog = None
        self.preview_phase = False
        self.pause_event.set()
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Pausar")
        self._set_status("●  Baixando seleção", "warning")
        self.progress_title.setText("Iniciando os arquivos escolhidos…")
        self.selection_queue.put(keys)

    def _cancel_preview(self) -> None:
        self.preview_dialog = None
        self._cancel()

    def _refresh_preview(self) -> None:
        self.preview_dialog = None
        self.preview_session = None
        self.failures.clear()
        self.pause_event.set()
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Pausar")
        self.progress.setRange(0, 0)
        self.progress_title.setText("Atualizando a thread — buscando páginas e links…")
        self.progress_text.setText("Atualizando")
        self._set_status("●  Atualizando thread", "warning")
        self.selection_queue.put(PreviewCommand.REFRESH)

    def _update_counts(
        self,
        counts: dict[str, int],
        total: int,
        *,
        progress_units: float | None = None,
        active_tasks: int = 0,
    ) -> None:
        self.last_counts = counts
        done = sum(counts.values())
        self.completed_metric.value.setText(str(counts["completed"]))
        self.skipped_metric.value.setText(str(counts["skipped"]))
        self.failed_metric.value.setText(str(counts["failed"]))
        failures = max(counts["failed"], len(self.failures))
        self.failure_button.setText(
            f"Ver falhas ({failures})" if failures else "Ver falhas"
        )
        self.failure_button.setEnabled(bool(failures))
        if total > 0:
            displayed_units = max(float(done), progress_units or 0.0)
            percent = round(min(displayed_units / total, 1) * 100)
            self.progress.setRange(0, 1000)
            self.progress.setValue(round(min(displayed_units / total, 1) * 1000))
            activity = f" · {active_tasks} ativos" if active_tasks else ""
            self.progress_text.setText(f"{done} / {total} · {percent}%{activity}")

    def _append_log(self, stamp: str, event: str, details: str) -> None:
        clean = details.replace("\n", " · ")
        self.log_box.appendPlainText(f"{stamp}  {event:<18} {clean}")
        bar = self.log_box.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_log(self) -> None:
        self.log_box.clear()
        self._update_counts({"completed": 0, "skipped": 0, "failed": 0}, 0)
        self.elapsed_metric.value.setText("00:00")

    def _show_failures(self) -> None:
        if not self.failures:
            QMessageBox.information(
                self, "Detalhes das falhas", "Não há falhas nesta execução."
            )
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Falhas do download ({len(self.failures)})")
        dialog.resize(760, 500)
        dialog.setMinimumSize(560, 380)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            _label(f"{len(self.failures)} arquivo(s) não foram baixados", "section")
        )
        details = QPlainTextEdit(self._failure_report())
        details.setReadOnly(True)
        layout.addWidget(details, 1)
        actions = QHBoxLayout()
        open_log = QPushButton("Abrir log completo")
        open_log.clicked.connect(self._open_log)
        copy = QPushButton("Copiar detalhes")
        copy.clicked.connect(
            lambda: QApplication.clipboard().setText(details.toPlainText())
        )
        close = QPushButton("Fechar")
        close.setProperty("primary", True)
        close.clicked.connect(dialog.accept)
        actions.addWidget(open_log)
        actions.addWidget(copy)
        actions.addStretch(1)
        actions.addWidget(close)
        layout.addLayout(actions)
        dialog.exec()

    def _failure_report(self) -> str:
        return "\n\n".join(
            f"#{index}  {stamp}  {event}\n{details}"
            for index, (stamp, event, details) in enumerate(self.failures, start=1)
        )

    def _open_log(self) -> None:
        if not self.current_log_file.exists():
            QMessageBox.information(
                self,
                "Log ainda não criado",
                f"O arquivo ainda não existe:\n{self.current_log_file}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_log_file)))

    def _toggle_pause(self) -> None:
        if not self.running:
            return
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.setText("Continuar")
            self._set_status("●  Pausado", "warning")
            self._append_log(
                time.strftime("%H:%M:%S"), "Pausado", "Novos arquivos aguardarão."
            )
        else:
            self.pause_event.set()
            self.pause_button.setText("Pausar")
            self._set_status("●  Em execução", "warning")
            self._append_log(
                time.strftime("%H:%M:%S"), "Retomado", "Download continuado."
            )

    def _cancel(self) -> None:
        if not self.running:
            return
        self.cancel_event.set()
        self.pause_event.set()
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelando…")
        self._set_status("●  Cancelando", "warning")

    def _finish_download(self, failed: bool, cancelled: bool) -> None:
        self.running = False
        self.progress.setRange(0, 1000)
        self._set_running_ui(False)
        if cancelled:
            self._set_status("●  Cancelado", "warning")
            self.progress_title.setText(
                "Prévia cancelada — nenhum arquivo foi baixado"
                if self.preview_phase
                else "Download cancelado — partes mantidas para retomada"
            )
        elif failed or self.last_counts["failed"] or self.failures:
            self._set_status("●  Finalizado com falhas", "danger")
            count = max(self.last_counts["failed"], len(self.failures))
            self.progress_title.setText(
                f"Finalizado — {count} falha(s) · abra os detalhes"
            )
        else:
            self._set_status("●  Concluído", "success")
            self.progress_title.setText("Download concluído com sucesso")
            if self.total_files:
                self.progress.setValue(1000)

    def _set_running_ui(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.preview_button.setEnabled(not running)
        self.settings_tabs.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.pause_button.setText("Pausar")
        self.cancel_button.setEnabled(running)
        self.cancel_button.setText("Cancelar")

    def _open_downloads(self) -> None:
        base = Path(self.output_entry.text().strip() or (Path.cwd() / "Downloads"))
        base.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(base)))

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return (
            f"{hours:02}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.running:
            answer = QMessageBox.question(
                self,
                "Download em andamento",
                "Cancelar o download e fechar? As partes serão preservadas para retomada.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.cancel_event.set()
            self.pause_event.set()
        if self.preview_dialog is not None:
            self.preview_dialog.reject()
        event.accept()


def main() -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("BUIDL")
    app.setStyle("Fusion")
    apply_theme(app, True)
    window = BuidlWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
