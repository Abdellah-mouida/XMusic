"""Original XMusic wordmark: one 5-row pixel font, rendered at three sizes.

big   5 text rows, 2 chars per pixel  (62 columns)   - terminals >= 30 rows
mid   3 text rows, half-block pixels  (31 columns)   - terminals >= 21 rows
small handled by the renderer as a compact one-line wordmark
"""
from __future__ import annotations

_FONT = {
    "X": ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    "u": ["#...#", "#...#", "#...#", "#...#", ".###."],
    "s": [".####", "#....", ".###.", "....#", "####."],
    "i": ["#", ".", "#", "#", "#"],
    "c": [".####", "#....", "#....", "#....", ".####"],
}
WORD = "XMusic"


def bitmap() -> list[str]:
    rows = [""] * 5
    for n, ch in enumerate(WORD):
        g = _FONT[ch]
        for r in range(5):
            rows[r] += g[r] + ("." if n < len(WORD) - 1 else "")
    return rows


BITS = bitmap()
PIXEL_W = len(BITS[0])


def rows(tier: str) -> list[list[str]]:
    """Per text-row list of per-pixel-column strings (so callers can colour each column)."""
    if tier == "big":
        return [["██" if c == "#" else "  " for c in r] for r in BITS]
    padded = BITS + ["." * PIXEL_W]                      # 6 pixel rows -> 3 half-block text rows
    out = []
    for r in range(0, 6, 2):
        line = []
        for x in range(PIXEL_W):
            t, b = padded[r][x] == "#", padded[r + 1][x] == "#"
            line.append("█" if t and b else "▀" if t else "▄" if b else " ")
        out.append(line)
    return out


def width(tier: str) -> int:
    return PIXEL_W * (2 if tier == "big" else 1)


def height(tier: str) -> int:
    return 5 if tier == "big" else 3
