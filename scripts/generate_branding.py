"""Regenerate branding assets: icon.png, icon.ico, and the README hero spectrogram.

Run from the repo root::

    python scripts/generate_branding.py

Outputs:
    assets/icon.png          256x256 PNG used by the Qt window and README.
    assets/icon.ico          Multi-size Windows ICO used by PyInstaller + the .exe.
    docs/hero_spectrogram.png  Rendered spectrogram containing the watermarked
                               word "SpectraGlyph" in the 17-20 kHz band.

The icon design mirrors ``assets/logo.svg`` (same 7-bar arch) so the SVG can be
swapped in later without the raster assets drifting visually.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import numpy as np
from PIL import Image, ImageDraw

ASSETS = REPO / "assets"
DOCS = REPO / "docs"
ASSETS.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

BG_TOP = (31, 36, 48)
BG_BOT = (15, 18, 24)
# Viridis stops used by the 7-bar arch (matches assets/logo.svg).
BARS = [
    (0.36, (68, 1, 84)),
    (0.60, (59, 82, 139)),
    (0.82, (33, 145, 140)),
    (1.00, (253, 231, 37)),
    (0.82, (33, 145, 140)),
    (0.60, (59, 82, 139)),
    (0.36, (68, 1, 84)),
]


def _vertical_gradient(size: int) -> Image.Image:
    bg = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(bg)
    for y in range(size):
        t = y / (size - 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOT[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOT[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOT[2] * t)
        d.line([(0, y), (size, y)], fill=(r, g, b))
    return bg


def make_icon(size: int = 256) -> Image.Image:
    bg = _vertical_gradient(size)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=size // 6, fill=255
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(bg, (0, 0), mask)

    draw = ImageDraw.Draw(canvas)
    n = len(BARS)
    pad_x = int(size * 0.15)
    gap = max(2, size // 48)
    avail = size - 2 * pad_x - (n - 1) * gap
    bar_w = max(1, avail // n)
    total_w = bar_w * n + gap * (n - 1)
    x0 = (size - total_w) // 2
    cy = size // 2
    h_max = int(size * 0.48)

    for i, (scale, color) in enumerate(BARS):
        h = int(h_max * scale)
        x = x0 + i * (bar_w + gap)
        y0 = cy - h // 2
        y1 = y0 + h
        r = bar_w // 3
        draw.rounded_rectangle((x, y0, x + bar_w, y1), radius=r, fill=(*color, 255))

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), mask)
    return out


def write_icon() -> None:
    icon = make_icon(256)
    icon.save(ASSETS / "icon.png", format="PNG")
    # Multi-size ICO so Windows picks a crisp variant per context.
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon.save(ASSETS / "icon.ico", format="ICO", sizes=sizes)


def write_hero_spectrogram() -> None:
    # Deferred imports: spectraglyph package sits under src/.
    from scipy import signal

    from spectraglyph.core.spectrogram_renderer import compute_spectrogram, to_rgb_image
    from spectraglyph.core.text_renderer import TextStyle, render_text_mask
    from spectraglyph.core.watermark import WatermarkParams, embed_watermark

    sr = 48_000
    duration = 6.0
    rng = np.random.default_rng(20260418)

    # Quiet low-pass noise: broadband below ~5 kHz, near-silent above — lets the
    # upper-band watermark "paint" onto a clean dark backdrop in the render.
    raw = rng.standard_normal(int(sr * duration)).astype(np.float32) * 0.18
    b, a = signal.butter(6, 5_000 / (sr / 2), btype="low")
    noise = signal.lfilter(b, a, raw).astype(np.float32)

    text_mask = render_text_mask(
        TextStyle(text="SpectraGlyph", font_size=220, padding=16, letter_spacing=2)
    )
    params = WatermarkParams(
        mode="invisible",
        start_s=0.5,
        duration_s=duration - 1.0,
        freq_min_hz=16_800.0,
        freq_max_hz=20_800.0,
        strength_db=-3.0,
        n_fft=2048,
        hop=256,
    )
    watermarked = embed_watermark(noise, sr, text_mask, params)
    spec = compute_spectrogram(
        watermarked, sr, n_fft=2048, hop=256, max_cols=1600, dynamic_range_db=90.0
    )
    rgb = to_rgb_image(spec)
    img = Image.fromarray(rgb, mode="RGB")

    # Force a wide cinematic aspect regardless of STFT grid shape.
    img = img.resize((1400, 500), Image.BICUBIC)
    img.save(DOCS / "hero_spectrogram.png", format="PNG", optimize=True)


def main() -> None:
    write_icon()
    write_hero_spectrogram()
    print(f"Wrote {ASSETS/'icon.png'}")
    print(f"Wrote {ASSETS/'icon.ico'}")
    print(f"Wrote {DOCS/'hero_spectrogram.png'}")


if __name__ == "__main__":
    main()
