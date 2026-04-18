import numpy as np
from scipy import signal

from spectraglyph.core.watermark import WatermarkParams, embed_watermark
from spectraglyph.core.image_processor import MaskOptions, to_mask
from PIL import Image


SR = 48_000


def _noise(sr: int, seconds: float, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # Low-frequency noise — nothing above ~5 kHz so high-freq watermark will stand out.
    raw = rng.standard_normal(int(seconds * sr)).astype(np.float32) * 0.2
    b, a = signal.butter(6, 5000 / (sr / 2), btype="low")
    return signal.lfilter(b, a, raw).astype(np.float32)


def _rect_mask(h: int, w: int) -> np.ndarray:
    m = np.zeros((h, w), dtype=np.float32)
    m[h // 4 : h * 3 // 4, w // 4 : w * 3 // 4] = 1.0
    return m


def test_invisible_mode_adds_energy_in_target_band():
    audio = _noise(SR, 3.0)
    mask = _rect_mask(64, 128)
    params = WatermarkParams(
        mode="invisible",
        start_s=0.5,
        duration_s=2.0,
        freq_min_hz=16_000,
        freq_max_hz=20_000,
        strength_db=-18.0,
    )
    out = embed_watermark(audio, SR, mask, params)

    assert out.shape == audio.shape
    # Compute spectral energy above 16 kHz before and after.
    def band_energy(x: np.ndarray, lo: float, hi: float) -> float:
        f, _, Z = signal.stft(x, fs=SR, nperseg=params.n_fft, noverlap=params.n_fft - params.hop)
        idx = (f >= lo) & (f <= hi)
        return float(np.mean(np.abs(Z[idx]) ** 2))

    before = band_energy(audio, 16_000, 20_000)
    after = band_energy(out, 16_000, 20_000)
    assert after > before * 10, f"expected 10x energy bump, got {after/before:.2f}x"


def test_no_modification_outside_target_band():
    audio = _noise(SR, 2.0)
    mask = _rect_mask(32, 64)
    params = WatermarkParams(
        mode="invisible",
        start_s=0.0,
        duration_s=2.0,
        freq_min_hz=17_000,
        freq_max_hz=20_000,
        strength_db=-12.0,
    )
    out = embed_watermark(audio, SR, mask, params)

    f, _, Z_in = signal.stft(audio, fs=SR, nperseg=params.n_fft, noverlap=params.n_fft - params.hop)
    _, _, Z_out = signal.stft(out, fs=SR, nperseg=params.n_fft, noverlap=params.n_fft - params.hop)
    # Energy below 8 kHz should be virtually unchanged.
    low = f < 8_000
    err = np.mean(np.abs(np.abs(Z_in[low]) - np.abs(Z_out[low])) ** 2)
    baseline = np.mean(np.abs(Z_in[low]) ** 2)
    assert err / max(baseline, 1e-12) < 0.01


def test_mask_from_alpha_png():
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    for y in range(10, 40):
        for x in range(10, 40):
            img.putpixel((x, y), (255, 255, 255, 255))
    mask = to_mask(img, MaskOptions(mode="alpha"))
    assert mask.shape == (50, 50)
    assert mask[25, 25] == 1.0
    assert mask[0, 0] == 0.0


def test_remove_white_background():
    img = Image.new("RGB", (40, 40), (255, 255, 255))
    for y in range(10, 30):
        for x in range(10, 30):
            img.putpixel((x, y), (20, 20, 20))
    mask = to_mask(img, MaskOptions(mode="remove_white", threshold=0.1))
    assert mask[20, 20] > 0.5
    assert mask[0, 0] < 0.1


def test_stereo_input_stays_stereo():
    mono = _noise(SR, 1.5)
    stereo = np.stack([mono, mono * 0.9], axis=1)
    mask = _rect_mask(32, 32)
    params = WatermarkParams(duration_s=1.5)
    out = embed_watermark(stereo, SR, mask, params)
    assert out.shape == stereo.shape
    assert out.dtype == np.float32
