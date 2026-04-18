from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class TextStyle:
    text: str = "Your text"
    font_path: str | None = None
    font_size: int = 128
    bold: bool = False
    letter_spacing: int = 0
    padding: int = 8


def _resolve_font(style: TextStyle) -> ImageFont.FreeTypeFont:
    candidates: list[str] = []
    if style.font_path:
        candidates.append(style.font_path)
    assets = Path(__file__).resolve().parents[3] / "assets"
    candidates.append(str(assets / "default_font.ttf"))
    candidates.extend([
        "C:/Windows/Fonts/segoeuib.ttf" if style.bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if style.bold else "C:/Windows/Fonts/arial.ttf",
        "arial.ttf",
    ])
    for c in candidates:
        try:
            return ImageFont.truetype(c, size=style.font_size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_text_mask(style: TextStyle) -> np.ndarray:
    """Render `text` to a float32 mask in [0, 1] with tight bounding box + padding.

    Pillow's `draw.text((x,y), ...)` uses the font ascender as the y anchor, not the
    actual glyph top, which can leave the bbox offset. We measure `textbbox` first and
    compensate so the rendered pixels sit exactly inside the canvas.
    """
    text = style.text or ""
    font = _resolve_font(style)

    dummy = Image.new("L", (8, 8), 0)
    draw = ImageDraw.Draw(dummy)
    pad = max(0, style.padding)

    if style.letter_spacing and len(text) > 1:
        metrics = [draw.textbbox((0, 0), ch, font=font) for ch in text]
        widths = [m[2] - m[0] for m in metrics]
        total_w = sum(widths) + style.letter_spacing * (len(text) - 1)
        top = min(m[1] for m in metrics)
        bottom = max(m[3] for m in metrics)
        total_h = bottom - top

        w = max(1, total_w + pad * 2)
        h = max(1, total_h + pad * 2)
        img = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(img)
        x = pad
        for ch, m, cw in zip(text, metrics, widths):
            d.text((x - m[0], pad - top), ch, fill=255, font=font)
            x += cw + style.letter_spacing
    else:
        bbox = draw.textbbox((0, 0), text, font=font)
        left, top, right, bottom = bbox
        w = max(1, (right - left) + pad * 2)
        h = max(1, (bottom - top) + pad * 2)
        img = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(img)
        d.text((pad - left, pad - top), text, fill=255, font=font)

    return np.asarray(img, dtype=np.float32) / 255.0
