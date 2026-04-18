# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2026-04-18

### Added

- **Help → Check for updates…** queries the [latest GitHub Release](https://github.com/joenb33/spectraglyph/releases/latest), compares semver to the running app, and can open the release page or download the Windows `.exe` to your Downloads folder. The built app also checks automatically about **once per week** (after a short delay on startup) when a new check is due.
- `last_update_check_iso` in `settings.json` records the last successful GitHub check.

### Fixed

- **Background workers:** `Worker` signal objects are parented to the main window and cleaned up after delivery so **QueuedConnection** slots always run on the GUI thread without hanging or losing the signal when the thread pool deletes the runnable.

## [0.2.2] - 2026-04-18

### Added

- **Playhead + click-to-seek** on the spectrogram preview: a red vertical line shows the playback position while playing; click anywhere on the spectrogram to jump to that time (and to start playback if nothing is playing). Clicks inside the watermark region are ignored so drag/resize keeps working.

### Changed

- **Much faster preview when dragging the watermark region.** The preview now embeds the watermark only in a short window around the selected time range and splices that window's spectrogram columns into the cached original — instead of re-embedding across the entire file and recomputing the full spectrogram on every update. On long audio this removes the biggest source of lag.
- **Instant Play after the preview updates.** The watermarked samples produced by the preview are cached and reused by **Play**, so you no longer wait for a second watermark render the moment you press play. If you press Play before the preview has caught up, the old render path runs as a fallback.

## [0.2.1] - 2026-04-18

### Added

- **Play / Stop** button (also **Space**) in the top bar — audition the spectrogram you see, either the original audio or the watermarked mix, so you can confirm the watermark really is inaudible before exporting.
- **Chroma key masking:** new **Background / mask → Chroma key…** option with a color picker. Remove any color (not just white or black) from the source image. The active key is stored per preset.
- **File → Recent files:** the last eight audio files you opened are persisted in `settings.json` and available from a new **File** menu (with **Open audio…**, **Export…**, **Exit**, and **Clear list**).
- **Export — quick-action dialog:** after writing a file, offer **Open in Audacity** (auto-detects Windows install paths and `PATH`) and **Show in folder** (uses `explorer /select,…` on Windows, `open` / `xdg-open` elsewhere).

### Changed

- `Help → Keyboard shortcuts…` now lists the **Space** play/stop shortcut.
- Presets serialize the new `chroma_rgb` field; older presets still load unchanged.

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

[0.2.3]: https://github.com/joenb33/spectraglyph/releases/tag/v0.2.3
[0.2.2]: https://github.com/joenb33/spectraglyph/releases/tag/v0.2.2
[0.2.1]: https://github.com/joenb33/spectraglyph/releases/tag/v0.2.1
[0.2.0]: https://github.com/joenb33/spectraglyph/releases/tag/v0.2.0
[0.1.0]: https://github.com/joenb33/spectraglyph/releases/tag/v0.1.0
