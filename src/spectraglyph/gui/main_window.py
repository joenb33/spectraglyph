from __future__ import annotations

import base64
import binascii
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
from functools import partial
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QByteArray, QObject, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
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

from .. import APP_DISPLAY_NAME, __version__
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
from ..core.spectrogram_renderer import (
    SpectrogramImage,
    compute_spectrogram,
    compute_spectrogram_patch,
    splice_spectrogram_patch,
)
from ..core.watermark import (
    WatermarkParams,
    embed_watermark,
    embed_watermark_local,
    recommend_freq_range,
)
from ..utils.config import (
    AppSettings,
    Preset,
    Presets,
    normalized_existing_dir,
    save_app_settings,
    update_recent_files,
)
from ..utils.github_release import (
    LatestRelease,
    compare_versions,
    download_release_asset,
    fetch_latest_release,
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

        # Playback state
        self._media_player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None
        self._play_tmp_path: str | None = None
        self._play_pending_watermarked = False
        # Cached watermarked audio from the last preview render — reused by Play
        # to avoid re-running embed_watermark on every press.
        self._wm_samples_cache: np.ndarray | None = None
        self._play_mode_watermarked: bool = False
        self._play_duration_ms: int = 0
        self._seek_pending_ms: int | None = None

        self._build_ui()
        self._restore_window_state()
        self._setup_shortcuts()
        self._wire_signals()
        self._update_audio_label()

        self._update_check_timer = QTimer(self)
        self._update_check_timer.setSingleShot(True)
        self._update_check_timer.setInterval(4500)
        self._update_check_timer.timeout.connect(self._scheduled_update_check_if_due)
        self._update_check_timer.start()

    # ---------- UI ----------

    def _build_ui(self):
        tr = self._tr
        self._build_file_menu()
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

        self._play_btn = QPushButton(tr.play_preview)
        self._play_btn.setToolTip(tr.play_tooltip)
        self._play_btn.setMinimumHeight(34)
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._toggle_playback)
        top.addWidget(self._play_btn)
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

    def _build_file_menu(self) -> None:
        tr = self._tr
        file_menu = self.menuBar().addMenu(tr.menu_file)
        open_act = QAction(tr.file_open, self)
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.triggered.connect(self._pick_audio)
        file_menu.addAction(open_act)

        self._recent_menu = file_menu.addMenu(tr.file_recent)
        self._populate_recent_menu()

        file_menu.addSeparator()
        export_act = QAction(tr.file_export, self)
        export_act.setShortcut(QKeySequence("Ctrl+E"))
        export_act.triggered.connect(self._export)
        file_menu.addAction(export_act)

        file_menu.addSeparator()
        exit_act = QAction(tr.file_exit, self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

    def _populate_recent_menu(self) -> None:
        tr = self._tr
        menu = self._recent_menu
        menu.clear()
        files = self._lang_settings.recent_audio_files
        if not files:
            placeholder = menu.addAction(tr.file_recent_empty)
            placeholder.setEnabled(False)
            return
        for path in files:
            act = QAction(self._recent_label(path), self)
            act.setData(path)
            act.setToolTip(path)
            act.triggered.connect(lambda _=False, p=path: self._open_recent(p))
            menu.addAction(act)
        menu.addSeparator()
        clear_act = QAction(tr.file_recent_clear, self)
        clear_act.triggered.connect(self._clear_recent_files)
        menu.addAction(clear_act)

    def _recent_label(self, path: str) -> str:
        p = Path(path)
        parent = p.parent.name or str(p.parent)
        return f"{p.name}  —  {parent}"

    def _open_recent(self, path: str) -> None:
        if not Path(path).is_file():
            self._hint(self._tr.recent_missing.format(path=path))
            self._lang_settings.recent_audio_files = [
                p for p in self._lang_settings.recent_audio_files if p != path
            ]
            save_app_settings(self._lang_settings)
            self._populate_recent_menu()
            return
        self._request_load_audio(path)

    def _clear_recent_files(self) -> None:
        self._lang_settings.recent_audio_files = []
        save_app_settings(self._lang_settings)
        self._populate_recent_menu()

    def _build_help_menu(self) -> None:
        tr = self._tr
        help_menu = self.menuBar().addMenu(tr.menu_help)
        act = QAction(tr.shortcuts_action, self)
        act.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(act)
        upd = QAction(tr.check_updates_action, self)
        upd.triggered.connect(self._check_for_updates_menu)
        help_menu.addAction(upd)

    def _show_shortcuts_dialog(self) -> None:
        tr = self._tr
        QMessageBox.information(
            self, tr.shortcuts_dialog_title, tr.shortcuts_dialog_body
        )

    def _scheduled_update_check_if_due(self) -> None:
        if not getattr(sys, "frozen", False):
            return
        raw = self._lang_settings.last_update_check_iso
        if raw:
            try:
                prev = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if prev.tzinfo is None:
                    prev = prev.replace(tzinfo=datetime.timezone.utc)
                now = datetime.datetime.now(datetime.timezone.utc)
                if (now - prev).total_seconds() < 7 * 24 * 3600:
                    return
            except ValueError:
                pass
        self._run_update_check(silent_failures=True)

    def _check_for_updates_menu(self) -> None:
        self._run_update_check(silent_failures=False)

    def _run_update_check(self, *, silent_failures: bool) -> None:
        self._push_busy()
        self._hint(self._tr.update_check_progress)
        w = Worker(fetch_latest_release, parent=self)
        sig = w.signals
        w.signals.finished.connect(
            partial(self._on_release_info_dispatch, sig, silent_failures),
            Qt.ConnectionType.QueuedConnection,
        )
        w.signals.failed.connect(
            partial(self._on_release_fetch_failed_dispatch, sig, silent_failures),
            Qt.ConnectionType.QueuedConnection,
        )
        pool().start(w)

    def _on_release_fetch_failed_dispatch(
        self, sig: QObject, silent_failures: bool, msg: str
    ) -> None:
        try:
            self._on_release_fetch_failed(silent_failures, msg)
        finally:
            sig.deleteLater()

    def _on_release_fetch_failed(self, silent_failures: bool, msg: str) -> None:
        self._pop_busy()
        self._hint(self._tr.status_hint_drop)
        if not silent_failures:
            QMessageBox.warning(
                self,
                self._tr.update_error_title,
                self._tr.update_error_body.format(msg=msg),
            )

    def _on_release_info_dispatch(
        self, sig: QObject, silent_failures: bool, info: object
    ) -> None:
        try:
            if not isinstance(info, LatestRelease):
                self._pop_busy()
                self._hint(self._tr.status_hint_drop)
                return
            self._on_release_info(silent_failures, info)
        finally:
            sig.deleteLater()

    def _on_release_info(self, silent_failures: bool, info: LatestRelease) -> None:
        self._pop_busy()
        self._lang_settings.last_update_check_iso = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        save_app_settings(self._lang_settings)
        self._hint(self._tr.status_hint_drop)
        tr = self._tr
        if compare_versions(__version__, info.version) >= 0:
            if not silent_failures:
                QMessageBox.information(
                    self,
                    tr.update_up_to_date_title,
                    tr.update_up_to_date_body.format(version=__version__),
                )
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr.update_available_title)
        box.setText(
            tr.update_available_body.format(
                current=__version__, latest=info.version, url=info.page_url
            )
        )
        open_btn = box.addButton(tr.update_open_release, QMessageBox.ActionRole)
        dl_btn = box.addButton(tr.update_download, QMessageBox.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.setDefaultButton(open_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is open_btn and info.page_url:
            QDesktopServices.openUrl(QUrl(info.page_url))
        elif clicked is dl_btn:
            self._download_update(info)

    def _download_update(self, info: LatestRelease) -> None:
        tr = self._tr
        if not info.download_url:
            QMessageBox.information(self, tr.update_available_title, tr.update_no_download)
            if info.page_url:
                QDesktopServices.openUrl(QUrl(info.page_url))
            return
        folder = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        name = info.asset_name or f"SpectraGlyph-{info.version}-Windows-x64.exe"
        dest = str(Path(folder) / name)
        self._push_busy()
        self._hint(tr.update_downloading)
        w = Worker(download_release_asset, info.download_url, dest, parent=self)
        sig = w.signals
        w.signals.finished.connect(
            partial(self._on_update_download_done_dispatch, sig, dest),
            Qt.ConnectionType.QueuedConnection,
        )
        w.signals.failed.connect(
            partial(self._on_update_download_failed_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        pool().start(w)

    def _on_update_download_done_dispatch(self, sig: QObject, dest: str, _result: object) -> None:
        try:
            self._pop_busy()
            self._hint(self._tr.status_hint_drop)
            QMessageBox.information(
                self,
                self._tr.update_available_title,
                self._tr.update_download_done.format(path=dest),
            )
        finally:
            sig.deleteLater()

    def _on_update_download_failed_dispatch(self, sig: QObject, msg: str) -> None:
        try:
            self._pop_busy()
            self._hint(self._tr.status_hint_drop)
            QMessageBox.warning(
                self,
                self._tr.update_error_title,
                self._tr.update_download_failed.format(msg=msg),
            )
        finally:
            sig.deleteLater()

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
        self._build_file_menu()
        self._build_language_menu()
        self._build_help_menu()

        self._load_audio_btn.setText(tr.choose_audio)
        self._load_audio_btn.setToolTip(tr.choose_audio_tooltip)
        self._toggle_preview_btn.setText(tr.preview_watermark)
        self._play_btn.setToolTip(tr.play_tooltip)
        self._update_play_btn_label()
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
        self._stop_playback()
        self._cleanup_tmp_playback()
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
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._toggle_playback)

    def _wire_signals(self):
        self.controls_panel.settings_changed.connect(self._on_settings_changed)
        self.controls_panel.export_requested.connect(self._export)
        self.controls_panel.save_preset_requested.connect(self._save_preset)
        self.controls_panel.reset_requested.connect(self._reset_settings)
        self.controls_panel.copy_view_guide_requested.connect(self._copy_view_guide)
        self.source_panel.mask_changed.connect(self._on_mask_changed)
        self.spectrogram_view.region_changed.connect(self._on_region_dragged)
        self.spectrogram_view.seek_requested.connect(self._on_seek_requested)

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
        w = Worker(
            load_audio, path, start_s=start_s, duration_s=duration_s, parent=self
        )
        sig = w.signals
        w.signals.finished.connect(
            partial(self._on_audio_loaded_dispatch, sig, path),
            Qt.ConnectionType.QueuedConnection,
        )
        w.signals.failed.connect(
            partial(self._on_load_audio_failed_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        pool().start(w)

    def _on_load_audio_failed_dispatch(self, sig: QObject, msg: str) -> None:
        try:
            self._on_load_audio_failed(msg)
        finally:
            sig.deleteLater()

    def _on_audio_loaded_dispatch(self, sig: QObject, path: str, audio: AudioData) -> None:
        try:
            self._on_audio_loaded(audio, path)
        finally:
            sig.deleteLater()

    def _on_load_audio_failed(self, msg: str) -> None:
        self._hide_load_progress()
        self._pop_busy()
        self._error(self._tr.load_audio_error.format(msg=msg))

    def _on_audio_loaded(self, audio: AudioData, path: str):
        self._audio = audio
        self._audio_path = path
        self._stop_playback()
        self._play_btn.setEnabled(True)
        self._lang_settings.last_audio_dir = str(Path(path).parent)
        self._lang_settings.recent_audio_files = update_recent_files(
            self._lang_settings.recent_audio_files, path
        )
        save_app_settings(self._lang_settings)
        self._populate_recent_menu()
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
        w = Worker(
            compute_spectrogram, audio.samples, audio.sample_rate, parent=self
        )
        w.signals.finished.connect(self._on_spec_ready, Qt.ConnectionType.QueuedConnection)
        w.signals.failed.connect(self._on_spec_failed, Qt.ConnectionType.QueuedConnection)
        pool().start(w)

    def _on_spec_failed(self, msg: str) -> None:
        try:
            self._hide_load_progress()
            self._pop_busy()
            self._error(self._tr.spectrogram_error.format(msg=msg))
        finally:
            if (s := self.sender()) is not None:
                s.deleteLater()

    def _on_spec_ready(self, spec: SpectrogramImage):
        try:
            self._hide_load_progress()
            self._pop_busy()
            self._spec_original = spec
            self.spectrogram_view.set_spectrogram(spec)
            self._apply_region_from_settings()
            self._schedule_preview()
        finally:
            if (s := self.sender()) is not None:
                s.deleteLater()

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
            MaskOptions(
                mode=s.bg_mode,
                threshold=s.bg_threshold,
                chroma_rgb=s.chroma_rgb,
                invert=s.invert,
            )
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
        # Any pending settings/mask change invalidates the cached watermarked samples.
        self._wm_samples_cache = None
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
        base = self._spec_original
        w = Worker(_compute_preview, audio, sr, mask, params, base, parent=self)
        sig = w.signals
        w.signals.finished.connect(
            partial(self._on_preview_ready_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        w.signals.failed.connect(
            partial(self._on_preview_failed_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        pool().start(w)

    def _on_preview_ready_dispatch(self, sig: QObject, result: tuple) -> None:
        try:
            self._on_preview_ready(result)
        finally:
            sig.deleteLater()

    def _on_preview_failed_dispatch(self, sig: QObject, msg: str) -> None:
        try:
            self._preview_failed(msg)
        finally:
            sig.deleteLater()

    def _on_preview_ready(self, result: tuple):
        self._pending_preview = False
        spec, samples = result
        self._spec_preview = spec
        self._wm_samples_cache = samples
        self.spectrogram_view.set_spectrogram(spec)
        self._apply_region_from_settings()

    def _preview_failed(self, msg: str):
        self._pending_preview = False
        self._hint(self._tr.preview_error.format(msg=msg))

    # ---------- Playback ----------

    def _ensure_media_player(self) -> QMediaPlayer:
        if self._media_player is None:
            self._media_player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.playbackStateChanged.connect(self._on_playback_state)
            self._media_player.errorOccurred.connect(self._on_playback_error)
            self._media_player.positionChanged.connect(self._on_playback_position)
            self._media_player.durationChanged.connect(self._on_playback_duration)
        return self._media_player

    def _is_playing(self) -> bool:
        return (
            self._media_player is not None
            and self._media_player.playbackState() == QMediaPlayer.PlayingState
        )

    def _update_play_btn_label(self) -> None:
        tr = self._tr
        self._play_btn.setText(tr.stop_preview if self._is_playing() else tr.play_preview)

    def _toggle_playback(self) -> None:
        if self._audio is None or not self._audio_path:
            self._hint(self._tr.play_needs_audio)
            return
        if self._is_playing():
            self._stop_playback()
            return
        want_watermarked = self._toggle_preview_btn.isChecked() and (
            self.source_panel.current_mask() is not None
        )
        if want_watermarked:
            self._start_watermarked_playback()
        else:
            self._start_original_playback()

    def _start_original_playback(self) -> None:
        self._play_mode_watermarked = False
        player = self._ensure_media_player()
        player.setSource(QUrl.fromLocalFile(str(Path(self._audio_path).resolve())))
        if self._seek_pending_ms is not None:
            player.setPosition(self._seek_pending_ms)
            self._seek_pending_ms = None
        player.play()
        self._update_play_btn_label()

    def _start_watermarked_playback(self) -> None:
        if self._audio is None:
            return
        mask = self.source_panel.current_mask()
        if mask is None:
            self._start_original_playback()
            return
        self._play_mode_watermarked = True
        audio = self._audio
        # Fast path: preview already computed the watermarked samples — write them
        # straight to a tmp WAV instead of re-running the embed.
        if self._wm_samples_cache is not None and len(self._wm_samples_cache) == len(audio.samples):
            try:
                tmp = tempfile.NamedTemporaryFile(
                    prefix="spectraglyph_play_", suffix=".wav", delete=False
                )
                tmp.close()
                save_audio(
                    tmp.name,
                    AudioData(samples=self._wm_samples_cache, sample_rate=audio.sample_rate),
                )
                self._on_watermarked_ready(tmp.name)
                return
            except OSError as exc:
                self._hint(self._tr.play_failed.format(msg=str(exc)))
                return

        # Slow path: no cached samples yet — render in a worker.
        self._play_pending_watermarked = True
        self._hint(self._tr.play_preparing)
        params = _settings_to_params(self.controls_panel.settings())

        def do_render():
            out = embed_watermark(audio.samples, audio.sample_rate, mask, params)
            tmp = tempfile.NamedTemporaryFile(
                prefix="spectraglyph_play_", suffix=".wav", delete=False
            )
            tmp.close()
            save_audio(tmp.name, AudioData(samples=out, sample_rate=audio.sample_rate))
            return (tmp.name, out)

        w = Worker(do_render, parent=self)
        sig = w.signals
        w.signals.finished.connect(
            partial(self._on_watermarked_render_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        w.signals.failed.connect(
            partial(self._on_playback_render_failed_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        pool().start(w)

    def _on_watermarked_render_dispatch(self, sig: QObject, result: tuple) -> None:
        try:
            self._on_watermarked_render_ready(result)
        finally:
            sig.deleteLater()

    def _on_playback_render_failed_dispatch(self, sig: QObject, msg: str) -> None:
        try:
            self._on_playback_render_failed(msg)
        finally:
            sig.deleteLater()

    def _on_watermarked_render_ready(self, result: tuple) -> None:
        tmp_path, samples = result
        self._wm_samples_cache = samples
        self._on_watermarked_ready(tmp_path)

    def _on_watermarked_ready(self, tmp_path: str) -> None:
        self._play_pending_watermarked = False
        self._cleanup_tmp_playback()
        self._play_tmp_path = tmp_path
        player = self._ensure_media_player()
        player.setSource(QUrl.fromLocalFile(tmp_path))
        if self._seek_pending_ms is not None:
            player.setPosition(self._seek_pending_ms)
            self._seek_pending_ms = None
        player.play()
        self._update_play_btn_label()

    def _on_playback_render_failed(self, msg: str) -> None:
        self._play_pending_watermarked = False
        self._hint(self._tr.play_failed.format(msg=msg))

    def _stop_playback(self) -> None:
        if self._media_player is not None:
            self._media_player.stop()
        self.spectrogram_view.set_playhead(None)
        self._update_play_btn_label()

    def _on_playback_state(self, _state) -> None:
        if not self._is_playing():
            self.spectrogram_view.set_playhead(None)
        self._update_play_btn_label()

    def _on_playback_error(self, _err, msg: str) -> None:
        if msg:
            self._hint(self._tr.play_failed.format(msg=msg))
        self._update_play_btn_label()

    def _on_playback_position(self, ms: int) -> None:
        if self._audio is None or not self._is_playing():
            return
        self.spectrogram_view.set_playhead(ms / 1000.0)

    def _on_playback_duration(self, ms: int) -> None:
        self._play_duration_ms = int(ms)

    def _on_seek_requested(self, seconds: float) -> None:
        """User clicked the spectrogram — seek or start playback at that time."""
        if self._audio is None or not self._audio_path:
            return
        seconds = max(0.0, min(float(self._audio.duration_s), float(seconds)))
        target_ms = int(seconds * 1000)
        want_watermarked = self._toggle_preview_btn.isChecked() and (
            self.source_panel.current_mask() is not None
        )
        if self._is_playing() and self._media_player is not None:
            # Switch source if the play mode no longer matches the current preview state.
            if want_watermarked != self._play_mode_watermarked:
                self._stop_playback()
                self._seek_pending_ms = target_ms
                if want_watermarked:
                    self._start_watermarked_playback()
                else:
                    self._start_original_playback()
                return
            self._media_player.setPosition(target_ms)
            self.spectrogram_view.set_playhead(seconds)
            return
        # Not currently playing — queue a seek and start playback.
        self._seek_pending_ms = target_ms
        if want_watermarked:
            self._start_watermarked_playback()
        else:
            self._start_original_playback()

    def _cleanup_tmp_playback(self) -> None:
        if self._play_tmp_path and os.path.isfile(self._play_tmp_path):
            try:
                os.unlink(self._play_tmp_path)
            except OSError:
                pass
        self._play_tmp_path = None

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

        w = Worker(do_export, parent=self)
        sig = w.signals
        w.signals.finished.connect(
            partial(self._on_export_done_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        w.signals.failed.connect(
            partial(self._on_export_failed_dispatch, sig),
            Qt.ConnectionType.QueuedConnection,
        )
        pool().start(w)

    def _on_export_failed_dispatch(self, sig: QObject, msg: str) -> None:
        try:
            self._on_export_failed(msg)
        finally:
            sig.deleteLater()

    def _on_export_done_dispatch(self, sig: QObject, path: str) -> None:
        try:
            self._on_export_done(path)
        finally:
            sig.deleteLater()

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

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(tr.export_done_title)
        box.setText(tr.export_done_body.format(path=path))
        audacity_btn = box.addButton(tr.export_done_open_audacity, QMessageBox.ActionRole)
        folder_btn = box.addButton(tr.export_done_show_folder, QMessageBox.ActionRole)
        close_btn = box.addButton(tr.export_done_close, QMessageBox.AcceptRole)
        box.setDefaultButton(close_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is audacity_btn:
            self._open_in_audacity(path)
        elif clicked is folder_btn:
            self._show_in_folder(path)

    def _open_in_audacity(self, path: str) -> None:
        exe = _find_audacity()
        if exe is None:
            self._error(self._tr.audacity_not_found)
            return
        try:
            subprocess.Popen([exe, path], close_fds=True)
        except OSError as exc:
            self._error(self._tr.audacity_not_found + f" ({exc})")

    def _show_in_folder(self, path: str) -> None:
        p = Path(path).resolve()
        if sys.platform == "win32":
            try:
                subprocess.Popen(["explorer", f"/select,{p}"], close_fds=True)
                return
            except OSError:
                pass
        # Fallback: open the containing folder.
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(p.parent)], close_fds=True)
            else:
                subprocess.Popen(["xdg-open", str(p.parent)], close_fds=True)
        except OSError:
            pass

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
            chroma_rgb=s.chroma_rgb,
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


_AUDACITY_WIN_PATHS = (
    r"C:\Program Files\Audacity\Audacity.exe",
    r"C:\Program Files (x86)\Audacity\Audacity.exe",
)


def _find_audacity() -> str | None:
    """Locate Audacity. Checks PATH, typical Windows install dirs, and LOCALAPPDATA."""
    on_path = shutil.which("audacity") or shutil.which("Audacity")
    if on_path:
        return on_path
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        candidates = list(_AUDACITY_WIN_PATHS)
        if local:
            candidates.append(str(Path(local) / "Programs" / "Audacity" / "Audacity.exe"))
        for c in candidates:
            if os.path.isfile(c):
                return c
    return None


def _settings_to_params(s: WatermarkSettings) -> WatermarkParams:
    return WatermarkParams(
        mode=s.mode,  # type: ignore[arg-type]
        start_s=s.start_s,
        duration_s=s.duration_s,
        freq_min_hz=s.freq_min_hz,
        freq_max_hz=s.freq_max_hz,
        strength_db=s.strength_db,
    )


def _compute_preview(
    audio: np.ndarray,
    sr: int,
    mask: np.ndarray,
    params: WatermarkParams,
    base: SpectrogramImage,
) -> tuple[SpectrogramImage, np.ndarray]:
    """Fast preview: localize the embed to the watermark window, then splice that
    window's spectrogram columns into the cached original spectrogram."""
    watermarked = embed_watermark_local(audio, sr, mask, params)
    pad_s = params.n_fft / sr
    t0 = max(0.0, params.start_s - pad_s)
    t1 = params.start_s + params.duration_s + pad_s
    patch, c0, c1 = compute_spectrogram_patch(
        watermarked, base, time_start_s=t0, time_end_s=t1
    )
    spec = splice_spectrogram_patch(base, patch, c0, c1)
    return spec, watermarked
