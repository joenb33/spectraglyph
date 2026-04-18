from __future__ import annotations

from dataclasses import dataclass, replace

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
    ref_magnitude: float = 1.0       # linear peak used for dB normalization
    downsample_factor: int = 1       # time downsample applied
    dynamic_range_db: float = 80.0


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

    factor = 1
    if mag.shape[1] > max_cols:
        factor = int(np.ceil(mag.shape[1] / max_cols))
        new_t = mag.shape[1] // factor
        trimmed = mag[:, : new_t * factor]
        mag = trimmed.reshape(trimmed.shape[0], new_t, factor).mean(axis=2)
        t = t[: new_t * factor : factor]

    ref = max(float(mag.max()), 1e-9)
    db = _mag_to_db(mag, ref, dynamic_range_db)
    return SpectrogramImage(
        magnitude_db=db,
        freqs=f.astype(np.float32),
        times=t.astype(np.float32),
        sr=sr,
        n_fft=n_fft,
        hop=hop,
        ref_magnitude=ref,
        downsample_factor=factor,
        dynamic_range_db=dynamic_range_db,
    )


def _mag_to_db(mag: np.ndarray, ref: float, dynamic_range_db: float) -> np.ndarray:
    db = 20.0 * np.log10(np.maximum(mag, ref * 1e-6) / ref)
    return np.clip(db, -dynamic_range_db, 0.0).astype(np.float32)


def compute_spectrogram_patch(
    audio: np.ndarray,
    base: SpectrogramImage,
    *,
    time_start_s: float,
    time_end_s: float,
) -> tuple[np.ndarray, int, int]:
    """Compute a (F, K) dB patch aligned to ``base`` for the time range [start, end].

    The patch is computed with the same FFT/hop/downsample/ref as ``base`` and can be
    dropped directly into ``base.magnitude_db[:, col_start:col_end]``. Returns
    ``(patch_db, col_start, col_end)`` where the columns are indices into ``base``.

    The caller is responsible for only modifying audio within the requested time range;
    a small amount of padding (``n_fft`` samples) is included in the STFT input so the
    boundary taper does not bleed into the returned columns.
    """
    mono = to_mono(audio)
    total_cols = base.magnitude_db.shape[1]
    stride = base.hop * base.downsample_factor
    col_start = int(max(0, np.floor(time_start_s * base.sr / stride)))
    col_end = int(min(total_cols, np.ceil(time_end_s * base.sr / stride)))
    if col_end <= col_start:
        return np.zeros((base.magnitude_db.shape[0], 0), dtype=np.float32), col_start, col_start

    s_start = col_start * stride
    s_end = col_end * stride
    pad = base.n_fft
    s_start_pad = max(0, s_start - pad)
    s_end_pad = min(len(mono), s_end + pad)

    slice_audio = mono[s_start_pad:s_end_pad]
    if slice_audio.size < base.n_fft:
        slice_audio = np.pad(slice_audio, (0, base.n_fft - slice_audio.size))

    win = signal.windows.hann(base.n_fft, sym=False)
    _, _, Z = signal.stft(
        slice_audio,
        fs=base.sr,
        window=win,
        nperseg=base.n_fft,
        noverlap=base.n_fft - base.hop,
        boundary="zeros",
        padded=True,
    )
    mag = np.abs(Z).astype(np.float32)

    # Frame offset: column k of base corresponds to (sample k*stride) in the global audio;
    # locally that is sample (k*stride - s_start_pad), i.e. hop-frame index
    # (k*stride - s_start_pad) / hop.
    frame_offset = int(round((s_start - s_start_pad) / base.hop))
    factor = base.downsample_factor
    n_patch_cols = col_end - col_start
    frames_needed = n_patch_cols * factor
    end_frame = frame_offset + frames_needed

    if end_frame > mag.shape[1]:
        mag = np.pad(mag, ((0, 0), (0, end_frame - mag.shape[1])))
    mag_sub = mag[:, frame_offset:end_frame]
    if factor > 1:
        mag_ds = mag_sub.reshape(mag_sub.shape[0], n_patch_cols, factor).mean(axis=2)
    else:
        mag_ds = mag_sub

    patch_db = _mag_to_db(mag_ds, base.ref_magnitude, base.dynamic_range_db)
    return patch_db, col_start, col_end


def splice_spectrogram_patch(
    base: SpectrogramImage,
    patch_db: np.ndarray,
    col_start: int,
    col_end: int,
) -> SpectrogramImage:
    """Return a new SpectrogramImage with columns [col_start, col_end) replaced by ``patch_db``."""
    if patch_db.size == 0 or col_end <= col_start:
        return replace(base, magnitude_db=base.magnitude_db.copy())
    new_db = base.magnitude_db.copy()
    width = min(col_end - col_start, patch_db.shape[1], new_db.shape[1] - col_start)
    if width <= 0:
        return replace(base, magnitude_db=new_db)
    new_db[:, col_start : col_start + width] = patch_db[:, :width]
    return replace(base, magnitude_db=new_db)


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
