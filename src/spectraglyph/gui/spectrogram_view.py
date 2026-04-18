from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from ..core.spectrogram_renderer import SpectrogramImage
from .i18n import UIStrings


class SpectrogramView(pg.GraphicsLayoutWidget):
    """Live spectrogram viewer with a draggable/resizable watermark region."""

    region_changed = Signal(float, float, float, float)  # start_s, end_s, f_min, f_max
    seek_requested = Signal(float)  # seconds — user clicked on the spectrogram

    def __init__(self, tr: UIStrings, parent=None):
        super().__init__(parent)
        self._tr = tr
        self.setBackground("#14161a")
        self._plot = self.addPlot()
        self._plot.setLabel("left", tr.axis_frequency, units="Hz")
        self._plot.setLabel("bottom", tr.axis_time, units="s")
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.getAxis("left").setPen(pg.mkPen("#8aa"))
        self._plot.getAxis("bottom").setPen(pg.mkPen("#8aa"))
        self._plot.getAxis("left").setTextPen(pg.mkPen("#ccd"))
        self._plot.getAxis("bottom").setTextPen(pg.mkPen("#ccd"))
        self._image_item = pg.ImageItem(axisOrder="row-major")
        self._plot.addItem(self._image_item)

        self._region: pg.ROI | None = None
        self._freq_lines: tuple[pg.InfiniteLine, pg.InfiniteLine] | None = None
        self._placeholder = pg.TextItem(
            tr.empty_spectrogram_hint,
            color=(180, 180, 200),
            anchor=(0.5, 0.5),
        )
        self._plot.addItem(self._placeholder)
        self._current_spec: SpectrogramImage | None = None
        self._suppress_emit = False

        # Vertical playhead — hidden until playback starts.
        self._playhead = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(QColor(255, 90, 90), width=2),
        )
        self._playhead.setZValue(10)
        self._playhead.hide()
        self._plot.addItem(self._playhead, ignoreBounds=True)

        # Seek-on-click handler.
        self.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    def set_strings(self, tr: UIStrings) -> None:
        self._tr = tr
        self._plot.setLabel("left", tr.axis_frequency, units="Hz")
        self._plot.setLabel("bottom", tr.axis_time, units="s")
        self._placeholder.setText(tr.empty_spectrogram_hint)

    def set_spectrogram(self, spec: SpectrogramImage | None):
        self._current_spec = spec
        if spec is None:
            self._image_item.clear()
            if self._placeholder.scene() is None:
                self._plot.addItem(self._placeholder)
            self._placeholder.setPos(1.0, 10_000.0)
            return
        if self._placeholder.scene() is not None:
            self._plot.removeItem(self._placeholder)

        # Row 0 = low freq, last row = high freq (match axis).
        db = spec.magnitude_db
        norm = (db - db.min()) / max(db.max() - db.min(), 1e-9)
        lut = _viridis_lut()
        img = lut[np.clip((norm * 255).astype(np.int32), 0, 255)]
        self._image_item.setImage(img, autoLevels=False)

        t_max = float(spec.times[-1]) if spec.times.size else 1.0
        f_max = float(spec.freqs[-1]) if spec.freqs.size else 20_000.0
        self._image_item.setRect(0, 0, t_max, f_max)
        self._plot.setXRange(0, t_max, padding=0)
        self._plot.setYRange(0, f_max, padding=0)

    def set_watermark_region(
        self,
        start_s: float,
        end_s: float,
        f_min: float,
        f_max: float,
    ):
        self._suppress_emit = True
        try:
            if self._region is None:
                self._region = pg.RectROI(
                    [start_s, f_min],
                    [end_s - start_s, f_max - f_min],
                    pen=pg.mkPen(QColor(255, 180, 40), width=2),
                    hoverPen=pg.mkPen(QColor(255, 220, 80), width=2),
                    handlePen=pg.mkPen(QColor(255, 210, 60)),
                )
                self._region.addScaleHandle([1, 1], [0, 0])
                self._region.addScaleHandle([0, 0], [1, 1])
                self._plot.addItem(self._region)
                self._region.sigRegionChanged.connect(self._emit_region)
            else:
                self._region.setPos([start_s, f_min], finish=False)
                self._region.setSize([end_s - start_s, f_max - f_min], finish=False)
        finally:
            self._suppress_emit = False

    def _emit_region(self):
        if self._suppress_emit or self._region is None:
            return
        pos = self._region.pos()
        size = self._region.size()
        start_s = float(pos.x())
        f_min = float(pos.y())
        end_s = float(start_s + size.x())
        f_max = float(f_min + size.y())
        self.region_changed.emit(start_s, end_s, f_min, f_max)

    # ---------- Playhead / seek ----------

    def set_playhead(self, seconds: float | None) -> None:
        if seconds is None:
            self._playhead.hide()
            return
        self._playhead.setValue(float(seconds))
        if not self._playhead.isVisible():
            self._playhead.show()

    def _on_mouse_clicked(self, event) -> None:
        if self._current_spec is None:
            return
        if event.button() != Qt.LeftButton:
            return
        vb = self._plot.getViewBox()
        if vb is None:
            return
        # Ignore clicks inside the ROI (drag/resize) or on the ROI's handles.
        if self._region is not None:
            items_under = self._plot.scene().items(event.scenePos())
            for it in items_under:
                # The ROI itself and its scale handles should not trigger seeks.
                if it is self._region or getattr(it, "parentItem", lambda: None)() is self._region:
                    return
        pt = vb.mapSceneToView(event.scenePos())
        seconds = float(pt.x())
        t_max = float(self._current_spec.times[-1]) if self._current_spec.times.size else 0.0
        if seconds < 0.0 or seconds > t_max:
            return
        event.accept()
        self.set_playhead(seconds)
        self.seek_requested.emit(seconds)


_LUT_CACHE: np.ndarray | None = None


def _viridis_lut() -> np.ndarray:
    global _LUT_CACHE
    if _LUT_CACHE is not None:
        return _LUT_CACHE
    # Same stops as the built-in viridis LUT in core.spectrogram_renderer.
    from ..core.spectrogram_renderer import viridis_colormap

    x = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    rgb = viridis_colormap(x)
    rgba = np.concatenate([rgb, np.full((256, 1), 255, dtype=np.uint8)], axis=1)
    _LUT_CACHE = rgba
    return rgba
