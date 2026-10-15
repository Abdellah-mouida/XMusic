"""Local playlists: one human-readable JSON file {"version":1,"playlists":{"Name":["/abs/path.mp3",...]}}.

Only file paths are stored (no metadata copies), so playlists stay tiny even for huge libraries.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paths

FAVORITES = "Favorites"
MAX_NAME = 40


class Playlists:
    def __init__(self, directory: Path | None = None):
        self.path = (directory or paths.data_dir()) / "playlists.json"
        self.data: dict[str, list[str]] = {FAVORITES: []}

    def load(self) -> "Playlists":
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            pl = raw.get("playlists") if isinstance(raw, dict) else None
            if isinstance(pl, dict):
                self.data = {str(k): [p for p in v if isinstance(p, str)] for k, v in pl.items() if isinstance(v, list)}
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            try:
                self.path.replace(self.path.with_name("playlists.json.bad"))
            except OSError:
                pass
        self.data.setdefault(FAVORITES, [])
        return self

    def import_legacy(self, legacy) -> bool:
        """Adopt playlists stored inside an XMusic 1.x config.json (only if no playlists file exists yet)."""
        if self.path.exists() or not isinstance(legacy, dict):
            return False
        for k, v in legacy.items():
            if isinstance(k, str) and isinstance(v, list):
                self.data[k] = [p for p in v if isinstance(p, str)]
        self.data.setdefault(FAVORITES, [])
        return self.save()

    def save(self) -> bool:
        return paths.atomic_write(self.path, json.dumps({"version": 1, "playlists": self.data}, indent=1) + "\n")

    # -------------------------------------------------------------- queries
    def names(self) -> list[str]:
        return sorted(self.data, key=lambda n: (n != FAVORITES, n.lower()))

    def get(self, name: str) -> list[str]:
        return self.data.get(name, [])

    def contains(self, name: str, path: str) -> bool:
        return path in self.data.get(name, [])

    def _clean(self, name: str) -> str:
        return " ".join(name.split())[:MAX_NAME]

    def valid_name(self, name: str, ignore: str | None = None) -> str | None:
        """Return an error message, or None if the name is usable."""
        n = self._clean(name)
        if not n:
            return "Name can't be empty"
        for other in self.data:
            if other.lower() == n.lower() and other != ignore:
                return "A playlist with that name already exists"
        return None

    # ------------------------------------------------------------- mutation
    def create(self, name: str) -> str | None:
        if self.valid_name(name):
            return None
        n = self._clean(name)
        self.data[n] = []
        self.save()
        return n

    def rename(self, old: str, new: str) -> str | None:
        if old not in self.data or old == FAVORITES or self.valid_name(new, ignore=old):
            return None
        n = self._clean(new)
        self.data = {(n if k == old else k): v for k, v in self.data.items()}
        self.save()
        return n

    def delete(self, name: str) -> bool:
        if name == FAVORITES or name not in self.data:
            return False
        del self.data[name]
        return self.save()

    def add(self, name: str, path: str) -> bool:
        lst = self.data.get(name)
        if lst is None or path in lst:
            return False
        lst.append(path)
        self.save()
        return True

    def remove(self, name: str, path: str) -> bool:
        lst = self.data.get(name)
        if lst is None or path not in lst:
            return False
        lst.remove(path)
        self.save()
        return True

    def toggle(self, name: str, path: str) -> bool:
        """Add if absent / remove if present. Returns True if the path is now in the playlist."""
        if self.contains(name, path):
            self.remove(name, path)
            return False
        self.add(name, path)
        return True
