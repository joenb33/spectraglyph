from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .. import APP_DISPLAY_NAME
from ..core.audio_io import AudioData, load_audio, save_audio
from ..core.image_processor import MaskOptions
from ..core.spectrogram_renderer import SpectrogramImage, compute_spectrogram
from ..core.watermark import WatermarkParams, embed_watermark, recommend_freq_range
from ..utils.config import Preset, Presets
from ..utils.worker import Worker, pool
from .controls_panel import ControlsPanel, WatermarkSettings
from .export_dialog import ask_export_path
from .image_panel import SourcePanel
from .spectrogram_view import SpectrogramView

AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1400, 880)
        self.setAcceptDrops(True)

        self._audio: Optional[AudioData] = None
        self._audio_path: Optional[str] = None
        self._spec_original: Optional[SpectrogramImage] = None
        self._spec_preview: Optional[SpectrogramImage] = None
        self._presets = Presets.load()
        self._pending_preview = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(180)
        self._preview_timer.timeout.connect(self._rebuild_preview)

        self._build_ui()
        self._wire_signals()
        self._update_audio_label()

    # ---------- UI ----------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 4)
        root.setSpacing(6)

        top = QHBoxLayout()
        self._load_audio_btn = QPushButton("🎵  Välj ljudfil…")
        self._load_audio_btn.setMinimumHeight(34)
        self._load_audio_btn.clicked.connect(self._pick_audio)
        self._audio_label = QLabel("Ingen ljudfil laddad")
        self._audio_label.setStyleSheet("color: #889; padding-left: 8px;")
        top.addWidget(self._load_audio_btn)
        top.addWidget(self._audio_label, 1)

        self._toggle_preview_btn = QPushButton("👁  Förhandsgranska vattenmärke")
        self._toggle_preview_btn.setCheckable(True)
        self._toggle_preview_btn.setChecked(True)
        self._toggle_preview_btn.toggled.connect(lambda _: self._schedule_preview())
        top.addWidget(self._toggle_preview_btn)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.spectrogram_view = SpectrogramView()
        splitter.addWidget(self.spectrogram_view)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.source_panel = SourcePanel()
        right_layout.addWidget(self.source_panel, 1)
        self.controls_panel = ControlsPanel()
        right_layout.addWidget(self.controls_panel, 2)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 520])

        root.addWidget(splitter, 1)

        self.setStatusBar(QStatusBar())
        self._hint("Dra in en ljudfil och en bild – sedan knappen 'Exportera'.")

    def _wire_signals(self):
        self.controls_panel.settings_changed.connect(self._on_settings_changed)
        self.controls_panel.export_requested.connect(self._export)
        self.controls_panel.save_preset_requested.connect(self._save_preset)
        self.controls_panel.reset_requested.connect(self._reset_settings)
        self.controls_panel.copy_view_guide_requested.connect(self._copy_view_guide)
        self.source_panel.mask_changed.connect(self._on_mask_changed)
        self.spectrogram_view.region_changed.connect(self._on_region_dragged)

    # ---------- Drag and drop ----------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = Path(path).suffix.lower()
            if ext in AUDIO_EXTS:
                self._load_audio(path)
            elif ext in IMAGE_EXTS:
                self.source_panel.load_image_path(path)
        event.acceptProposedAction()

    # ---------- Audio loading ----------

    def _pick_audio(self):
        exts = " ".join(f"*{e}" for e in sorted(AUDIO_EXTS))
        path, _ = QFileDialog.getOpenFileName(
            self, "Välj ljudfil", "", f"Ljudfiler ({exts})"
        )
        if path:
            self._load_audio(path)

    def _load_audio(self, path: str):
        self._hint(f"Läser in {Path(path).name}…")
        w = Worker(load_audio, path)
        w.signals.finished.connect(lambda a: self._on_audio_loaded(a, path))
        w.signals.failed.connect(lambda msg: self._error(f"Kunde inte läsa ljudet: {msg}"))
        pool().start(w)

    def _on_audio_loaded(self, audio: AudioData, path: str):
        self._audio = audio
        self._audio_path = path
        self._update_audio_label()
        self.controls_panel.apply_audio_info(audio.duration_s, audio.sample_rate)
        lo, hi = recommend_freq_range(audio.sample_rate, self.controls_panel.settings().mode)
        s = self.controls_panel.settings()
        s.freq_min_hz, s.freq_max_hz = lo, hi
        s.duration_s = min(s.duration_s, audio.duration_s)
        self.controls_panel.set_settings(s)
        self._hint(f"Ljud: {Path(path).name} ({audio.sample_rate} Hz, {audio.duration_s:.1f}s)")
        self.controls_panel.set_export_enabled(True)
        w = Worker(compute_spectrogram, audio.samples, audio.sample_rate)
        w.signals.finished.connect(self._on_spec_ready)
        w.signals.failed.connect(lambda m: self._error(f"Spektrogram-fel: {m}"))
        pool().start(w)

    def _on_spec_ready(self, spec: SpectrogramImage):
        self._spec_original = spec
        self.spectrogram_view.set_spectrogram(spec)
        self._apply_region_from_settings()
        self._schedule_preview()

    def _update_audio_label(self):
        if self._audio is None:
            self._audio_label.setText("Ingen ljudfil laddad")
            return
        self._audio_label.setText(
            f"{Path(self._audio_path).name}  •  "
            f"{self._audio.sample_rate} Hz  •  "
            f"{self._audio.duration_s:.2f}s  •  "
            f"{self._audio.channels} ch"
        )

    # ---------- Settings / mask / region ----------

    def _on_settings_changed(self, s: WatermarkSettings):
        # Keep bg options on source panel in sync.
        self.source_panel.set_bg_options(
            MaskOptions(mode=s.bg_mode, threshold=s.bg_threshold, invert=s.invert)
        )
        self._apply_region_from_settings()
        self._schedule_preview()

    def _on_mask_changed(self, _mask):
        self._schedule_preview()

    def _on_region_dragged(self, start_s: float, end_s: float, f_min: float, f_max: float):
        self.controls_panel.apply_region_from_view(start_s, end_s, f_min, f_max)

    def _apply_region_from_settings(self):
        s = self.controls_panel.settings()
        self.spectrogram_view.set_watermark_region(
            s.start_s, s.start_s + s.duration_s, s.freq_min_hz, s.freq_max_hz
        )

    # ---------- Preview ----------

    def _schedule_preview(self):
        self._preview_timer.start()

    def _rebuild_preview(self):
        if self._audio is None or self._spec_original is None:
            return
        if not self._toggle_preview_btn.isChecked():
            self.spectrogram_view.set_spectrogram(self._spec_original)
            return
        mask = self.source_panel.current_mask()
        if mask is None:
            self.spectrogram_view.set_spectrogram(self._spec_original)
            return
        if self._pending_preview:
            return  # simple debounce — timer will fire again
        self._pending_preview = True
        s = self.controls_panel.settings()
        params = _settings_to_params(s)
        audio = self._audio.samples
        sr = self._audio.sample_rate
        w = Worker(_compute_preview, audio, sr, mask, params)
        w.signals.finished.connect(self._on_preview_ready)
        w.signals.failed.connect(lambda m: self._preview_failed(m))
        pool().start(w)

    def _on_preview_ready(self, spec: SpectrogramImage):
        self._pending_preview = False
        self._spec_preview = spec
        self.spectrogram_view.set_spectrogram(spec)
        self._apply_region_from_settings()

    def _preview_failed(self, msg: str):
        self._pending_preview = False
        self._hint(f"Preview-fel: {msg}")

    # ---------- Export ----------

    def _export(self):
        if self._audio is None:
            return
        mask = self.source_panel.current_mask()
        if mask is None:
            self._error("Ladda eller skriv något i Bild/Text först.")
            return
        suggested = Path(self._audio_path or "watermarked").stem + "_watermarked"
        path = ask_export_path(self, suggested)
        if not path:
            return
        params = _settings_to_params(self.controls_panel.settings())
        self._hint("Exporterar…")
        self.controls_panel.set_export_enabled(False)
        audio = self._audio

        def do_export():
            out = embed_watermark(audio.samples, audio.sample_rate, mask, params)
            save_audio(path, AudioData(samples=out, sample_rate=audio.sample_rate))
            return path

        w = Worker(do_export)
        w.signals.finished.connect(self._on_export_done)
        w.signals.failed.connect(lambda m: (self._error(f"Exportfel: {m}"), self.controls_panel.set_export_enabled(True)))
        pool().start(w)

    def _on_export_done(self, path: str):
        self.controls_panel.set_export_enabled(True)
        self._hint(f"Exporterad: {path}")
        QMessageBox.information(
            self,
            "Klart",
            f"Sparad till:\n{path}\n\nÖppna filen i Audacity eller Spek för att se vattenmärket.",
        )

    # ---------- Presets ----------

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Spara preset", "Namn:")
        if not ok or not name.strip():
            return
        s = self.controls_panel.settings()
        preset = Preset(
            name=name.strip(),
            mode=s.mode,
            start_s=s.start_s,
            duration_s=s.duration_s,
            freq_min_hz=s.freq_min_hz,
            freq_max_hz=s.freq_max_hz,
            strength_db=s.strength_db,
            bg_mode=s.bg_mode,
            bg_threshold=s.bg_threshold,
            invert=s.invert,
        )
        self._presets.items = [p for p in self._presets.items if p.name != preset.name]
        self._presets.items.append(preset)
        self._presets.save()
        self._hint(f"Preset '{preset.name}' sparad.")

    def _reset_settings(self):
        s = WatermarkSettings()
        if self._audio is not None:
            lo, hi = recommend_freq_range(self._audio.sample_rate, "invisible")
            s.freq_min_hz = lo
            s.freq_max_hz = hi
            s.duration_s = min(3.0, self._audio.duration_s)
        self.controls_panel.set_settings(s)

    def _copy_view_guide(self):
        s = self.controls_panel.settings()
        guide = (
            "Så här ser du vattenmärket i ljudfilen:\n\n"
            "1. Öppna filen i Audacity (eller Spek / Sonic Visualiser).\n"
            "2. Välj spår-menyn → Spectrogram view.\n"
            "3. Inställningar:\n"
            "   • FFT-storlek: 4096\n"
            "   • Fönster: Hann\n"
            "   • Dynamiskt omfång: 80 dB\n"
            f"4. Tidsposition: {s.start_s:.2f}s – {s.start_s + s.duration_s:.2f}s\n"
            f"5. Frekvensomfång: {int(s.freq_min_hz)} Hz – {int(s.freq_max_hz)} Hz"
        )
        QGuiApplication.clipboard().setText(guide)
        self._hint("View-guide kopierad till urklipp.")

    # ---------- Helpers ----------

    def _hint(self, msg: str):
        self.statusBar().showMessage(msg, 8000)

    def _error(self, msg: str):
        self.statusBar().showMessage(msg, 10000)
        QMessageBox.critical(self, "Fel", msg)


def _settings_to_params(s: WatermarkSettings) -> WatermarkParams:
    return WatermarkParams(
        mode=s.mode,  # type: ignore[arg-type]
        start_s=s.start_s,
        duration_s=s.duration_s,
        freq_min_hz=s.freq_min_hz,
        freq_max_hz=s.freq_max_hz,
        strength_db=s.strength_db,
    )


def _compute_preview(audio: np.ndarray, sr: int, mask: np.ndarray, params: WatermarkParams) -> SpectrogramImage:
    out = embed_watermark(audio, sr, mask, params)
    return compute_spectrogram(out, sr)
