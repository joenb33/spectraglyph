from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image

BgMode = Literal[
    "alpha",
    "auto",
    "remove_white",
    "remove_black",
    "chroma",
    "luminance",
]


@dataclass
class MaskOptions:
    mode: BgMode = "alpha"
    threshold: float = 0.15
    chroma_rgb: tuple[int, int, int] | None = None
    invert: bool = False
    gamma: float = 1.0


def load_image(path: str | os.PathLike) -> Image.Image:
    img = Image.open(path)
    img.load()
    return img


def to_mask(img: Image.Image, opts: MaskOptions) -> np.ndarray:
    """Return a float32 mask in [0, 1] where 1 = draw, 0 = transparent."""
    if opts.mode == "alpha":
        mask = _mask_from_alpha(img)
    elif opts.mode == "auto":
        mask = _mask_auto(img, opts.threshold)
    elif opts.mode == "remove_white":
        mask = _mask_remove_color(img, (255, 255, 255), opts.threshold)
    elif opts.mode == "remove_black":
        mask = _mask_remove_color(img, (0, 0, 0), opts.threshold)
    elif opts.mode == "chroma":
        key = opts.chroma_rgb or (0, 255, 0)
        mask = _mask_remove_color(img, key, opts.threshold)
    elif opts.mode == "luminance":
        mask = _mask_luminance(img)
    else:
        raise ValueError(f"Unknown bg mode: {opts.mode}")

    if opts.invert:
        mask = 1.0 - mask
    if opts.gamma and opts.gamma != 1.0:
        mask = np.clip(mask, 0.0, 1.0) ** float(opts.gamma)
    return mask.astype(np.float32, copy=False)


def _mask_from_alpha(img: Image.Image) -> np.ndarray:
    """Prefer the alpha channel if the PNG has any real transparency."""
    if img.mode in ("RGBA", "LA"):
        a = np.asarray(img.split()[-1], dtype=np.float32) / 255.0
        # Any transparent pixel → alpha is meaningful, use it directly.
        if a.min() < 0.999:
            return a
        # Fully opaque image → alpha carries no shape info. Use luminance.
        return _mask_luminance(img)
    if img.mode == "P" and "transparency" in img.info:
        # Paletted PNG with transparency — convert and use alpha.
        a = np.asarray(img.convert("RGBA").split()[-1], dtype=np.float32) / 255.0
        if a.min() < 0.999:
            return a
    return _mask_luminance(img)


def _mask_luminance(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.float32) / 255.0


def _mask_remove_color(
    img: Image.Image, key: tuple[int, int, int], threshold: float
) -> np.ndarray:
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    key_arr = np.array(key, dtype=np.float32) / 255.0
    dist = np.sqrt(np.sum((rgb - key_arr) ** 2, axis=2) / 3.0)
    # Smooth transition near the threshold.
    soft = np.clip((dist - threshold) / max(threshold, 1e-3), 0.0, 1.0)
    return soft


def _mask_auto(img: Image.Image, threshold: float) -> np.ndarray:
    """Pick the dominant corner color as bg key; respect alpha if present."""
    rgba = img.convert("RGBA")
    arr = np.asarray(rgba, dtype=np.float32) / 255.0
    alpha = arr[..., 3]
    rgb = arr[..., :3]
    h, w = rgb.shape[:2]
    corners = np.stack([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
    key = corners.mean(axis=0)
    dist = np.sqrt(np.sum((rgb - key) ** 2, axis=2) / 3.0)
    soft = np.clip((dist - threshold) / max(threshold, 1e-3), 0.0, 1.0)
    if alpha.max() > 0.999 and alpha.min() >= 0.999:
        return soft
    return np.minimum(soft, alpha)


def resize_mask(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize mask to (height, width) using high-quality Lanczos."""
    if width <= 0 or height <= 0:
        return np.zeros((max(height, 1), max(width, 1)), dtype=np.float32)
    arr = np.clip(mask * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="L").resize((width, height), Image.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def preview_rgba(mask: np.ndarray, tint: tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    """Build an RGBA preview image (uint8) from the 0-1 mask."""
    h, w = mask.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0] = tint[0]
    out[..., 1] = tint[1]
    out[..., 2] = tint[2]
    out[..., 3] = np.clip(mask * 255.0, 0, 255).astype(np.uint8)
    return out
