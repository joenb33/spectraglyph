from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


# Subfolder next to the .exe (frozen build) holding settings + presets — delete this folder with the app.
_PORTABLE_DATA_DIRNAME = "SpectraGlyph_data"


@dataclass
class AppSettings:
    """User preferences in config_dir() / settings.json (with presets.json)."""

    ui_language: str = "auto"  # auto | sv | en
    last_audio_dir: str = ""
    last_image_dir: str = ""
    last_export_dir: str = ""
    # QByteArray from saveGeometry(), base64-encoded
    window_geometry_b64: str = ""
    # Main splitter [spectrogram, right panel]; empty means use defaults in the UI
    splitter_sizes: list[int] = field(default_factory=lambda: [820, 520])


def _appdata_config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "SpectraGlyph"


def _portable_config_dir() -> Path:
    """Directory next to SpectraGlyph.exe (PyInstaller onefile)."""
    return Path(sys.executable).resolve().parent / _PORTABLE_DATA_DIRNAME


def _maybe_migrate_appdata_to_portable(portable: Path) -> None:
    """One-time copy from legacy %APPDATA%\\SpectraGlyph if portable folder is new and empty."""
    if any(portable.iterdir()):
        return
    legacy = _appdata_config_dir()
    if not legacy.is_dir():
        return
    for name in ("settings.json", "presets.json"):
        src = legacy / name
        dst = portable / name
        if src.is_file() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass


def config_dir() -> Path:
    """Where settings.json and presets.json live.

    - **Frozen (.exe)**: ``<folder containing SpectraGlyph.exe>/SpectraGlyph_data/`` so removing
      the install folder removes user data. If that location is not writable (e.g. Program Files),
      falls back to ``%APPDATA%\\SpectraGlyph`` (same as dev).
    - **Running from source (``python main.py``)**: ``%APPDATA%\\SpectraGlyph`` (or XDG-style on
      non-Windows) so the repo stays clean.
    """
    if getattr(sys, "frozen", False):
        portable = _portable_config_dir()
        try:
            portable.mkdir(parents=True, exist_ok=True)
        except OSError:
            d = _appdata_config_dir()
            d.mkdir(parents=True, exist_ok=True)
            return d
        _maybe_migrate_appdata_to_portable(portable)
        return portable
    d = _appdata_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_path() -> Path:
    return config_dir() / "settings.json"


def normalized_existing_dir(path: str) -> str:
    """Return a usable directory for QFileDialog, or \"\" if missing."""
    if not path:
        return ""
    try:
        p = Path(path)
        if p.is_dir():
            return str(p.resolve())
    except OSError:
        pass
    return ""


def load_app_settings() -> AppSettings:
    path = settings_path()
    if not path.exists():
        return AppSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        lang = raw.get("ui_language", "auto")
        if lang not in ("auto", "sv", "en"):
            lang = "auto"
        sizes = raw.get("splitter_sizes")
        if not isinstance(sizes, list) or len(sizes) != 2:
            sizes = [820, 520]
        else:
            sizes = [int(sizes[0]), int(sizes[1])]
        return AppSettings(
            ui_language=lang,
            last_audio_dir=str(raw.get("last_audio_dir") or ""),
            last_image_dir=str(raw.get("last_image_dir") or ""),
            last_export_dir=str(raw.get("last_export_dir") or ""),
            window_geometry_b64=str(raw.get("window_geometry_b64") or ""),
            splitter_sizes=sizes,
        )
    except (json.JSONDecodeError, TypeError, OSError, ValueError):
        return AppSettings()


def save_app_settings(settings: AppSettings) -> None:
    path = settings_path()
    payload = {
        "ui_language": settings.ui_language,
        "last_audio_dir": settings.last_audio_dir,
        "last_image_dir": settings.last_image_dir,
        "last_export_dir": settings.last_export_dir,
        "window_geometry_b64": settings.window_geometry_b64,
        "splitter_sizes": settings.splitter_sizes,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@dataclass
class Preset:
    name: str
    mode: str = "invisible"
    start_s: float = 0.0
    duration_s: float = 3.0
    freq_min_hz: float = 15_000.0
    freq_max_hz: float = 20_000.0
    strength_db: float = -24.0
    bg_mode: str = "alpha"
    bg_threshold: float = 0.15
    invert: bool = False


@dataclass
class Presets:
    items: list[Preset] = field(default_factory=list)

    @classmethod
    def load(cls) -> "Presets":
        path = config_dir() / "presets.json"
        if not path.exists():
            return cls(items=_default_presets())
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return cls(items=[Preset(**p) for p in raw.get("items", [])])
        except (json.JSONDecodeError, TypeError, KeyError):
            return cls(items=_default_presets())

    def save(self) -> None:
        path = config_dir() / "presets.json"
        path.write_text(
            json.dumps({"items": [asdict(p) for p in self.items]}, indent=2),
            encoding="utf-8",
        )


def _default_presets() -> list[Preset]:
    return [
        Preset(name="Invisible (top end)", mode="invisible", freq_min_hz=15_000, freq_max_hz=20_000, strength_db=-24.0),
        Preset(name="Invisible subtle", mode="invisible", freq_min_hz=16_000, freq_max_hz=19_000, strength_db=-30.0),
        Preset(name="Full range vocal", mode="full_range", freq_min_hz=300, freq_max_hz=6_000, strength_db=-18.0),
    ]
