"""Extract the Keep a Changelog section for a given version (e.g. 0.1.0)."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def extract_section(changelog: str, version: str) -> str | None:
    # Match ## [0.1.0] - date or ## [0.1.0]
    header = re.compile(
        rf"^## \[{re.escape(version)}\](?:\s+-\s+[^\n]*)?\s*$",
        re.MULTILINE,
    )
    m = header.search(changelog)
    if not m:
        return None
    start = m.end()
    rest = changelog[start:]
    next_header = re.search(r"^## \[", rest, re.MULTILINE)
    block = rest[: next_header.start()] if next_header else rest
    lines = block.strip().splitlines()
    # Drop Keep a Changelog version link lines at section end, e.g. [0.1.0]: https://...
    while lines and re.match(r"^\[[^\]]+\]:\s*https?://", lines[-1].strip()):
        lines.pop()
    return "\n".join(lines).strip()


def _ensure_utf8_stdout() -> None:
    """Avoid UnicodeEncodeError on Windows (cp1252) when piping to Set-Content."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):
        pass


def main() -> None:
    _ensure_utf8_stdout()
    if len(sys.argv) < 2:
        print("Usage: extract_changelog.py <version> [CHANGELOG.md]", file=sys.stderr)
        sys.exit(2)
    version = sys.argv[1]
    path = Path(sys.argv[2] if len(sys.argv) > 2 else "CHANGELOG.md")
    text = path.read_text(encoding="utf-8")
    section = extract_section(text, version)
    if section:
        print(section)
    else:
        print(
            f"No changelog section found for [{version}]. See [CHANGELOG.md](CHANGELOG.md).",
        )


if __name__ == "__main__":
    main()
