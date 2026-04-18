"""GitHub Releases metadata for “check for updates” (public API, no token)."""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

# Must match the repo that publishes SpectraGlyph.exe on Releases.
GITHUB_LATEST_API = "https://api.github.com/repos/joenb33/spectraglyph/releases/latest"
USER_AGENT = "SpectraGlyph-update-check"


@dataclass(frozen=True)
class LatestRelease:
    """Latest published GitHub Release (stable tag, e.g. v0.2.3)."""

    version: str
    page_url: str
    asset_name: str | None
    download_url: str | None


def _parse_semver_tuple(s: str) -> tuple[int, ...]:
    """Loose semver: compare numeric segments only (suffixes like -beta are ignored)."""
    parts: list[int] = []
    for seg in s.strip().split("."):
        m = re.match(r"^(\d+)", seg)
        parts.append(int(m.group(1)) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def compare_versions(current: str, latest: str) -> int:
    """Return -1 if current < latest, 0 if equal, +1 if current > latest."""
    a, b = _parse_semver_tuple(current), _parse_semver_tuple(latest)
    n = max(len(a), len(b))
    aa = a + (0,) * (n - len(a))
    bb = b + (0,) * (n - len(b))
    if aa < bb:
        return -1
    if aa > bb:
        return 1
    return 0


def fetch_latest_release(timeout_s: float = 20.0) -> LatestRelease:
    """GET /releases/latest and pick the Windows x64 .exe asset if present."""
    req = urllib.request.Request(
        GITHUB_LATEST_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub HTTP {exc.code}") from exc
    except OSError as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc

    data = json.loads(raw)
    tag = str(data.get("tag_name") or "")
    version = tag.removeprefix("v").strip() or "0"
    page_url = str(data.get("html_url") or "").strip()

    asset_name: str | None = None
    download_url: str | None = None
    for asset in data.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if not url or not name.lower().endswith(".exe"):
            continue
        if "windows" in name.lower() and "x64" in name.lower():
            asset_name, download_url = name, url
            break
        if "spectraglyph" in name.lower() and asset_name is None:
            asset_name, download_url = name, url

    return LatestRelease(
        version=version,
        page_url=page_url,
        asset_name=asset_name,
        download_url=download_url,
    )


def download_release_asset(url: str, dest: str, *, timeout_s: float = 600.0) -> str:
    """Stream a release asset to disk (used from a background worker). Returns ``dest``."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
        block = 1024 * 1024
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(block)
                if not chunk:
                    break
                f.write(chunk)
    return dest
