from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .. import APP_DISPLAY_NAME
from ..core.audio_io import (
    LARGE_FILE_DURATION_S,
    LARGE_FILE_SIZE_BYTES,
    AudioData,
    AudioFileInfo,
    load_audio,
    probe_audio_file,
    save_audio,
)
from ..core.image_processor import MaskOptions
from ..core.spectrogram_renderer import SpectrogramImage, compute_spectrogram
from ..core.watermark import WatermarkParams, embed_watermark, recommend_freq_range
from ..utils.config import (
    AppSettings,
    Preset,
    Presets,
    normalized_existing_dir,
    save_app_settings,
)
from ..utils.worker import Worker, pool
from .controls_panel import ControlsPanel, WatermarkSettings
from .export_dialog import ask_export_path
from .i18n import UIStrings, resolve_language, ui_strings
from .image_panel import SourcePanel
from .long_audio_dialog import LongAudioDialog
from .spectrogram_view import SpectrogramView

AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class MainWindow(QMainWindow):
    def __init__(self, tr: UIStrings, lang_settings: AppSettings):
        super().__init__()
        self._tr = tr
        self._lang_settings = lang_settings
        self.setWindowTitle(APP_DISPLAY_NAME)
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
        self._busy_depth = 0
        self._splitter: QSplitter | None = None
        self._load_progress: QProgressDialog | None = None
        self._last_file_info: AudioFileInfo | None = None
        self._last_load_start_s: float = 0.0
        self._last_load_duration_param: float | None = None

        self._build_ui()
        self._restore_window_state()
        self._setup_shortcuts()
        self._wire_signals()
        self._update_audio_label()

    # ---------- UI ----------

    def _build_ui(self):
        tr = self._tr
        self._build_language_menu()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 4)
        root.setSpacing(6)

        top = QHBoxLayout()
        self._load_audio_btn = QPushButton(tr.choose_audio)
        self._load_audio_btn.setToolTip(tr.choose_audio_tooltip)
        self._load_audio_btn.setMinimumHeight(34)
        self._load_audio_btn.clicked.connect(self._pick_audio)
        self._audio_label = QLabel(tr.no_audio_loaded)
        self._audio_label.setWordWrap(True)
        self._audio_label.setStyleSheet("color: #889; padding-left: 8px;")
        top.addWidget(self._load_audio_btn)
        top.addWidget(self._audio_label, 1)

        self._toggle_preview_btn = QPushButton(tr.preview_watermark)
        self._toggle_preview_btn.setCheckable(True)
        self._toggle_preview_btn.setChecked(True)
        self._toggle_preview_btn.toggled.connect(lambda _: self._schedule_preview())
        top.addWidget(self._toggle_preview_btn)
        root.addLayout(top)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        self.spectrogram_view = SpectrogramView(tr)
        self._splitter.addWidget(self.spectrogram_view)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.source_panel = SourcePanel(tr, self._lang_settings)
        right_layout.addWidget(self.source_panel, 1)
        self.controls_panel = ControlsPanel(tr)
        right_layout.addWidget(self.controls_panel, 2)
        self._splitter.addWidget(right)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes(self._lang_settings.splitter_sizes)

        root.addWidget(self._splitter, 1)

        self.setStatusBar(QStatusBar())
        self._hint(tr.status_hint_drop)

        self._build_help_menu()

    def _build_help_menu(self) -> None:
        tr = self._tr
        help_menu = self.menuBar().addMenu(tr.menu_help)
        act = QAction(tr.shortcuts_action, self)
        act.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(act)

    def _show_shortcuts_dialog(self) -> None:
        tr = self._tr
        QMessageBox.information(
            self, tr.shortcuts_dialog_title, tr.shortcuts_dialog_body
        )

    def _build_language_menu(self) -> None:
        tr = self._tr
        view_menu = self.menuBar().addMenu(tr.menu_view)
        lang_menu = view_menu.addMenu(tr.menu_language)
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        for pref, label in (
            ("auto", tr.lang_auto),
            ("sv", tr.lang_sv),
            ("en", tr.lang_en),
        ):
            act = QAction(label, self)
            act.setData(pref)
            act.setCheckable(True)
            self._lang_group.addAction(act)
            lang_menu.addAction(act)
            if self._lang_settings.ui_language == pref:
                act.setChecked(True)
        self._lang_group.triggered.connect(self._on_language_selected)

    def _on_language_selected(self, action: QAction) -> None:
        pref = action.data()
        if pref is None or pref == self._lang_settings.ui_language:
            return
        self._lang_settings.ui_language = pref
        save_app_settings(self._lang_settings)
        resolved = resolve_language(pref)
        self._tr = ui_strings(resolved)
        self._apply_strings()

    def _apply_strings(self) -> None:
        tr = self._tr
        self.menuBar().clear()
        self._build_language_menu()
        self._build_help_menu()

        self._load_audio_btn.setText(tr.choose_audio)
        self._load_audio_btn.setToolTip(tr.choose_audio_tooltip)
        self._toggle_preview_btn.setText(tr.preview_watermark)
        self.source_panel.set_strings(tr)
        self.controls_panel.set_strings(tr)
        self.spectrogram_view.set_strings(tr)
        self._update_audio_label()
        self._hint(tr.status_hint_drop)

    def _restore_window_state(self) -> None:
        g = self._lang_settings.window_geometry_b64
        if g:
            try:
                raw = base64.b64decode(g.encode("ascii"))
                self.restoreGeometry(QByteArray(raw))
            except (TypeError, ValueError, binascii.Error, UnicodeError):
                self.resize(1400, 880)
        else:
            self.resize(1400, 880)

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._lang_settings.window_geometry_b64 = base64.b64encode(
                bytes(self.saveGeometry())
            ).decode("ascii")
            if self._splitter is not None:
                self._lang_settings.splitter_sizes = self._splitter.sizes()
            save_app_settings(self._lang_settings)
        except OSError:
            pass
        super().closeEvent(event)

    def _push_busy(self) -> None:
        self._busy_depth += 1
        if self._busy_depth == 1:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def _pop_busy(self) -> None:
        if self._busy_depth <= 0:
            return
        self._busy_depth -= 1
        if self._busy_depth == 0:
            QApplication.restoreOverrideCursor()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._pick_audio)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self.source_panel.open_image_dialog)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._export)

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
                self._request_load_audio(path)
            elif ext in IMAGE_EXTS:
                self.source_panel.load_image_path(path)
        event.acceptProposedAction()

    # ---------- Audio loading ----------

    def _pick_audio(self):
        tr = self._tr
        exts = " ".join(f"*{e}" for e in sorted(AUDIO_EXTS))
        start = normalized_existing_dir(self._lang_settings.last_audio_dir)
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr.pick_audio_title,
            start,
            tr.pick_audio_filter.format(exts=exts),
        )
        if path:
            self._request_load_audio(path)

    def _request_load_audio(self, path: str) -> None:
        """Probe metadata, optional segment dialog, then decode."""
        tr = self._tr
        p = Path(path)
        info: AudioFileInfo | None = None
        try:
            info = probe_audio_file(path)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                tr.long_audio_title,
                tr.audio_probe_failed_detail.format(err=exc),
            )
        start_s = 0.0
        duration_s: float | None = None
        self._last_file_info = info
        self._last_load_start_s = 0.0
        self._last_load_duration_param = None

        if info is not None and (
            info.duration_s > LARGE_FILE_DURATION_S
            or info.size_bytes > LARGE_FILE_SIZE_BYTES
        ):
            dlg = LongAudioDialog(self, tr, p, info)
            if dlg.exec() != QDialog.Accepted:
                return
            ch = dlg.choice()
            if ch.cancelled:
                return
            start_s, duration_s = ch.start_s, ch.duration_s
            self._last_load_start_s = start_s
            self._last_load_duration_param = duration_s
        elif info is not None:
            self._last_load_start_s = 0.0
            self._last_load_duration_param = None

        self._start_decode_audio(path, start_s, duration_s)

    def _show_load_progress(self, message: str) -> None:
        if self._load_progress is None:
            self._load_progress = QProgressDialog(self)
            self._load_progress.setCancelButton(None)
            self._load_progress.setRange(0, 0)
            self._load_progress.setWindowModality(Qt.WindowModality.WindowModal)
            self._load_progress.setMinimumDuration(0)
        self._load_progress.setLabelText(message)
        self._load_progress.show()
        QApplication.processEvents()

    def _hide_load_progress(self) -> None:
        if self._load_progress is not None:
            self._load_progress.reset()
            self._load_progress.hide()

    def _start_decode_audio(
        self,
        path: str,
        start_s: float,
        duration_s: float | None,
    ) -> None:
        self._push_busy()
        tr = self._tr
        self._show_load_progress(tr.progress_loading_audio)
        self._hint(tr.reading_file.format(name=Path(path).name))
        w = Worker(load_audio, path, start_s=start_s, duration_s=duration_s)
        w.signals.finished.connect(lambda a: self._on_audio_loaded(a, path))
        w.signals.failed.connect(self._on_load_audio_failed)
        pool().start(w)

    def _on_load_audio_failed(self, msg: str) -> None:
        self._hide_load_progress()
        self._pop_busy()
        self._error(self._tr.load_audio_error.format(msg=msg))

    def _on_audio_loaded(self, audio: AudioData, path: str):
        self._audio = audio
        self._audio_path = path
        self._lang_settings.last_audio_dir = str(Path(path).parent)
        save_app_settings(self._lang_settings)
        self._update_audio_label()
        self.controls_panel.apply_audio_info(audio.duration_s, audio.sample_rate)
        lo, hi = recommend_freq_range(audio.sample_rate, self.controls_panel.settings().mode)
        s = self.controls_panel.settings()
        s.freq_min_hz, s.freq_max_hz = lo, hi
        s.duration_s = min(s.duration_s, audio.duration_s)
        self.controls_panel.set_settings(s)
        tr = self._tr
        self._hint(
            tr.audio_loaded_hint.format(
                name=Path(path).name, sr=audio.sample_rate, dur=audio.duration_s
            )
        )
        self.controls_panel.set_export_enabled(True)
        self._show_load_progress(tr.progress_spectrogram)
        w = Worker(compute_spectrogram, audio.samples, audio.sample_rate)
        w.signals.finished.connect(self._on_spec_ready)
        w.signals.failed.connect(self._on_spec_failed)
        pool().start(w)

    def _on_spec_failed(self, msg: str) -> None:
        self._hide_load_progress()
        self._pop_busy()
        self._error(self._tr.spectrogram_error.format(msg=msg))

    def _on_spec_ready(self, spec: SpectrogramImage):
        self._hide_load_progress()
        self._pop_busy()
        self._spec_original = spec
        self.spectrogram_view.set_spectrogram(spec)
        self._apply_region_from_settings()
        self._schedule_preview()

    def _update_audio_label(self):
        tr = self._tr
        if self._audio is None:
            self._audio_label.setText(tr.no_audio_loaded)
            return
        line = (
            f"{Path(self._audio_path).name}  •  "
            f"{self._audio.sample_rate} Hz  •  "
            f"{self._audio.duration_s:.2f}s  •  "
            f"{self._audio.channels} {tr.channels_abbr}"
        )
        info = self._last_file_info
        if info is not None and (
            self._last_load_start_s > 0.01 or self._last_load_duration_param is not None
        ):
            t0 = self._last_load_start_s
            t1 = self._last_load_start_s + self._audio.duration_s
            line += tr.audio_segment_badge.format(
                start=t0, end=t1, total=info.duration_s
            )
        self._audio_label.setText(line)

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
        self._hint(self._tr.preview_error.format(msg=msg))

    # ---------- Export ----------

    def _export(self):
        if self._audio is None:
            return
        mask = self.source_panel.current_mask()
        if mask is None:
            self._error(self._tr.export_need_source)
            return
        suggested = Path(self._audio_path or "watermarked").stem + "_watermarked"
        path = ask_export_path(
            self,
            self._tr,
            suggested,
            initial_dir=self._lang_settings.last_export_dir,
        )
        if not path:
            return
        self._push_busy()
        params = _settings_to_params(self.controls_panel.settings())
        self._hint(self._tr.exporting)
        self.controls_panel.set_export_enabled(False)
        audio = self._audio

        def do_export():
            out = embed_watermark(audio.samples, audio.sample_rate, mask, params)
            save_audio(path, AudioData(samples=out, sample_rate=audio.sample_rate))
            return path

        w = Worker(do_export)
        w.signals.finished.connect(self._on_export_done)
        w.signals.failed.connect(self._on_export_failed)
        pool().start(w)

    def _on_export_failed(self, msg: str) -> None:
        self._pop_busy()
        self.controls_panel.set_export_enabled(True)
        self._error(self._tr.export_error.format(msg=msg))

    def _on_export_done(self, path: str):
        self._pop_busy()
        tr = self._tr
        self._lang_settings.last_export_dir = str(Path(path).parent)
        save_app_settings(self._lang_settings)
        self.controls_panel.set_export_enabled(True)
        self._hint(tr.export_saved_status.format(path=path))
        QMessageBox.information(
            self,
            tr.export_done_title,
            tr.export_done_body.format(path=path),
        )

    # ---------- Presets ----------

    def _save_preset(self):
        tr = self._tr
        name, ok = QInputDialog.getText(self, tr.save_preset_title, tr.preset_name_label)
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
        self._hint(self._tr.preset_saved.format(name=preset.name))

    def _reset_settings(self):
        s = WatermarkSettings()
        if self._audio is not None:
            lo, hi = recommend_freq_range(self._audio.sample_rate, "invisible")
            s.freq_min_hz = lo
            s.freq_max_hz = hi
            s.duration_s = min(3.0, self._audio.duration_s)
        self.controls_panel.set_settings(s)

    def _copy_view_guide(self):
        tr = self._tr
        s = self.controls_panel.settings()
        guide = (
            tr.view_guide_intro
            + tr.view_guide_step1
            + tr.view_guide_step2
            + tr.view_guide_step3_header
            + tr.view_guide_fft
            + tr.view_guide_window
            + tr.view_guide_dyn
            + tr.view_guide_time.format(t0=s.start_s, t1=s.start_s + s.duration_s)
            + tr.view_guide_freq.format(f0=int(s.freq_min_hz), f1=int(s.freq_max_hz))
        )
        QGuiApplication.clipboard().setText(guide)
        self._hint(tr.view_guide_copied)

    # ---------- Helpers ----------

    def _hint(self, msg: str):
        self.statusBar().showMessage(msg, 8000)

    def _error(self, msg: str):
        self.statusBar().showMessage(msg, 10000)
        QMessageBox.critical(self, self._tr.error_title, msg)


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
