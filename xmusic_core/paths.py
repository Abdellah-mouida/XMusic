"""Per-OS configuration / data locations (stdlib only).

Linux   config: $XDG_CONFIG_HOME/xmusic  (~/.config/xmusic)       data: $XDG_DATA_HOME/xmusic (~/.local/share/xmusic)
macOS   both:   ~/Library/Application Support/XMusic
Windows both:   %APPDATA%\\XMusic
Override everything with the XMUSIC_HOME environment variable (used by the tests).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _override() -> Path | None:
    v = os.environ.get("XMUSIC_HOME")
    return Path(v).expanduser() if v else None


def config_dir() -> Path:
    o = _override()
    if o:
        return o
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "XMusic"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "XMusic"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "xmusic"


def data_dir() -> Path:
    o = _override()
    if o:
        return o
    if sys.platform in ("win32", "darwin"):
        return config_dir()
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "xmusic"


def default_music_dir() -> Path:
    return Path.home() / "Music"


def short(p: str | Path) -> str:
    """Display a path with the home directory abbreviated to ~ (works for POSIX and Windows paths)."""
    s, home = str(p), str(Path.home())
    if s == home:
        return "~"
    for sep in {os.sep, "/"}:
        if s.startswith(home + sep):
            return "~" + s[len(home):]
    return s


def atomic_write(path: Path, text: str) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False
