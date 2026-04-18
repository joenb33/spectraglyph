# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-18

### Added

- **UI languages:** Swedish and English — **View → Language** (choice stored in settings). All user-visible strings live in `src/spectraglyph/gui/i18n.py`.
- **Keyboard shortcuts:** **Ctrl+O** (open audio), **Ctrl+I** (choose image), **Ctrl+E** (export); **Help → Keyboard shortcuts…** lists them. Tooltips on primary actions.
- **Portable user data:** When running the **built `.exe`**, presets and settings default to `SpectraGlyph_data\` next to the executable (with migration from legacy `%APPDATA%\SpectraGlyph` once). Fallback to AppData if the folder is not writable.
- **Session memory:** Last folders for open/save dialogs; window geometry and splitter sizes saved on exit (`settings.json`).
- **Large / long audio:** Fast metadata probe; if duration **> 2 minutes** or size **> 40 MB**, a dialog offers loading the **full file**, **only the first N seconds**, or a **custom time range**; partial decode reduces load time and RAM. Progress dialog during decode + spectrogram; segment shown in the audio info line when relevant.
- **CI:** GitHub Actions workflow runs **pytest** on pushes to `main` and pull requests.
- **Releases:** Workflow builds **SpectraGlyph.exe** with PyInstaller and attaches the versioned binary to GitHub Releases on `v*` tags or preview builds (see `CONTRIBUTING.md`).

### Changed

- Release artifacts ship as a **versioned `.exe`** on GitHub Releases (no zip wrapper by default).
- `README`, `CONTRIBUTING`, and `SECURITY` updated for the public repo and workflows.

### Fixed

- **CI / releases:** `extract_changelog.py` forces UTF-8 stdout so the Windows release job can write GitHub Release notes that contain Unicode (for example **→** in menu paths) without failing.

## [0.1.0] - 2026-04-18

### Added

- Initial public release: embed images or text as a near-inaudible spectral watermark in exported audio (WAV / FLAC / MP3).
- Swedish desktop UI (PySide6), live spectrogram preview, masking tools, presets, and export with viewer-oriented FFT hints.

[0.2.0]: https://github.com/joenb33/spectraglyph/releases/tag/v0.2.0
[0.1.0]: https://github.com/joenb33/spectraglyph/releases/tag/v0.1.0
