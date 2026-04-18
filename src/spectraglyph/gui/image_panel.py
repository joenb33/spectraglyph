from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSpinBox,
    QFormLayout,
)

from ..core.image_processor import MaskOptions, load_image, to_mask
from ..core.text_renderer import TextStyle, render_text_mask
from ..utils.config import AppSettings, normalized_existing_dir, save_app_settings
from .i18n import UIStrings


class SourcePanel(QTabWidget):
    """Tabs: image and text. Emits mask (HxW float32 in 0-1) on change."""

    mask_changed = Signal(object)  # numpy array or None

    def __init__(self, tr: UIStrings, app_settings: AppSettings, parent=None):
        super().__init__(parent)
        self._tr = tr
        self._app_settings = app_settings
        self._image: Image.Image | None = None
        self._image_path: str | None = None
        self._image_error_detail: str | None = None
        self._current_mask: np.ndarray | None = None
        self._bg_opts = MaskOptions()

        # --- Image tab ---
        img_tab = QWidget()
        img_layout = QVBoxLayout(img_tab)
        img_layout.setContentsMargins(10, 8, 10, 8)

        row = QHBoxLayout()
        self._pick_btn = QPushButton(tr.pick_image)
        self._pick_btn.setToolTip(tr.pick_image_tooltip)
        self._pick_btn.clicked.connect(self._pick_image)
        self._clear_btn = QPushButton(tr.clear)
        self._clear_btn.clicked.connect(self._clear_image)
        self._path_label = QLabel(tr.no_image)
        self._path_label.setStyleSheet("color: #889;")
        row.addWidget(self._pick_btn)
        row.addWidget(self._clear_btn)
        row.addWidget(self._path_label, 1)
        img_layout.addLayout(row)

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumHeight(140)
        self._preview.setStyleSheet(
            "QLabel { background: #1a1d22; border: 1px dashed #3a3e46; border-radius: 6px; color: #667; }"
        )
        self._preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._preview.setText(tr.drop_png_here)
        img_layout.addWidget(self._preview, 1)

        self.addTab(img_tab, tr.tab_image)

        # --- Text tab ---
        txt_tab = QWidget()
        txt_layout = QVBoxLayout(txt_tab)
        txt_layout.setContentsMargins(10, 8, 10, 8)
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(tr.text_placeholder)
        self._text_edit.setPlainText("HALLÅ")
        self._text_edit.setMaximumHeight(90)
        self._text_edit.textChanged.connect(self._rebuild_text_mask)
        txt_layout.addWidget(self._text_edit)

        form = QFormLayout()
        self._font_size = QSpinBox()
        self._font_size.setRange(16, 512)
        self._font_size.setValue(128)
        self._font_size.valueChanged.connect(self._rebuild_text_mask)
        self._label_font_size = QLabel(tr.label_font_size)
        form.addRow(self._label_font_size, self._font_size)
        self._letter_spacing = QSpinBox()
        self._letter_spacing.setRange(-20, 60)
        self._letter_spacing.setValue(2)
        self._letter_spacing.valueChanged.connect(self._rebuild_text_mask)
        self._label_letter_spacing = QLabel(tr.label_letter_spacing)
        form.addRow(self._label_letter_spacing, self._letter_spacing)
        txt_layout.addLayout(form)

        self._text_preview = QLabel()
        self._text_preview.setAlignment(Qt.AlignCenter)
        self._text_preview.setMinimumHeight(120)
        self._text_preview.setStyleSheet(
            "QLabel { background: #1a1d22; border: 1px dashed #3a3e46; border-radius: 6px; }"
        )
        txt_layout.addWidget(self._text_preview, 1)

        self.addTab(txt_tab, tr.tab_text)

        self.currentChanged.connect(lambda _: self._emit())
        self._rebuild_text_mask()

    # ---------- Public ----------

    def set_strings(self, tr: UIStrings) -> None:
        self._tr = tr
        self._pick_btn.setText(tr.pick_image)
        self._clear_btn.setText(tr.clear)
        if self._image_error_detail is not None:
            self._path_label.setText(tr.image_error.format(detail=self._image_error_detail))
        elif self._image is None:
            self._path_label.setText(tr.no_image)
        elif self._image_path is not None:
            self._path_label.setText(Path(self._image_path).name)
        self._preview.setText(tr.drop_png_here)
        self._text_edit.setPlaceholderText(tr.text_placeholder)
        self._label_font_size.setText(tr.label_font_size)
        self._label_letter_spacing.setText(tr.label_letter_spacing)
        self._pick_btn.setToolTip(tr.pick_image_tooltip)
        self.setTabText(0, tr.tab_image)
        self.setTabText(1, tr.tab_text)

    def set_bg_options(self, opts: MaskOptions):
        self._bg_opts = opts
        if self.currentIndex() == 0 and self._image is not None:
            self._rebuild_image_mask()

    def load_image_path(self, path: str):
        try:
            img = load_image(path)
        except Exception as exc:  # noqa: BLE001
            self._image_error_detail = str(exc)
            self._path_label.setText(self._tr.image_error.format(detail=self._image_error_detail))
            return
        self._image_error_detail = None
        self._image = img
        self._image_path = path
        self._path_label.setText(Path(path).name)
        self._app_settings.last_image_dir = str(Path(path).parent)
        save_app_settings(self._app_settings)
        self.setCurrentIndex(0)
        self._rebuild_image_mask()

    def current_mask(self) -> np.ndarray | None:
        return self._current_mask

    # ---------- Internals ----------

    def open_image_dialog(self) -> None:
        """Used by keyboard shortcut (Ctrl+I)."""
        self._pick_image()

    def _pick_image(self):
        tr = self._tr
        start = normalized_existing_dir(self._app_settings.last_image_dir)
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr.pick_image_title,
            start,
            tr.pick_image_filter,
        )
        if path:
            self.load_image_path(path)


    def _clear_image(self):
        self._image = None
        self._image_path = None
        self._image_error_detail = None
        self._path_label.setText(self._tr.no_image)
        self._preview.setText(self._tr.drop_png_here)
        self._preview.setPixmap(QPixmap())
        self._current_mask = None
        self.mask_changed.emit(None)

    def _rebuild_image_mask(self):
        if self._image is None:
            self._current_mask = None
            self.mask_changed.emit(None)
            return
        mask = to_mask(self._image, self._bg_opts)
        self._current_mask = mask
        self._update_image_preview(mask)
        if self.currentIndex() == 0:
            self.mask_changed.emit(mask)

    def _rebuild_text_mask(self):
        style = TextStyle(
            text=self._text_edit.toPlainText() or " ",
            font_size=int(self._font_size.value()),
            letter_spacing=int(self._letter_spacing.value()),
        )
        mask = render_text_mask(style)
        self._update_text_preview(mask)
        if self.currentIndex() == 1:
            self._current_mask = mask
            self.mask_changed.emit(mask)

    def _emit(self):
        if self.currentIndex() == 0:
            self._rebuild_image_mask()
        else:
            self._rebuild_text_mask()

    def _update_image_preview(self, mask: np.ndarray):
        self._preview.setPixmap(_mask_to_pixmap(mask, self._preview.size()))

    def _update_text_preview(self, mask: np.ndarray):
        self._text_preview.setPixmap(_mask_to_pixmap(mask, self._text_preview.size()))


def _mask_to_pixmap(mask: np.ndarray, size) -> QPixmap:
    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.clip(mask * 255.0, 0, 255).astype(np.uint8)
    img = QImage(rgba.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
    pm = QPixmap.fromImage(img)
    if size and size.width() > 20 and size.height() > 20:
        pm = pm.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm
