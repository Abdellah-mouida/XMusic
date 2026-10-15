"""Central theme registry + terminal colour handling.  The UI only ever asks for *roles* ("accent", "playing"...).

Honours NO_COLOR (https://no-color.org) and degrades truecolor -> 256 -> 16 colours -> monochrome.
"""
from __future__ import annotations

import os
import sys

DEFAULT_THEME = "blue"


def _make(tid: str, name: str, desc: str, **b: str) -> dict:
    t = dict(b)
    t.setdefault("brand_a", b["accent"])      # logo gradient start
    t.setdefault("brand_b", b["hl"])          # logo gradient end
    t.setdefault("playing", b["hl"])          # currently playing track
    t.setdefault("sel_bar", b["accent"])      # selected-row marker
    t.setdefault("prog_fill", b["accent"])    # progress: completed
    t.setdefault("prog_knob", b["bright"])
    t.setdefault("vol", b["accent"])          # volume indicator
    t.setdefault("st_play", b["hl"])          # playback state colours
    t.setdefault("st_pause", b["text2"])
    t.setdefault("st_idle", b["accent"])
    t.setdefault("search", b["bright"])       # search highlight
    t.setdefault("anim_a", b["accent"])       # equalizer / animation gradient
    t.setdefault("anim_b", b["hl"])
    t["id"], t["name"], t["desc"] = tid, name, desc
    return t


THEMES: dict[str, dict] = {t["id"]: t for t in (
    _make("blue", "Blue", "Deep navy, electric blue, cyan",
          bg="080B12", panel="111827", border="1E3A5F", accent="3D8BFF", bright="60A5FA", hl="38BDF8",
          text="E5EAF3", text2="8B95A7", muted="596579", rem="2B3A55", ok="5CC79A", warn="E0B15C", err="C46B6B"),
    _make("girly", "Girly / Rose", "Plum surfaces, rose and blush pink",
          bg="1A1220", panel="2A1B33", border="5A2D4E", accent="FF78B7", bright="FFB6D5", hl="F9A8D4",
          text="FFF1F5", text2="C9A5B8", muted="7E6074", rem="4A3040", ok="8FD6A8", warn="F2C078", err="E0788C"),
    _make("yaru", "Yaru Orange", "Charcoal with burnt orange and amber",
          bg="1A1A1A", panel="2A2725", border="5A3626", accent="E95420", bright="FF8C42", hl="FFB86B",
          text="F2F0EE", text2="A8A39E", muted="6B6661", rem="3D3835", ok="8FBF6A", warn="FFB86B", err="E0605A"),
    _make("amoled-blue", "AMOLED Blue", "Pure black with electric blue",
          bg="000000", panel="0A0F1A", border="16294A", accent="3D8BFF", bright="60A5FA", hl="38BDF8",
          text="F0F4FA", text2="8B95A7", muted="4B5668", rem="1A2438", ok="5CC79A", warn="E0B15C", err="D06A6A"),
    _make("amoled-pink", "AMOLED Pink", "Pure black with neon pink",
          bg="000000", panel="150A12", border="4A1535", accent="FF2E93", bright="FF8AC4", hl="FF5CAA",
          text="F7F2F5", text2="A58C99", muted="5E4A55", rem="2A1420", ok="7FD6A0", warn="F0C070", err="E8607A"),
    _make("violet", "Violet", "Deep purple, vivid violet, lavender",
          bg="120B24", panel="1D1236", border="3B2A6B", accent="8B5CF6", bright="A78BFA", hl="C4B5FD",
          text="EFEAFB", text2="A99BC9", muted="6D5F8F", rem="33285A", ok="86D6A8", warn="E8C37A", err="D9708A"),
)}
ALIASES = {"rose": "girly", "pink": "girly", "orange": "yaru", "ubuntu": "yaru", "amoled": "amoled-blue",
           "purple": "violet", "default": "blue"}
ROLES = tuple(k for k in THEMES["blue"] if k not in ("id", "name", "desc"))


