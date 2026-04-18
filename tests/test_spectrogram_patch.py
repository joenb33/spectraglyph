import numpy as np
from scipy import signal

from spectraglyph.core.spectrogram_renderer import (
    compute_spectrogram,
    compute_spectrogram_patch,
    splice_spectrogram_patch,
)
from spectraglyph.core.watermark import (
    WatermarkParams,
    embed_watermark,
    embed_watermark_local,
)


SR = 48_000


def _noise(seconds: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(int(seconds * SR)) * 0.15).astype(np.float32)


def _lowpass_noise(seconds: float, seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = (rng.standard_normal(int(seconds * SR)) * 0.2).astype(np.float32)
    b, a = signal.butter(6, 5000 / (SR / 2), btype="low")
    return signal.lfilter(b, a, raw).astype(np.float32)


def _rect_mask(h: int, w: int) -> np.ndarray:
    m = np.zeros((h, w), dtype=np.float32)
    m[h // 4 : h * 3 // 4, w // 4 : w * 3 // 4] = 1.0
    return m


def test_patch_of_unmodified_audio_matches_base_columns():
    audio = _noise(4.0)
    base = compute_spectrogram(audio, SR)
    # Pick a time window somewhere in the middle.
    t0, t1 = 1.0, 2.5
    patch, c0, c1 = compute_spectrogram_patch(
        audio, base, time_start_s=t0, time_end_s=t1
    )
    assert patch.shape == (base.magnitude_db.shape[0], c1 - c0)
    # Columns that came from the patch must match the base's columns within a
    # small tolerance (floating-point + boundary handling). Ignore the extreme
    # edge columns where STFT boundary tapering can cause tiny differences.
    if (c1 - c0) > 4:
        a = patch[:, 2:-2]
        b = base.magnitude_db[:, c0 + 2 : c1 - 2]
        assert np.max(np.abs(a - b)) < 1e-2


def test_splice_with_identical_patch_leaves_base_unchanged():
    audio = _noise(3.0)
    base = compute_spectrogram(audio, SR)
    patch, c0, c1 = compute_spectrogram_patch(
        audio, base, time_start_s=0.5, time_end_s=1.5
    )
    spliced = splice_spectrogram_patch(base, patch, c0, c1)
    # Outside the patch range: bit-identical to base.
    np.testing.assert_array_equal(spliced.magnitude_db[:, :c0], base.magnitude_db[:, :c0])
    np.testing.assert_array_equal(spliced.magnitude_db[:, c1:], base.magnitude_db[:, c1:])


def test_preview_splice_matches_full_recompute_in_watermark_band():
    # The whole goal: running the fast preview (local embed + splice) should give
    # essentially the same spectrogram, inside the watermark band, as running the
    # old slow path (global embed + full recompute).
    audio = _lowpass_noise(5.0)
    mask = _rect_mask(64, 128)
    params = WatermarkParams(
        mode="invisible",
        start_s=1.5,
        duration_s=1.5,
        freq_min_hz=16_000,
        freq_max_hz=20_000,
        strength_db=-18.0,
    )
    base = compute_spectrogram(audio, SR)

    # Slow path (reference): embed globally, recompute spectrogram from scratch.
    full_out = embed_watermark(audio, SR, mask, params)
    slow_spec = compute_spectrogram(full_out, SR)

    # Fast path: local embed, compute only the patch, splice it in.
    local_out = embed_watermark_local(audio, SR, mask, params)
    pad_s = params.n_fft / SR
    t0 = max(0.0, params.start_s - pad_s)
    t1 = params.start_s + params.duration_s + pad_s
    patch, c0, c1 = compute_spectrogram_patch(
        local_out, base, time_start_s=t0, time_end_s=t1
    )
    fast_spec = splice_spectrogram_patch(base, patch, c0, c1)

    # Inside the watermark band and inside the watermark time window, both
    # spectrograms should show a clear energy bump relative to the base's own
    # band energy (i.e. both paths produce a visible watermark). We don't
    # compare absolute dB between the two paths because they use different
    # references for normalization (and the global path may apply a uniform
    # clip-guard that shifts its levels).
    freqs = base.freqs
    band = (freqs >= 16_000) & (freqs <= 20_000)
    if (c1 - c0) > 4:
        col_slice = slice(c0 + 2, c1 - 2)
        base_band_mean = float(base.magnitude_db[band][:, col_slice].mean())
        fast_band_mean = float(fast_spec.magnitude_db[band][:, col_slice].mean())
        slow_band_mean = float(slow_spec.magnitude_db[band][:, col_slice].mean())
        # Fast path shows a bump vs. the original base in that band.
        assert fast_band_mean - base_band_mean > 10.0, (
            f"fast path didn't lift the watermark band: "
            f"base={base_band_mean:.1f} fast={fast_band_mean:.1f}"
        )
        # The two paths are in the same ballpark (within 10 dB).
        assert abs(fast_band_mean - slow_band_mean) < 10.0, (
            f"fast vs slow band mean differs by "
            f"{abs(fast_band_mean - slow_band_mean):.1f} dB"
        )
