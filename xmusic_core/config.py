"""Settings (config.json) with validation + graceful recovery, plus small state (recent/queue)."""
from __future__ import annotations

import json
from pathlib import Path

from . import paths, themes

DEFAULTS = {"version": 2, "theme": "blue", "volume": 70, "muted": False, "music_dir": None,
            "shuffle": False, "repeat": "off", "animation": True}
REPEAT_MODES = ("off", "all", "one")


def validate(raw) -> dict:
    """Coerce arbitrary loaded JSON into a valid settings dict (unknown/invalid values -> defaults)."""
    cfg = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return cfg
    t = themes.resolve(raw.get("theme"))
    cfg["theme"] = t or DEFAULTS["theme"]
    v = raw.get("volume")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        cfg["volume"] = max(0, min(100, int(v)))
    for k in ("muted", "shuffle", "animation"):
        if isinstance(raw.get(k), bool):
            cfg[k] = raw[k]
    if raw.get("repeat") in REPEAT_MODES:
        cfg["repeat"] = raw["repeat"]
    if isinstance(raw.get("music_dir"), str) and raw["music_dir"]:
        cfg["music_dir"] = raw["music_dir"]
    return cfg


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, e


class Settings:
    def __init__(self, directory: Path | None = None):
        self.path = (directory or paths.config_dir()) / "config.json"
        self.values = dict(DEFAULTS)
        self.warning: str | None = None
        self.legacy: dict = {}          # playlists/recent from XMusic 1.x config, migrated by the caller

    def load(self) -> "Settings":
        raw, err = _read_json(self.path)
        if err is not None:             # malformed: keep a copy, start from defaults
            try:
                self.path.replace(self.path.with_name("config.json.bad"))
            except OSError:
                pass
            self.warning = "config.json was unreadable; defaults loaded (copy kept as config.json.bad)"
        if isinstance(raw, dict):
            self.legacy = {k: raw[k] for k in ("playlists", "recent") if k in raw}
        self.values = validate(raw)
        return self

    def save(self) -> bool:
        return paths.atomic_write(self.path, json.dumps(self.values, indent=2) + "\n")

    def __getitem__(self, k):
        return self.values[k]

    def __setitem__(self, k, v):
        self.values[k] = v


class State:
    """recent tracks + persisted queue (data dir, state.json)."""

    def __init__(self, directory: Path | None = None):
        self.path = (directory or paths.data_dir()) / "state.json"
        self.recent: list[str] = []
        self.queue: list[str] = []
        self.current: str | None = None

    def load(self):
        raw, _ = _read_json(self.path)
        if isinstance(raw, dict):
            def strs(k):
                v = raw.get(k)
                return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []
            self.recent, self.queue = strs("recent")[:50], strs("queue")[:2000]
            self.current = raw.get("current") if isinstance(raw.get("current"), str) else None
        return self

    def save(self):
        data = {"version": 1, "recent": self.recent[:50], "queue": self.queue[:2000], "current": self.current}
        return paths.atomic_write(self.path, json.dumps(data) + "\n")
