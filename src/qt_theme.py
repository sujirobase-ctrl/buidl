"""Qt 6 design tokens shared by the Windows application and gallery."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

DARK = {
    "bg": "#1B1A17",
    "surface": "#24231F",
    "surface_alt": "#2D2C28",
    "field": "#302F2B",
    "line": "#41403B",
    "text": "#F7F5F2",
    "muted": "#BBB7B0",
    "accent": "#52BDF2",
    "accent_hover": "#78CCF5",
    "on_accent": "#08222E",
    "success": "#4ED2A0",
    "warning": "#F6C35B",
    "danger": "#FF7D91",
}

LIGHT = {
    "bg": "#F3F3F3",
    "surface": "#FFFFFF",
    "surface_alt": "#F8F8F8",
    "field": "#F4F4F4",
    "line": "#D5D5D5",
    "text": "#1A1A1A",
    "muted": "#616161",
    "accent": "#0078D4",
    "accent_hover": "#1989DA",
    "on_accent": "#FFFFFF",
    "success": "#167556",
    "warning": "#906000",
    "danger": "#B32948",
}


def apply_theme(app, dark: bool = True) -> dict[str, str]:
    """Apply a compact, accessible theme without fixed widget dimensions."""
    colors = DARK if dark else LIGHT
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["field"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["field"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["on_accent"]))
    app.setPalette(palette)
    app.setStyleSheet(_stylesheet(colors))
    return colors


def _stylesheet(c: dict[str, str]) -> str:
    return f"""
        * {{
            font-size: 10.5pt;
            color: {c["text"]};
        }}
        QMainWindow, QDialog, QWidget#appRoot {{ background: {c["bg"]}; }}
        QFrame[card="true"] {{
            background: {c["surface"]};
            border: 1px solid {c["line"]};
            border-radius: 8px;
        }}
        *[subtle="true"] {{
            background: {c["surface_alt"]};
            border: 1px solid {c["line"]};
            border-radius: 7px;
        }}
        QLabel[role="title"] {{ font-size: 22pt; font-weight: 700; }}
        QLabel[role="section"] {{ font-size: 13pt; font-weight: 650; }}
        QLabel[role="muted"] {{ color: {c["muted"]}; }}
        QLabel[role="success"] {{ color: {c["success"]}; font-weight: 650; }}
        QLabel[role="warning"] {{ color: {c["warning"]}; font-weight: 650; }}
        QLabel[role="danger"] {{ color: {c["danger"]}; font-weight: 650; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
            background: {c["field"]};
            border: 1px solid {c["line"]};
            border-radius: 5px;
            padding: 9px 11px;
            selection-background-color: {c["accent"]};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
        QComboBox:focus, QPlainTextEdit:focus {{ border: 2px solid {c["accent"]}; }}
        QComboBox::drop-down {{ border: 0; width: 28px; }}
        QComboBox QAbstractItemView {{
            background: {c["surface"]}; border: 1px solid {c["line"]};
            selection-background-color: {c["accent"]}; padding: 6px;
        }}
        QPushButton {{
            background: {c["field"]};
            border: 1px solid {c["line"]};
            border-radius: 5px;
            padding: 9px 14px;
            min-height: 18px;
            font-weight: 600;
        }}
        QPushButton:hover {{ background: {c["surface_alt"]}; border-color: {c["accent"]}; }}
        QPushButton:pressed {{ background: {c["line"]}; }}
        QPushButton:disabled {{ color: {c["muted"]}; background: {c["surface_alt"]}; }}
        QPushButton[primary="true"] {{
            background: {c["accent"]}; color: {c["on_accent"]}; border-color: {c["accent"]};
        }}
        QPushButton[primary="true"]:hover {{ background: {c["accent_hover"]}; }}
        QPushButton[menu="true"] {{
            background: transparent; border: 0; border-radius: 3px;
            padding: 6px 9px; min-height: 16px; font-weight: 400;
        }}
        QPushButton[menu="true"]:hover {{ background: {c["surface_alt"]}; border: 0; }}
        QPushButton[link="true"] {{
            background: transparent; border: 0; color: {c["accent"]};
            padding: 7px 2px; text-align: left; font-weight: 500;
        }}
        QPushButton[link="true"]:hover {{ background: transparent; border: 0; color: {c["accent_hover"]}; }}
        QPushButton[filter="true"]:checked {{
            background: {c["accent"]}; color: {c["on_accent"]}; border-color: {c["accent"]};
        }}
        QPushButton[nav="true"] {{
            background: transparent; border: 0; border-left: 3px solid transparent;
            border-radius: 4px; padding: 10px 12px; text-align: left;
        }}
        QPushButton[nav="true"]:hover {{ background: {c["surface_alt"]}; border-color: transparent; }}
        QPushButton[nav="true"]:checked {{
            background: {c["surface_alt"]}; border-left-color: {c["accent"]};
        }}
        QCheckBox {{ spacing: 9px; }}
        QCheckBox::indicator {{ width: 20px; height: 20px; }}
        QProgressBar {{
            background: {c["field"]}; border: 0; border-radius: 5px; height: 10px;
            text-align: center;
        }}
        QProgressBar::chunk {{ background: {c["accent"]}; border-radius: 5px; }}
        QTabWidget::pane {{ border: 0; background: transparent; }}
        QTabBar::tab {{
            background: transparent; color: {c["muted"]}; padding: 10px 18px;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:selected {{ color: {c["text"]}; border-bottom-color: {c["accent"]}; }}
        QScrollArea {{ border: 0; background: transparent; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {c["line"]}; border-radius: 4px; min-height: 32px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QToolTip {{ background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["line"]}; }}
    """
