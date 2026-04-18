from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ..utils.config import normalized_existing_dir
from .i18n import UIStrings, export_filter_all


def ask_export_path(
    parent: QWidget,
    tr: UIStrings,
    suggested_name: str = "watermarked",
    *,
    initial_dir: str = "",
) -> str | None:
    d = normalized_existing_dir(initial_dir)
    start_path = (
        str(Path(d) / f"{suggested_name}.wav") if d else f"{suggested_name}.wav"
    )
    path, _filter = QFileDialog.getSaveFileName(
        parent,
        tr.export_dialog_title,
        start_path,
        export_filter_all(tr),
    )
    if not path:
        return None
    ext = Path(path).suffix.lower()
    if ext in {".mp3", ".m4a", ".aac", ".ogg", ".opus"}:
        if not _confirm_lossy(parent, tr, ext):
            return None
    return path


def _confirm_lossy(parent: QWidget, tr: UIStrings, ext: str) -> bool:
    fmt = ext.lstrip(".").upper()
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(tr.lossy_title)
    box.setText(tr.lossy_body.format(fmt=fmt))
    box.setStandardButtons(QMessageBox.Save | QMessageBox.Cancel)
    box.setDefaultButton(QMessageBox.Cancel)
    return box.exec() == QMessageBox.Save
