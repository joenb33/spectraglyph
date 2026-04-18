from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import signal

from .image_processor import resize_mask

Mode = Literal["invisible", "full_range"]


@dataclass
class WatermarkParams:
    mode: Mode = "invisible"
    start_s: float = 0.0
    duration_s: float = 3.0
    freq_min_hz: float = 15_000.0
    freq_max_hz: float = 20_000.0
    strength_db: float = -24.0
    n_fft: int = 4096
    hop: int = 1024
    seed: int = 1337


def _stft(audio: np.ndarray, sr: int, n_fft: int, hop: int):
    win = signal.windows.hann(n_fft, sym=False)
    f, t, Z = signal.stft(
        audio,
        fs=sr,
        window=win,
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary="zeros",
        padded=True,
    )
    return f, t, Z


def _istft(Z: np.ndarray, sr: int, n_fft: int, hop: int, length: int) -> np.ndarray:
    win = signal.windows.hann(n_fft, sym=False)
    _, x = signal.istft(
        Z,
        fs=sr,
        window=win,
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary=True,
    )
    return x[:length].astype(np.float32, copy=False)


def _bin_ranges(
    f: np.ndarray, t: np.ndarray, p: WatermarkParams, sr: int
) -> tuple[int, int, int, int]:
    nyq = sr / 2.0
    f_min = max(0.0, min(p.freq_min_hz, nyq - 1))
    f_max = max(f_min + 1, min(p.freq_max_hz, nyq - 1))
    f_lo = int(np.searchsorted(f, f_min))
    f_hi = int(np.searchsorted(f, f_max))
    f_hi = max(f_hi, f_lo + 1)

    t_start = max(0.0, p.start_s)
    t_end = max(t_start + 1e-3, t_start + p.duration_s)
    t_lo = int(np.searchsorted(t, t_start))
    t_hi = int(np.searchsorted(t, t_end))
    t_hi = min(max(t_hi, t_lo + 1), len(t))
    return f_lo, f_hi, t_lo, t_hi


def _build_stamp_audio(
    audio_len: int,
    sr: int,
    mask01: np.ndarray,
    params: WatermarkParams,
) -> np.ndarray:
    """Return a time-domain watermark signal the same length as the audio."""
    # Build an empty STFT matrix with the same shape as the audio's STFT would produce.
    # Use a silent reference signal to get the right dims.
    ref = np.zeros(audio_len, dtype=np.float32)
    f, t, Z = _stft(ref, sr, params.n_fft, params.hop)

    f_lo, f_hi, t_lo, t_hi = _bin_ranges(f, t, params, sr)
    region_h = f_hi - f_lo
    region_w = t_hi - t_lo
    if region_h <= 0 or region_w <= 0:
        return ref

    mask_flip = np.flipud(mask01)
    mask_rs = resize_mask(mask_flip, width=region_w, height=region_h)

    rng = np.random.default_rng(params.seed)
    phase = rng.uniform(-np.pi, np.pi, size=mask_rs.shape)
    Z[f_lo:f_hi, t_lo:t_hi] = (mask_rs * np.exp(1j * phase)).astype(Z.dtype)

    return _istft(Z, sr, params.n_fft, params.hop, audio_len)


def embed_watermark(
    audio: np.ndarray,
    sr: int,
    mask01: np.ndarray,
    params: WatermarkParams,
) -> np.ndarray:
    """Embed `mask01` (HxW in [0,1]) into `audio` via STFT-domain amplitude injection.

    `strength_db` is interpreted as the watermark's rms (inside its active region) relative
    to the original audio's rms — so -24 dB means the watermark is about 1/16th the level
    of the original's rms in the active window. Output length equals input length.
    """
    if audio.ndim == 2:
        channels = [
            embed_watermark(audio[:, c], sr, mask01, params) for c in range(audio.shape[1])
        ]
        return np.stack(channels, axis=1)

    audio = audio.astype(np.float32, copy=False)
    length = len(audio)

    # 1) Build raw watermark in time domain (before scaling).
    stamp = _build_stamp_audio(length, sr, mask01, params)

    start = int(max(0.0, params.start_s) * sr)
    end = int(min(length, (params.start_s + params.duration_s) * sr))
    if end <= start or not np.any(stamp):
        return audio

    # 2) Scale to match target dB relative to the audio's rms in the active window.
    audio_window = audio[start:end]
    audio_rms = float(np.sqrt(np.mean(audio_window ** 2))) if audio_window.size else 0.0
    audio_rms = max(audio_rms, 1e-4)  # floor so silent audio still gets a watermark
    stamp_rms = float(np.sqrt(np.mean(stamp[start:end] ** 2))) or 1e-9
    target_rms = audio_rms * (10.0 ** (params.strength_db / 20.0))
    gain = target_rms / stamp_rms

    if params.mode == "full_range":
        # Same scaling as invisible mode — the mode difference is primarily the
        # suggested frequency range. The key difference: nothing.
        pass

    stamp_scaled = stamp * gain

    # 3) Add and clamp against clipping.
    out = audio + stamp_scaled
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 0.999:
        out = out * (0.999 / peak)
    return out.astype(np.float32, copy=False)


def recommend_freq_range(sr: int, mode: Mode) -> tuple[float, float]:
    nyq = sr / 2.0
    if mode == "invisible":
        lo = 15_000.0
        hi = min(20_000.0, nyq - 500.0)
        if hi <= lo:
            lo = max(nyq * 0.7, 100.0)
            hi = nyq - 500.0
        return lo, hi
    return 300.0, min(8_000.0, nyq - 500.0)
