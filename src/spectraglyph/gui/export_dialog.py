from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

LOSSLESS_FILTER = "WAV (*.wav);;FLAC (*.flac)"
LOSSY_FILTER = "MP3 (*.mp3);;AAC (*.m4a)"
ALL_FILTER = f"{LOSSLESS_FILTER};;{LOSSY_FILTER}"


def ask_export_path(parent: QWidget, suggested_name: str = "watermarked") -> str | None:
    path, _filter = QFileDialog.getSaveFileName(
        parent,
        "Exportera ljudfil",
        f"{suggested_name}.wav",
        ALL_FILTER,
    )
    if not path:
        return None
    ext = Path(path).suffix.lower()
    if ext in {".mp3", ".m4a", ".aac", ".ogg", ".opus"}:
        if not _confirm_lossy(parent, ext):
            return None
    return path


def _confirm_lossy(parent: QWidget, ext: str) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("Lossy format")
    box.setText(
        f"Du valde {ext.upper()[1:]}-format.\n\n"
        "Komprimering med förlust (MP3/AAC) kan dämpa eller ta bort höga "
        "frekvenser och därmed påverka eller förstöra vattenmärket. "
        "WAV eller FLAC rekommenderas starkt för att behålla bilden klart synlig.\n\n"
        "Vill du exportera ändå?"
    )
    box.setStandardButtons(QMessageBox.Save | QMessageBox.Cancel)
    box.setDefaultButton(QMessageBox.Cancel)
    return box.exec() == QMessageBox.Save
