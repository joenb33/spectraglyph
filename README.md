<div align="center">

<img src="assets/logo.svg" alt="SpectraGlyph logo" width="128" height="128" />

# SpectraGlyph

**Hide your logo in sound. Reveal it in the spectrogram.**

<em>A Windows desktop app that paints images and text into the upper spectrum of an audio file — inaudible to the ear, crystal-clear to Audacity, Spek, or Sonic Visualiser.</em>

[![CI](https://github.com/joenb33/spectraglyph/actions/workflows/ci.yml/badge.svg)](https://github.com/joenb33/spectraglyph/actions/workflows/ci.yml)
[![Release](https://github.com/joenb33/spectraglyph/actions/workflows/release.yml/badge.svg)](https://github.com/joenb33/spectraglyph/actions/workflows/release.yml)
[![Latest release](https://img.shields.io/github/v/release/joenb33/spectraglyph?sort=semver&display_name=tag&label=release)](https://github.com/joenb33/spectraglyph/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/joenb33/spectraglyph/total?color=%233a7bd5)](https://github.com/joenb33/spectraglyph/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Qt](https://img.shields.io/badge/UI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white)](#download-windows-exe)
[![Languages](https://img.shields.io/badge/UI-English%20%7C%20Swedish-cccccc)](#localization)

<img src="docs/hero_spectrogram.png" alt="Spectrogram of an audio file with the word 'SpectraGlyph' painted into the 17–21 kHz band" width="100%" />

</div>

---

## Why it's cool

Human speech and most music concentrate energy **below ~8 kHz**. SpectraGlyph paints your image into the **upper spectrum** (classic "invisible" mode: **15–20 kHz**), where everyday speakers, mics, and hearing barely notice — so the mix **stays clean to the ear**, yet the picture is **crystal-clear** the moment someone views a spectrogram. Same spirit as hidden art in game soundtracks — here tuned so you control time, band, and strength.

---

## Features

| | |
|---|---|
| **Dual modes** | **Invisible (>15 kHz)** — watermark above the vocal/instrument body; **Full range** — use the whole spectrum for bolder visuals (may color the sound at high strength). |
| **Image or text** | Drop PNG/JPG/WebP or type directly in the app — your message becomes part of the spectrum. |
| **Masking toolkit** | Alpha, auto-detect background, remove white/black, luminance, invert — get a crisp mask without leaving the UI. |
| **Live spectrogram** | Pan and resize the **time × frequency** region; preview updates follow your edits. |
| **Export** | Write **WAV**, **FLAC**, or **MP3** (with a heads-up when codecs affect watermark fidelity). |
| **Presets + view guide** | Save recipes; **copy FFT settings** to the clipboard so viewers can paste the same view into Audacity and see exactly what you intended. |
| **Languages** | **Swedish** and **English** — **View → Language** (saved under the [paths in Localization](#localization)). |
| **Shortcuts & help** | **Ctrl+O** / **Ctrl+I** / **Ctrl+E**; **Help → Keyboard shortcuts…** lists them. |
| **Where data is stored** | Next to **`SpectraGlyph.exe`**: `SpectraGlyph_data\` (settings + presets) when writable; otherwise `%APPDATA%\SpectraGlyph`. Window size and last open/save folders are remembered. |
| **Long audio** | Files **> ~2 min** or **> ~40 MB** trigger a choice: load everything or only a **time range** (faster). Progress is shown while decoding and building the spectrogram. |

---

## Download (Windows `.exe`)

Grab the signed-by-GitHub-Actions binary from the [latest release](https://github.com/joenb33/spectraglyph/releases/latest). Each stable build is attached as `SpectraGlyph-<version>-Windows-x64.exe`. Preview builds appear as **pre-releases** when changes are pushed to the `release` branch or the workflow is triggered manually.

> **SmartScreen note:** the `.exe` is not code-signed with a commercial cert, so Windows may show a warning the first time you run it. Click "More info → Run anyway" if you trust this project.

---

## How viewers reveal the watermark

1. Open the exported file in **Audacity**, **Spek**, or **Sonic Visualiser**.
2. Switch to **spectrogram** view (e.g. Audacity: track spectrogram).
3. Typical settings that work well: **FFT size 4096**, **Hann** window, **~80 dB** dynamic range.
4. Scroll to the time range and frequency band you chose at export (use **View guide** in the app for a copy-paste cheat sheet).

---

## Requirements

- **Windows** (primary target; Qt + audio stack tested there)
- **Python 3.10+** (only if running from source)

## Quick start (from source)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Run tests:

```powershell
pytest -q
```

## Build a standalone `.exe`

```powershell
pyinstaller pyinstaller.spec
```

Output: `dist\SpectraGlyph.exe`

---

## Localization

The desktop UI is available in **Swedish** and **English** (**View → Language** in the app). Code comments and this README are primarily **English** so the project stays approachable for contributors worldwide.

**Where settings are stored:** If you run the **built `.exe`**, presets and language live in a folder next to the executable: `SpectraGlyph_data\` (delete that folder together with the app). If the app cannot create that folder (e.g. install under `Program Files` without write access), it falls back to `%APPDATA%\SpectraGlyph`. Running from **source** (`python main.py`) always uses `%APPDATA%\SpectraGlyph`.

---

## Project layout

- `main.py` — application entry
- `src/spectraglyph/` — GUI, DSP, audio I/O, watermark core
- `assets/` — icon, logo, and bundled resources for builds
- `docs/` — README imagery (spectrogram hero, future screenshots)
- `scripts/generate_branding.py` — regenerates `assets/icon.*` and `docs/hero_spectrogram.png`
- `tests/` — pytest coverage for mask/text, watermark embedding, and audio I/O

---

## Repository

- **Product name:** **SpectraGlyph**
- **Upstream:** [github.com/joenb33/spectraglyph](https://github.com/joenb33/spectraglyph)
- **Security:** see [SECURITY.md](SECURITY.md)
- **Contributing & release process:** see [CONTRIBUTING.md](CONTRIBUTING.md)
- **Changelog:** see [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT — see [LICENSE](LICENSE).
