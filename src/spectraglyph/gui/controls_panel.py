from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .i18n import UIStrings


@dataclass
class WatermarkSettings:
    mode: str = "invisible"
    start_s: float = 0.0
    duration_s: float = 3.0
    freq_min_hz: float = 15_000.0
    freq_max_hz: float = 20_000.0
    strength_db: float = -24.0
    bg_mode: str = "alpha"
    bg_threshold: float = 0.15
    invert: bool = False
    # Chroma key in RGB 0-255 used when bg_mode == "chroma"; default green-screen.
    chroma_rgb: tuple[int, int, int] = (0, 255, 0)


class ControlsPanel(QWidget):
    settings_changed = Signal(object)  # emits WatermarkSettings
    export_requested = Signal()
    save_preset_requested = Signal()
    reset_requested = Signal()
    copy_view_guide_requested = Signal()

    def __init__(self, tr: UIStrings, parent=None):
        super().__init__(parent)
        self._tr = tr
        self._audio_duration_s = 60.0
        self._sr = 48_000
        self._settings = WatermarkSettings()
        self._build()
        self._emit()

    # ---------- Public API ----------

    def set_strings(self, tr: UIStrings) -> None:
        self._tr = tr
        self._mode_box.setTitle(tr.group_mode)
        self.mode_invisible.setText(tr.mode_invisible)
        self.mode_full.setText(tr.mode_full)
        self._params_box.setTitle(tr.group_placement)
        self._label_start.setText(tr.label_start)
        self._label_dur.setText(tr.label_duration)
        self._label_fmin.setText(tr.label_fmin)
        self._label_fmax.setText(tr.label_fmax)
        self._label_strength.setText(tr.label_strength)
        self._bg_box.setTitle(tr.group_bg)
        self._fill_bg_combo(tr)
        self._label_method.setText(tr.label_method)
        self._label_thr.setText(tr.label_threshold)
        self.invert_checkbox.setText(tr.invert)
        self.reset_btn.setText(tr.reset)
        self.preset_btn.setText(tr.save_preset)
        self.copy_btn.setText(tr.view_guide_btn)
        self.copy_btn.setToolTip(tr.view_guide_tooltip)
        self.export_btn.setText(tr.export)
        self.export_btn.setToolTip(tr.export_tooltip)
        self.chroma_btn.setText(tr.chroma_color_btn)
        self.chroma_btn.setToolTip(
            tr.chroma_current_tooltip.format(rgb=_rgb_hex(self._settings.chroma_rgb))
        )

    def settings(self) -> WatermarkSettings:
        return self._settings

    def apply_audio_info(self, duration_s: float, sr: int):
        self._audio_duration_s = max(duration_s, 0.1)
        self._sr = sr
        self.start_spin.setMaximum(self._audio_duration_s - 0.05)
        self.dur_spin.setMaximum(self._audio_duration_s)
        nyq = sr / 2.0
        self.fmin_spin.setMaximum(nyq - 100)
        self.fmax_spin.setMaximum(nyq - 50)
        if self._settings.freq_max_hz > nyq - 100:
            self.fmax_spin.setValue(max(1000, nyq - 500))

    def set_settings(self, s: WatermarkSettings):
        self._settings = s
        self._sync_widgets_from_settings()

    # ---------- UI ----------

    def _fill_bg_combo(self, tr: UIStrings) -> None:
        cur = self._settings.bg_mode
        if self.bg_combo.count() > 0:
            data = self.bg_combo.currentData()
            if data is not None:
                cur = data
        self.bg_combo.blockSignals(True)
        self.bg_combo.clear()
        for label, key in [
            (tr.bg_alpha, "alpha"),
            (tr.bg_auto, "auto"),
            (tr.bg_white, "remove_white"),
            (tr.bg_black, "remove_black"),
            (tr.bg_chroma, "chroma"),
            (tr.bg_luminance, "luminance"),
        ]:
            self.bg_combo.addItem(label, key)
        idx = self.bg_combo.findData(cur)
        if idx < 0:
            idx = 0
        self.bg_combo.setCurrentIndex(idx)
        self.bg_combo.blockSignals(False)

    def _build(self):
        tr = self._tr
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 10)

        # --- Mode group ---
        self._mode_box = QGroupBox(tr.group_mode)
        mode_box = self._mode_box
        mode_layout = QHBoxLayout(mode_box)
        self.mode_invisible = QRadioButton(tr.mode_invisible)
        self.mode_full = QRadioButton(tr.mode_full)
        self.mode_invisible.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.mode_invisible)
        self._mode_group.addButton(self.mode_full)
        self.mode_invisible.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_invisible)
        mode_layout.addWidget(self.mode_full)
        mode_layout.addStretch(1)
        root.addWidget(mode_box)

        # --- Time/Freq/Strength ---
        self._params_box = QGroupBox(tr.group_placement)
        params_box = self._params_box
        form = QFormLayout(params_box)
        form.setContentsMargins(10, 6, 10, 6)

        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 60.0)
        self.start_spin.setDecimals(2)
        self.start_spin.setSingleStep(0.1)
        self.start_spin.setSuffix(" s")
        self.start_spin.setValue(0.0)
        self.start_spin.valueChanged.connect(self._on_spin_changed)
        self._label_start = QLabel(tr.label_start)
        form.addRow(self._label_start, self.start_spin)

        self.dur_spin = QDoubleSpinBox()
        self.dur_spin.setRange(0.1, 60.0)
        self.dur_spin.setDecimals(2)
        self.dur_spin.setSingleStep(0.1)
        self.dur_spin.setSuffix(" s")
        self.dur_spin.setValue(3.0)
        self.dur_spin.valueChanged.connect(self._on_spin_changed)
        self._label_dur = QLabel(tr.label_duration)
        form.addRow(self._label_dur, self.dur_spin)

        self.fmin_spin = QDoubleSpinBox()
        self.fmin_spin.setRange(10.0, 24_000.0)
        self.fmin_spin.setDecimals(0)
        self.fmin_spin.setSingleStep(250)
        self.fmin_spin.setSuffix(" Hz")
        self.fmin_spin.setValue(15_000)
        self.fmin_spin.valueChanged.connect(self._on_spin_changed)
        self._label_fmin = QLabel(tr.label_fmin)
        form.addRow(self._label_fmin, self.fmin_spin)

        self.fmax_spin = QDoubleSpinBox()
        self.fmax_spin.setRange(20.0, 24_000.0)
        self.fmax_spin.setDecimals(0)
        self.fmax_spin.setSingleStep(250)
        self.fmax_spin.setSuffix(" Hz")
        self.fmax_spin.setValue(20_000)
        self.fmax_spin.valueChanged.connect(self._on_spin_changed)
        self._label_fmax = QLabel(tr.label_fmax)
        form.addRow(self._label_fmax, self.fmax_spin)

        # Strength slider (-60 .. -6 dB)
        strength_row = QHBoxLayout()
        self.strength_slider = QSlider(Qt.Horizontal)
        self.strength_slider.setRange(-60, -6)
        self.strength_slider.setValue(-24)
        self.strength_slider.setTickInterval(6)
        self.strength_slider.setTickPosition(QSlider.TicksBelow)
        self.strength_label = QLabel("-24 dB")
        self.strength_label.setMinimumWidth(60)
        self.strength_slider.valueChanged.connect(self._on_strength_changed)
        strength_row.addWidget(self.strength_slider, 1)
        strength_row.addWidget(self.strength_label)
        self._label_strength = QLabel(tr.label_strength)
        form.addRow(self._label_strength, strength_row)

        root.addWidget(params_box)

        # --- Background removal ---
        self._bg_box = QGroupBox(tr.group_bg)
        bg_box = self._bg_box
        bg_layout = QFormLayout(bg_box)
        bg_layout.setContentsMargins(10, 6, 10, 6)
        self.bg_combo = QComboBox()
        self._fill_bg_combo(tr)
        self.bg_combo.currentIndexChanged.connect(self._on_bg_changed)
        self._label_method = QLabel(tr.label_method)
        method_row = QHBoxLayout()
        method_row.setContentsMargins(0, 0, 0, 0)
        method_row.addWidget(self.bg_combo, 1)
        self.chroma_btn = QPushButton(tr.chroma_color_btn)
        self.chroma_btn.setToolTip(
            tr.chroma_current_tooltip.format(rgb=_rgb_hex(self._settings.chroma_rgb))
        )
        self.chroma_btn.clicked.connect(self._pick_chroma_color)
        self._style_chroma_btn()
        method_row.addWidget(self.chroma_btn)
        bg_layout.addRow(self._label_method, method_row)

        self.bg_thresh_slider = QSlider(Qt.Horizontal)
        self.bg_thresh_slider.setRange(1, 50)
        self.bg_thresh_slider.setValue(15)
        self.bg_thresh_slider.valueChanged.connect(self._on_bg_changed)
        self.bg_thresh_label = QLabel("0.15")
        self.bg_thresh_label.setMinimumWidth(42)
        thr_row = QHBoxLayout()
        thr_row.addWidget(self.bg_thresh_slider, 1)
        thr_row.addWidget(self.bg_thresh_label)
        self._label_thr = QLabel(tr.label_threshold)
        bg_layout.addRow(self._label_thr, thr_row)

        self.invert_checkbox = QRadioButton(tr.invert)
        self.invert_checkbox.setAutoExclusive(False)
        self.invert_checkbox.toggled.connect(self._on_bg_changed)
        bg_layout.addRow(" ", self.invert_checkbox)

        root.addWidget(bg_box)
        root.addStretch(1)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton(tr.reset)
        self.reset_btn.clicked.connect(self.reset_requested.emit)
        self.preset_btn = QPushButton(tr.save_preset)
        self.preset_btn.clicked.connect(self.save_preset_requested.emit)
        self.copy_btn = QPushButton(tr.view_guide_btn)
        self.copy_btn.setToolTip(tr.view_guide_tooltip)
        self.copy_btn.clicked.connect(self.copy_view_guide_requested.emit)
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.preset_btn)
        btn_row.addWidget(self.copy_btn)
        btn_row.addStretch(1)
        self.export_btn = QPushButton(tr.export)
        self.export_btn.setToolTip(tr.export_tooltip)
        self.export_btn.setMinimumWidth(160)
        self.export_btn.setStyleSheet(
            "QPushButton { background: #3a7bd5; color: white; font-weight: 600;"
            " padding: 8px 16px; border-radius: 6px; }"
            " QPushButton:hover { background: #4a8be5; }"
            " QPushButton:disabled { background: #3a3e46; color: #888; }"
        )
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.export_btn.setEnabled(False)
        btn_row.addWidget(self.export_btn)
        root.addLayout(btn_row)

    def set_export_enabled(self, enabled: bool):
        self.export_btn.setEnabled(enabled)

    # ---------- Slots ----------

    def _on_mode_changed(self):
        self._settings.mode = "invisible" if self.mode_invisible.isChecked() else "full_range"
        if self._settings.mode == "invisible":
            self.fmin_spin.setValue(15_000)
            self.fmax_spin.setValue(min(20_000, self._sr / 2 - 500))
        else:
            self.fmin_spin.setValue(300)
            self.fmax_spin.setValue(min(8_000, self._sr / 2 - 500))
        self._emit()

    def _on_spin_changed(self, *_):
        if self.fmin_spin.value() >= self.fmax_spin.value():
            self.fmax_spin.setValue(self.fmin_spin.value() + 500)
        max_end = self._audio_duration_s
        if self.start_spin.value() + self.dur_spin.value() > max_end:
            self.dur_spin.setValue(max(0.1, max_end - self.start_spin.value()))
        self._settings.start_s = self.start_spin.value()
        self._settings.duration_s = self.dur_spin.value()
        self._settings.freq_min_hz = self.fmin_spin.value()
        self._settings.freq_max_hz = self.fmax_spin.value()
        self._emit()

    def _on_strength_changed(self, val: int):
        self.strength_label.setText(f"{val} dB")
        self._settings.strength_db = float(val)
        self._emit()

    def _on_bg_changed(self, *_):
        self._settings.bg_mode = self.bg_combo.currentData()
        thr = self.bg_thresh_slider.value() / 100.0
        self.bg_thresh_label.setText(f"{thr:.2f}")
        self._settings.bg_threshold = thr
        self._settings.invert = self.invert_checkbox.isChecked()
        self._update_chroma_btn_visible()
        self._emit()

    def _update_chroma_btn_visible(self) -> None:
        self.chroma_btn.setVisible(self._settings.bg_mode == "chroma")

    def _style_chroma_btn(self) -> None:
        r, g, b = self._settings.chroma_rgb
        # Pick a readable foreground against the sampled color.
        fg = "#000" if (r * 0.299 + g * 0.587 + b * 0.114) > 140 else "#fff"
        self.chroma_btn.setStyleSheet(
            f"QPushButton {{ background: rgb({r},{g},{b}); color: {fg};"
            " border: 1px solid #555; padding: 2px 10px; border-radius: 3px; }"
        )

    def _pick_chroma_color(self) -> None:
        r, g, b = self._settings.chroma_rgb
        initial = QColor(r, g, b)
        color = QColorDialog.getColor(initial, self, self._tr.chroma_pick_title)
        if not color.isValid():
            return
        self._settings.chroma_rgb = (color.red(), color.green(), color.blue())
        self._style_chroma_btn()
        self.chroma_btn.setToolTip(
            self._tr.chroma_current_tooltip.format(rgb=_rgb_hex(self._settings.chroma_rgb))
        )
        self._emit()

    def apply_region_from_view(self, start_s: float, end_s: float, f_min: float, f_max: float):
        """Called when the user drags the ROI in the spectrogram view."""
        self.start_spin.blockSignals(True)
        self.dur_spin.blockSignals(True)
        self.fmin_spin.blockSignals(True)
        self.fmax_spin.blockSignals(True)
        self.start_spin.setValue(max(0.0, start_s))
        self.dur_spin.setValue(max(0.1, end_s - start_s))
        self.fmin_spin.setValue(max(10.0, f_min))
        self.fmax_spin.setValue(max(self.fmin_spin.value() + 500, f_max))
        self.start_spin.blockSignals(False)
        self.dur_spin.blockSignals(False)
        self.fmin_spin.blockSignals(False)
        self.fmax_spin.blockSignals(False)
        self._settings.start_s = self.start_spin.value()
        self._settings.duration_s = self.dur_spin.value()
        self._settings.freq_min_hz = self.fmin_spin.value()
        self._settings.freq_max_hz = self.fmax_spin.value()
        self._emit()

    def _sync_widgets_from_settings(self):
        s = self._settings
        self.mode_invisible.setChecked(s.mode == "invisible")
        self.mode_full.setChecked(s.mode == "full_range")
        self.start_spin.setValue(s.start_s)
        self.dur_spin.setValue(s.duration_s)
        self.fmin_spin.setValue(s.freq_min_hz)
        self.fmax_spin.setValue(s.freq_max_hz)
        self.strength_slider.setValue(int(s.strength_db))
        idx = self.bg_combo.findData(s.bg_mode)
        if idx >= 0:
            self.bg_combo.setCurrentIndex(idx)
        self.bg_thresh_slider.setValue(int(round(s.bg_threshold * 100)))
        self.invert_checkbox.setChecked(s.invert)
        self._style_chroma_btn()
        self._update_chroma_btn_visible()
        self._emit()

    def _emit(self):
        self.settings_changed.emit(self._settings)


def _rgb_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"
