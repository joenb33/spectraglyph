from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

from .audio_io import to_mono


@dataclass
class SpectrogramImage:
    """Log-magnitude spectrogram ready for display."""

    magnitude_db: np.ndarray  # shape (F, T), float32, clipped dB relative to peak
    freqs: np.ndarray         # shape (F,)
    times: np.ndarray         # shape (T,)
    sr: int
    n_fft: int
    hop: int


def compute_spectrogram(
    audio: np.ndarray,
    sr: int,
    *,
    n_fft: int = 4096,
    hop: int = 1024,
    max_cols: int = 1600,
    dynamic_range_db: float = 80.0,
) -> SpectrogramImage:
    """Return a log-magnitude spectrogram trimmed to a max column count for display."""
    mono = to_mono(audio)
    win = signal.windows.hann(n_fft, sym=False)
    f, t, Z = signal.stft(
        mono,
        fs=sr,
        window=win,
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary="zeros",
        padded=True,
    )
    mag = np.abs(Z).astype(np.float32)

    # Downsample in time if we have too many columns — average pooling.
    if mag.shape[1] > max_cols:
        factor = int(np.ceil(mag.shape[1] / max_cols))
        new_t = mag.shape[1] // factor
        trimmed = mag[:, : new_t * factor]
        mag = trimmed.reshape(trimmed.shape[0], new_t, factor).mean(axis=2)
        t = t[: new_t * factor : factor]

    ref = max(float(mag.max()), 1e-9)
    db = 20.0 * np.log10(np.maximum(mag, ref * 1e-6) / ref)
    db = np.clip(db, -dynamic_range_db, 0.0).astype(np.float32)
    return SpectrogramImage(
        magnitude_db=db,
        freqs=f.astype(np.float32),
        times=t.astype(np.float32),
        sr=sr,
        n_fft=n_fft,
        hop=hop,
    )


def viridis_colormap(normalized: np.ndarray) -> np.ndarray:
    """Small built-in viridis LUT to avoid matplotlib at runtime."""
    # 13-stop LUT that's visually close to viridis; interpolated linearly.
    stops = np.array(
        [
            [68, 1, 84],
            [72, 35, 116],
            [64, 67, 135],
            [52, 94, 141],
            [41, 120, 142],
            [32, 144, 140],
            [34, 167, 132],
            [68, 190, 112],
            [121, 209, 81],
            [189, 222, 38],
            [253, 231, 36],
            [253, 231, 36],
            [253, 231, 36],
        ],
        dtype=np.float32,
    )
    n = stops.shape[0] - 1
    x = np.clip(normalized, 0.0, 1.0) * n
    lo = np.floor(x).astype(np.int32)
    hi = np.clip(lo + 1, 0, n)
    frac = (x - lo)[..., None]
    rgb = stops[lo] * (1.0 - frac) + stops[hi] * frac
    return rgb.astype(np.uint8)


def to_rgb_image(spec: SpectrogramImage) -> np.ndarray:
    """Return an RGB uint8 array (H, W, 3) for display. Row 0 = high freq (top)."""
    db = spec.magnitude_db
    # Normalize 0..1 (higher dB = brighter).
    rng = float(db.max() - db.min()) or 1.0
    norm = (db - db.min()) / rng
    rgb = viridis_colormap(norm)
    # Flip so rows go high freq -> low freq top-down.
    return np.flipud(rgb)
