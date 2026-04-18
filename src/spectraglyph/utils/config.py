from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    d = Path(base) / "SpectraGlyph"
    d.mkdir(parents=True, exist_ok=True)
    return d


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
