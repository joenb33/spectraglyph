import numpy as np
from PIL import Image

from spectraglyph.core.image_processor import MaskOptions, to_mask
from spectraglyph.core.text_renderer import TextStyle, render_text_mask


def test_text_respects_padding():
    """Regression: Pillow's default text anchor is ascender-based, so the bbox
    top/left can be non-zero. Prior to the fix, glyphs drew past the padded
    canvas bounds and got clipped."""
    pad = 10
    mask = render_text_mask(TextStyle(text="HEJ", font_size=96, padding=pad))
    ys, xs = np.where(mask > 0.5)
    assert ys.size > 0, "text produced no pixels"
    # Glyphs must sit inside the padded region (allow a 2-pixel slack for
    # anti-aliased glyph edges).
    assert ys.min() >= pad - 2, f"text touches top (min y={ys.min()}, pad={pad})"
    assert ys.max() <= mask.shape[0] - pad + 1, f"text touches bottom (max y={ys.max()})"
    assert xs.min() >= pad - 2, f"text touches left edge (min x={xs.min()})"
    assert xs.max() <= mask.shape[1] - pad + 1, f"text touches right edge (max x={xs.max()})"


def test_text_descender_renders_fully():
    """Descenders (g, y, p, q) used to get cut off because the default anchor
    aligned on the ascender and the canvas was measured from the ascender
    line — losing the part of the glyph below the baseline."""
    # 'y' has a descender, 'o' does not. Both rendered at same font size
    # should yield a taller canvas for the descender word.
    ym = render_text_mask(TextStyle(text="y", font_size=96, padding=0))
    om = render_text_mask(TextStyle(text="o", font_size=96, padding=0))
    assert ym.shape[0] > om.shape[0], (
        f"descender canvas should be taller — got y={ym.shape} o={om.shape}"
    )
    # The 'y' should have bright pixels in the lower half (the descender).
    h = ym.shape[0]
    lower_half = ym[h // 2 :]
    assert lower_half.max() > 0.5, "descender not rendered in lower half"


def test_white_on_transparent_png_keeps_motif():
    """Regression: a white motif on a transparent background used to become
    a blank mask because _mask_from_alpha fell through to _mask_auto, which
    sampled corner RGB (which on many PNG exporters is white) and removed
    white as the 'background'."""
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))  # transparent bg
    for y in range(10, 30):
        for x in range(10, 30):
            img.putpixel((x, y), (255, 255, 255, 255))  # white opaque motif
    mask = to_mask(img, MaskOptions(mode="alpha"))
    assert mask[20, 20] > 0.95, "white motif should be visible in the mask"
    assert mask[0, 0] < 0.05, "transparent bg should be hidden"


def test_white_on_transparent_png_with_white_rgb_in_alpha0():
    """Some exporters leave RGB = (255,255,255) in transparent regions too.
    Alpha still correctly flags them as transparent — the mask must respect
    alpha even when RGB alone would be ambiguous."""
    img = Image.new("RGBA", (40, 40), (255, 255, 255, 0))  # transparent but white RGB
    for y in range(10, 30):
        for x in range(10, 30):
            img.putpixel((x, y), (255, 255, 255, 255))
    mask = to_mask(img, MaskOptions(mode="alpha"))
    assert mask[20, 20] > 0.95
    assert mask[0, 0] < 0.05


def test_fully_opaque_png_falls_back_to_luminance():
    img = Image.new("RGBA", (20, 20), (255, 255, 255, 255))  # opaque white
    for y in range(5, 15):
        for x in range(5, 15):
            img.putpixel((x, y), (0, 0, 0, 255))  # opaque black motif
    mask = to_mask(img, MaskOptions(mode="alpha"))
    # With alpha fully opaque, luminance takes over — white pixels=1, black pixels=0.
    assert mask[0, 0] > 0.95
    assert mask[10, 10] < 0.05
