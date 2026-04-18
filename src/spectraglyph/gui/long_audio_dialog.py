"""Dialog: long or heavy audio file — load all or a time range only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..core.audio_io import AudioFileInfo
from .i18n import UIStrings


@dataclass
class SegmentChoice:
    """How much of the source file to decode into memory."""

    cancelled: bool = False
    start_s: float = 0.0
    duration_s: float | None = None  # None = from start_s to EOF


class LongAudioDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        tr: UIStrings,
        path: Path,
        info: AudioFileInfo,
    ):
        super().__init__(parent)
        self._tr = tr
        self.setWindowTitle(tr.long_audio_title)
        self.setModal(True)
        self._duration = max(0.01, info.duration_s)
        self._choice = SegmentChoice(cancelled=True)

        head = tr.long_audio_intro.format(
            name=path.name,
            minutes=self._duration / 60.0,
            mb=info.size_bytes / (1024.0 * 1024.0),
        )
        root = QVBoxLayout(self)
        root.addWidget(QLabel(head))

        self._radio_full = QRadioButton(tr.long_audio_load_full)
        self._radio_first = QRadioButton()
        self._radio_range = QRadioButton(tr.long_audio_load_range)

        first_default = min(120.0, self._duration)
        self._first_sec = QDoubleSpinBox()
        self._first_sec.setRange(1.0, max(1.0, self._duration))
        self._first_sec.setDecimals(1)
        self._first_sec.setSuffix(" s")
        self._first_sec.setValue(first_default)
        row_first = QHBoxLayout()
        row_first.addWidget(self._radio_first, 0)
        row_first.addWidget(self._first_sec, 1)

        self._range_start = QDoubleSpinBox()
        self._range_start.setRange(0.0, max(0.0, self._duration - 0.1))
        self._range_start.setDecimals(2)
        self._range_start.setSuffix(" s")
        self._range_len = QDoubleSpinBox()
        self._range_len.setRange(0.1, self._duration)
        self._range_len.setDecimals(2)
        self._range_len.setSuffix(" s")
        self._range_len.setValue(min(60.0, self._duration))

        range_form = QFormLayout()
        range_form.addRow(tr.long_audio_range_start, self._range_start)
        range_form.addRow(tr.long_audio_range_length, self._range_len)

        range_box = QWidget()
        range_box.setLayout(range_form)

        root.addWidget(self._radio_full)
        root.addLayout(row_first)
        root.addWidget(self._radio_range)
        root.addWidget(range_box)

        self._radio_full.setChecked(True)
        self._sync_first_label()
        self._first_sec.valueChanged.connect(self._sync_first_label)
        self._range_start.valueChanged.connect(self._on_range_start_changed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _sync_first_label(self) -> None:
        self._radio_first.setText(
            self._tr.long_audio_load_first_n.format(sec=self._first_sec.value())
        )

    def _on_range_start_changed(self, v: float) -> None:
        max_len = max(0.1, self._duration - v)
        self._range_len.setMaximum(max_len)
        if self._range_len.value() > max_len:
            self._range_len.setValue(max_len)

    def _accept(self) -> None:
        if self._radio_full.isChecked():
            self._choice = SegmentChoice(
                cancelled=False, start_s=0.0, duration_s=None
            )
        elif self._radio_first.isChecked():
            n = float(self._first_sec.value())
            self._choice = SegmentChoice(
                cancelled=False, start_s=0.0, duration_s=min(n, self._duration)
            )
        else:
            st = float(self._range_start.value())
            ln = float(self._range_len.value())
            if st + ln > self._duration + 1e-6:
                ln = max(0.1, self._duration - st)
            self._choice = SegmentChoice(
                cancelled=False, start_s=st, duration_s=ln
            )
        self.accept()

    def choice(self) -> SegmentChoice:
        return self._choice
