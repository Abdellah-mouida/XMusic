"""Rendering helpers: display width, fitting, styled Line with click regions and overlay, ASCII fallback."""
from __future__ import annotations

from unicodedata import combining, east_asian_width

RESET = "\x1b[0m"

# Glyph substitutions for terminals/encodings that can't show box-drawing or block characters.
ASCII_MAP = str.maketrans({
    "─": "-", "│": "|", "╭": "+", "╮": "+", "╰": "+", "╯": "+", "├": "+", "┤": "+", "━": "=", "┃": "|",
    "█": "#", "▀": "^", "▄": "_", "▌": "|", "▏": "|", "●": "o", "▶": ">", "‖": "|", "↩": "<", "♪": "*",
    "▸": ">", "·": ".", "•": "*", "…": "~", "−": "-", "←": "<", "→": ">", "↑": "^", "↓": "v", "╲": "\\",
    "╱": "/", "╳": "X", "▁": ".", "▂": ".", "▃": ":", "▅": "=", "▆": "+", "▇": "*", "✓": "x",
    "▲": "^", "▼": "v", "⇄": "~", "↻": "@", "›": ">",
})


def ch_width(ch: str) -> int:
    if combining(ch):
        return 0
    return 2 if east_asian_width(ch) in "WF" else 1


def cw(s: str) -> int:
    if s.isascii():
        return len(s)
    return sum(ch_width(c) for c in s)


def fit(s: str, w: int) -> str:
    """Truncate to display width w, adding an ellipsis."""
    if w <= 0:
        return ""
    if cw(s) <= w:
        return s
    out, n = [], 0
    for ch in s:
        k = ch_width(ch)
        if n + k > w - 1:
            break
        out.append(ch)
        n += k
    return "".join(out) + "…"


def fmt_time(sec: float) -> str:
    sec = int(max(0, sec))
    if sec >= 3600:
        return "%d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)
    return "%02d:%02d" % (sec // 60, sec % 60)


class Line:
    """A row of styled text segments plus clickable regions [(x0, x1, kind, arg)]."""
    __slots__ = ("segs", "w", "hits")

    def __init__(self):
        self.segs: list = []
        self.w = 0
        self.hits: list = []

    def add(self, text, fg=None, bg=None, bold=False, hit=None):
        if not text:
            return self
        w = cw(text)
        if hit:
            self.hits.append((self.w, self.w + w, hit[0], hit[1]))
        self.segs.append((text, fg, bg, bold))
        self.w += w
        return self

    def fill(self, width, bg):
        if self.w < width:
            self.add(" " * (width - self.w), None, bg)
        return self

    def extend(self, o: "Line"):
        off = self.w
        self.hits.extend((a + off, b + off, k, g) for a, b, k, g in o.hits)
        self.segs.extend(o.segs)
        self.w += o.w
        return self

    def slice(self, a: int, b: int) -> "Line":
        """Columns [a, b) of this line (hit regions are dropped)."""
        out, col = Line(), 0
        for text, fg, bg, bold in self.segs:
            w = cw(text)
            s, e = col, col + w
            col = e
            if e <= a or s >= b:
                continue
            if s >= a and e <= b:
                out.segs.append((text, fg, bg, bold))
                out.w += w
                continue
            piece, pw, c = [], 0, s
            for ch in text:
                k = ch_width(ch)
                lo, hi = max(c, a), min(c + k, b)
                if hi > lo:
                    piece.append(ch if hi - lo == k else " " * (hi - lo))
                    pw += hi - lo
                c += k
            if piece:
                out.segs.append(("".join(piece), fg, bg, bold))
                out.w += pw
        return out

    def overlay(self, x: int, top: "Line") -> "Line":
        """This line with `top` painted over it starting at column x (used for dialogs)."""
        res = self.slice(0, x)
        res.fill(x, None)
        res.extend(top)
        rest = self.slice(x + top.w, self.w)
        res.segs.extend(rest.segs)
        res.w += rest.w
        return res

    def render(self, style) -> str:
        sgr = style.sgr
        return "".join(sgr(fg, bg, b) + t for t, fg, bg, b in self.segs) + RESET
