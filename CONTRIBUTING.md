# Contributing

Thanks for your interest in SpectraGlyph.

- **Code and comments** are primarily in **English**; the desktop UI is **Swedish** or **English** (see `src/spectraglyph/gui/i18n.py`).
- **Run tests** before submitting changes: `pytest -q` (see `README.md`).
- **Pull requests** should stay focused; match existing style and avoid unrelated refactors.

## Publishing a stable release (maintainers)

1. Update **`CHANGELOG.md`** and bump **`[project].version`** in **`pyproject.toml`** (and keep `src/spectraglyph/__init__.py` `__version__` in sync if you change the version).
2. Commit on `main`, then create and push a **semver tag** that matches the package version, e.g. `v0.2.0` when `pyproject.toml` says `0.2.0`:
   ```powershell
   git tag v0.2.0
   git push origin v0.2.0
   ```
3. The [Release workflow](.github/workflows/release.yml) builds `SpectraGlyph.exe`, attaches it to a **GitHub Release**, and fills notes from `CHANGELOG.md` for the tagged version.

## Preview builds

- Push to the **`release`** branch, or run the **Release** workflow manually from the Actions tab. This creates a **pre-release** with a `preview-*` tag (not a replacement for a versioned release).

Pushes to **`main` alone** do not upload an `.exe`; use tags or the preview paths above.
