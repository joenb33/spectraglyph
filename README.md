# SpectraGlyph

[![CI](https://github.com/joenb33/spectraglyph/actions/workflows/ci.yml/badge.svg)](https://github.com/joenb33/spectraglyph/actions/workflows/ci.yml)
[![Release](https://github.com/joenb33/spectraglyph/actions/workflows/release.yml/badge.svg)](https://github.com/joenb33/spectraglyph/actions/workflows/release.yml)

<p align="center">
  <strong>Your brand lives in the waveform — but only shows up when someone hits “spectrogram.”</strong>
</p>

<p align="center">
  <em>Hide logos and typography inside audio as a near-inaudible spectral watermark. Open the file in Audacity, Spek, or Sonic Visualiser — and watch your image bloom across the frequency axis.</em>
</p>

---

## Why it’s cool

Human speech and most music concentrate energy **below ~8 kHz**. SpectraGlyph paints your image into the **upper spectrum** (classic “invisible” mode: **15–20 kHz**), where everyday speakers, mics, and hearing barely notice — so the mix **stays clean to the ear**, yet the picture is **crystal-clear** the moment someone views a spectrogram. Same spirit as hidden art in game soundtracks — here tuned so you control time, band, and strength.

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

---

## Screenshots

_Add a couple of images under `docs/` or inline here after your first release — spectrogram before/after sells the effect instantly._

---

## Download (Windows `.exe`)

Pre-built binaries are attached to [GitHub Releases](https://github.com/joenb33/spectraglyph/releases) when maintainers publish a versioned tag (`v*`, matching `pyproject.toml`). Preview builds may appear as **pre-releases** when changes are pushed to the `release` branch or when the Release workflow is started manually.

---

## Requirements

- **Windows** (primary target; Qt + audio stack tested there)
- **Python 3.10+**

---

## Quick start

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

---

## Build a standalone `.exe`

```powershell
pyinstaller pyinstaller.spec
```

Output: `dist\SpectraGlyph.exe`

---

## How viewers reveal the watermark

1. Open the exported file in **Audacity**, **Spek**, or **Sonic Visualiser**.
2. Switch to **spectrogram** view (e.g. Audacity: track spectrogram).
3. Typical settings that work well: **FFT size 4096**, **Hann** window, **~80 dB** dynamic range.
4. Scroll to the time range and frequency band you chose at export (use **View guide** in the app for a copy-paste cheat sheet).

---

## Localization

The desktop UI is currently **Swedish**; code comments and this README are **English** so the project is approachable for contributors worldwide.

## Project layout

- `main.py` — application entry
- `src/spectraglyph/` — GUI, DSP, audio I/O, watermark core
- `assets/` — icon & bundled resources for builds
- `tests/` — pytest coverage for mask/text and watermark embedding

---

## Repository

- **Product name:** **SpectraGlyph**
- **Upstream:** [github.com/joenb33/spectraglyph](https://github.com/joenb33/spectraglyph)
- **Security:** see [SECURITY.md](SECURITY.md)
- **Contributing & release process:** see [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT — see [LICENSE](LICENSE).
