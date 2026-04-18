from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is importable when running from a checked-out repo.
_here = Path(__file__).resolve().parent
_src = _here / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from spectraglyph import APP_DISPLAY_NAME, ORGANIZATION_NAME
from spectraglyph.gui.i18n import resolve_language, ui_strings
from spectraglyph.gui.main_window import MainWindow
from spectraglyph.utils.config import load_app_settings


APP_QSS = """
QMainWindow, QWidget { background: #14161a; color: #e0e3ea; }
QLabel { color: #c8cdd5; }
QGroupBox {
    border: 1px solid #262a31;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 6px;
    color: #b8bfcb;
    font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
QPushButton {
    background: #232831;
    color: #e2e6ec;
    border: 1px solid #2c323b;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover { background: #2c323d; }
QPushButton:pressed { background: #1d2128; }
QPushButton:disabled { background: #1a1d22; color: #555; border-color: #242830; }
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QTextEdit {
    background: #1b1e24;
    border: 1px solid #2a2f38;
    border-radius: 6px;
    padding: 4px 6px;
    color: #e0e3ea;
    selection-background-color: #3a7bd5;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background: #1b1e24; color: #e0e3ea; selection-background-color: #3a7bd5; }
QRadioButton, QCheckBox { color: #d0d4dc; }
QSlider::groove:horizontal {
    height: 6px; background: #262a31; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #3a7bd5; width: 16px; margin: -5px 0;
    border-radius: 8px; border: 1px solid #2a5fa8;
}
QSlider::handle:horizontal:hover { background: #4a8be5; }
QTabWidget::pane { border: 1px solid #262a31; border-radius: 8px; top: -1px; }
QTabBar::tab {
    padding: 6px 14px; background: #1b1e24; color: #a8b0bc;
    border: 1px solid #262a31; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #232831; color: #e8ecf3; }
QStatusBar { background: #1b1e24; color: #a8b0bc; }
QSplitter::handle { background: #14161a; }
QMenuBar { background: #1b1e24; color: #c8cdd5; }
QMenuBar::item:selected { background: #2c323d; }
QMenu { background: #1b1e24; color: #e0e3ea; border: 1px solid #262a31; }
QMenu::item:selected { background: #3a7bd5; color: white; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    n = os.cpu_count() or 4
    QThreadPool.globalInstance().setMaxThreadCount(max(2, min(6, n)))
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)

    icon_path = _here / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    lang_settings = load_app_settings()
    resolved = resolve_language(lang_settings.ui_language)
    tr = ui_strings(resolved)
    win = MainWindow(tr, lang_settings)
    if icon_path.exists():
        win.setWindowIcon(QIcon(str(icon_path)))
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