def resolve(tid) -> str | None:
    """Normalise a user supplied theme id; None if unknown."""
    if not isinstance(tid, str):
        return None
    t = tid.strip().lower().replace("_", "-").replace(" ", "-")
    t = ALIASES.get(t, t)
    return t if t in THEMES else None


def get(tid) -> dict:
    return THEMES[resolve(tid) or DEFAULT_THEME]


def theme_ids() -> list[str]:
    return list(THEMES)


# ------------------------------------------------------------------ colour output
def detect_depth() -> int:
    """24 = truecolor, 8 = 256 colours, 4 = 16 colours, 0 = no colour."""
    env = os.environ
    if env.get("NO_COLOR") or env.get("TERM") == "dumb":
        return 0
    if env.get("COLORTERM", "").lower() in ("truecolor", "24bit") or "direct" in env.get("TERM", ""):
        return 24
    if env.get("WT_SESSION") or env.get("VTE_VERSION") or env.get("KITTY_WINDOW_ID") or env.get("WEZTERM_EXECUTABLE"):
        return 24
    if env.get("TERM_PROGRAM") == "Apple_Terminal":      # Terminal.app: 256 colours, no truecolor
        return 8
    if sys.platform == "win32":
        return 24                                        # Windows 10+ VT consoles support 24-bit
    if "256" in env.get("TERM", ""):
        return 8
    return 4


def _rgb(h: str):
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


_ANSI16 = [(0, 0, 0), (170, 0, 0), (0, 170, 0), (170, 85, 0), (0, 0, 170), (170, 0, 170), (0, 170, 170),
           (170, 170, 170), (85, 85, 85), (255, 85, 85), (85, 255, 85), (255, 255, 85), (85, 85, 255),
           (255, 85, 255), (85, 255, 255), (255, 255, 255)]


def _to256(r, g, b):
    if abs(r - g) < 10 and abs(g - b) < 10:
        return 16 if r < 8 else 231 if r > 248 else 232 + round((r - 8) / 247 * 24)
    q = lambda v: 0 if v < 48 else 1 if v < 115 else (v - 35) // 40
    return 16 + 36 * q(r) + 6 * q(g) + q(b)


def _to16(r, g, b):
    return min(range(16), key=lambda i: (r - _ANSI16[i][0]) ** 2 + (g - _ANSI16[i][1]) ** 2 + (b - _ANSI16[i][2]) ** 2)


class Style:
    """Turns (fg, bg, bold) hex triples into SGR escapes for the detected colour depth."""

    def __init__(self, depth: int | None = None):
        self.depth = detect_depth() if depth is None else depth
        self._cache: dict = {}

    @staticmethod
    def lerp(a: str, b: str, t: float) -> str:
        ra, ga, ba = _rgb(a)
        rb, gb, bb = _rgb(b)
        t = 0.0 if t < 0 else 1.0 if t > 1 else t
        return "%02X%02X%02X" % (round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t))

    def _code(self, hexc, bg):
        r, g, b = _rgb(hexc)
        if self.depth >= 24:
            return "%d;2;%d;%d;%d" % (48 if bg else 38, r, g, b)
        if self.depth >= 8:
            return "%d;5;%d" % (48 if bg else 38, _to256(r, g, b))
        i = _to16(r, g, b)
        return str((40 if bg else 30) + i if i < 8 else (100 if bg else 90) + i - 8)

    def sgr(self, fg=None, bg=None, bold=False) -> str:
        key = (fg, bg, bold)
        s = self._cache.get(key)
        if s is None:
            if self.depth == 0:                           # NO_COLOR: attributes only
                s = "\x1b[0;1m" if bold else "\x1b[0m"
            else:
                parts = ["0"] + (["1"] if bold else [])
                if fg:
                    parts.append(self._code(fg, False))
                if bg:
                    parts.append(self._code(bg, True))
                s = "\x1b[" + ";".join(parts) + "m"
            if len(self._cache) < 4096:
                self._cache[key] = s
        return s
