"""All drawing code (mixin for App). Reads colours exclusively from the active theme via self.c(role)."""
from __future__ import annotations

import math
import os
import time

from . import logo
from .paths import short
from .themes import THEMES, Style
from .ui import ASCII_MAP, Line, cw, fit, fmt_time

NAV = ("All Tracks", "Folders", "Queue", "Playlists", "Recently Played")
NAV_SHORT = ("All", "Folders", "Queue", "Lists", "Recent")
SORTS = ("path", "title", "artist", "album", "length")
EQ = " ▁▂▃▄▅▆▇█"
INTRO, HL = 0.85, 0.7
REPEAT_LABEL = {"off": "OFF", "all": "ALL", "one": "ONE"}

AUTHOR_LINE = "Made by Abdellah Mouida"
MATRIX_GLYPHS = "01#$%+*/<>[]{}"
MATRIX_COLORS = ("E3F2FF", "80C4FF", "367BF5", "153D82")


def matrix_glyph(x: int, y: int, frame: int, height: int = 17):
    """Deterministic single-cell Matrix rain sample: (glyph, brightness index) or None."""
    seed = (x * 1103515245 + 12345) & 0x7FFFFFFF
    if seed % 3 == 0:
        return None
    speed = 1 + (seed % 2)
    trail = 3 + (seed // 11) % 5
    period = height + trail + 9 + (seed // 29) % 13
    head = (frame // speed + (seed // 127) % period) % period
    distance = head - y
    if not 0 <= distance < trail:
        return None
    index = (frame // (1 + seed % 3) + x * 7 + y * 11 + seed) % len(MATRIX_GLYPHS)
    return MATRIX_GLYPHS[index], min(3, distance)

HELP = (
    ("PLAYBACK", None),
    ("Space", "Play / pause"), ("Enter", "Play / open"), ("x", "Stop"), ("n  p", "Next / previous"),
    ("← →", "Seek -/+ 5 s"), ("+  -", "Volume up / down"), ("m", "Mute / unmute"),
    ("s", "Shuffle on / off"), ("r", "Repeat off>all>one"),
    ("BROWSE", None),
    ("↑↓ PgUp PgDn", "Navigate"), ("1-5", "Switch library view"), ("l  f", "Library / folders"),
    ("/", "Search"), ("o", "Cycle sort order"), ("Tab", "Switch panel focus"), ("F5", "Rescan music folder"),
    ("QUEUE", None),
    ("e", "Add to queue"), ("E", "Play next"), ("d / Del", "Remove item"),
    ("K  J", "Move item up / down"), ("c", "Clear queue"),
    ("PLAYLISTS", None),
    ("a", "Toggle Favorites"), ("A", "Add to playlist"), ("N  R  D", "New / rename / delete"),
    ("APP", None),
    ("t", "Theme picker"), ("z", "Toggle animations"), ("?", "This help"),
    ("Esc", "Close / clear search"), ("q  Ctrl+C", "Quit"), ("Mouse", "Click, wheel, drag bars"),
)


def hl_spans(text: str, words: list[str]):
    """Split text into [(chunk, matched)] for search highlighting."""
    low = text.lower()
    if not words or len(low) != len(text):
        return [(text, False)]
    mark = [False] * len(text)
    for w in words:
        i = low.find(w)
        if i >= 0:
            for k in range(i, i + len(w)):
                mark[k] = True
    out, cur, flag = [], "", mark[0] if mark else False
    for ch, m in zip(text, mark):
        if m != flag:
            out.append((cur, flag))
            cur, flag = "", m
        cur += ch
    out.append((cur, flag))
    return out


class Renderer:
    # ------------------------------------------------------------------ colours
    def c(self, role: str) -> str:
        h = self.theme[role]
        return h if self.fade >= 1.0 else Style.lerp(self.theme["bg"], h, self.fade)

    # ------------------------------------------------------------------ entry
    def render(self):
        W, H = self.term.size
        self.hits = []
        if W <= 0 or H <= 0:
            return
        if self.help and W >= 30 and H >= 9:
            rows, self.mode = self.frame_help(W, H), "help"
        elif self.kali_mode:
            rows, self.mode = self.frame_kali(W, H), "kali"
        elif W < 30 or H < 9:
            rows = self.frame_compact(W, H)
            self.mode = "compact"
        elif W >= 76 and H >= 18:
            rows, self.mode = self.frame_full(W, H), "full"
        else:
            rows, self.mode = self.frame_compact(W, H), "compact"
        bg = self.c("bg")
        while len(rows) < H:
            rows.append(Line().fill(W, bg))
        rows = rows[:H]
        if self.modal and self.mode != "tiny":
            self.draw_modal(rows, W, H)          # overlay; also replaces hit regions
        else:
            for y, r in enumerate(rows):
                for a, b, k, g in r.hits:
                    self.hits.append((y, a, b, k, g))
                    if k == "bar":
                        self.bar_geo = (a, y, b - a)
                    elif k == "vol":
                        self.vol_geo = (a, y, b - a)
        strs = [r.render(self.style) for r in rows]
        if self.ascii:
            strs = [s.translate(ASCII_MAP) for s in strs]
        prev, out = self._prev, []
        if prev is None or len(prev) != len(strs):
            out.append("\x1b[2J")
            prev = None
        for y, s in enumerate(strs):
            if prev is None or prev[y] != s:
                out.append("\x1b[%d;1H%s" % (y + 1, s))
        if out:
            self.term.write("".join(out))
        self._prev = strs

    # ---------------------------------------------------------------- brand
    def logo_lines(self, tier: str, bg: str) -> list[Line]:
        cols = logo.rows(tier)
        pw = len(cols[0])
        edge = None
        if self.intro:
            edge = (time.monotonic() - self.t0) / INTRO * (pw + 8)
        out = []
        for row in cols:
            L = Line().add("  ", None, bg)
            for x, chunk in enumerate(row):
                if not chunk.strip():
                    L.add(chunk, None, bg)
                    continue
                col = Style.lerp(self.c("brand_a"), self.c("brand_b"), x / max(1, pw - 1))
                if edge is not None:
                    p = (edge - x) / 8
                    if p <= 0:
                        L.add(" " * len(chunk), None, bg)
                        continue
                    col = Style.lerp(self.c("muted"), col, p)
                L.add(chunk, col, bg, True)
            out.append(L)
        return out

    def wordmark(self, L, bg, mark="╳ "):
        t = time.monotonic() - self.t0
        L.add(mark, self.c("brand_b"), bg, True)
        label = "XMUSIC"
        for i, ch in enumerate(label):
            col = Style.lerp(self.c("brand_a"), self.c("brand_b"), i / max(1, len(label) - 1))
            if self.intro:
                p = t * 9 - i * 0.9
                if p <= 0:
                    L.add(" ", None, bg)
                    continue
                col = Style.lerp(self.c("muted"), col, p)
            L.add(ch, col, bg, True)

    def author_line(self, bg, start=2, width=None) -> Line:
        """Small attribution aligned beneath the XMusic block logo."""
        width = width or max(map(len, logo.XMUSIC_ART))
        left = start + max(0, (width - cw(AUTHOR_LINE)) // 2)
        return Line().add(" " * left, None, bg).add(AUTHOR_LINE, self.c("muted"), bg)

    def status(self):
        e = self.engine
        if self.audio_err:
            return "NO AUDIO DEVICE", self.c("err"), self.c("err")
        if e.playing:
            pulse = self.animate and int(time.monotonic() * 2) % 2
            return "STREAMING", self.c("st_play"), (self.c("bright") if pulse else self.c("accent"))
        if e.active and e.paused:
            return "PAUSED", self.c("st_pause"), self.c("st_pause")
        return "NODE READY", self.c("st_idle"), self.c("st_idle")

    def status_chunk(self, bg) -> Line:
        st, stc, dot = self.status()
        L = Line().add("● ", dot, bg).add(st, stc, bg, True)
        L.add("  ·  ", self.c("muted"), bg)
        L.add(self.theme["name"], self.c("accent"), bg, True, hit=("key", "t"))
        return L

    def eq(self, n):
        e = self.engine
        t = e.position() if e.active else 0.0
        out = []
        for i in range(n):
            if e.active and self.animate:
                v = (math.sin(t * (6.1 + i * 1.7) + i * 1.9) + 0.6 * math.sin(t * (11.3 + i * 0.9) + i)) / 1.6 * 0.5 + 0.5
                lvl = 1 + int(v * 7.99)
            else:
                lvl = 2 if not e.active else 3
            col = Style.lerp(self.c("anim_a"), self.c("anim_b"), i / max(1, n - 1)) if e.playing else self.c("muted")
            out.append((EQ[lvl], col))
        return out

    def header(self, label, w, bg, focus=False):
        L = Line().add("› ", self.c("hl"), bg, True)
        L.add(label, self.c("bright") if focus else self.c("accent"), bg, True)
        L.add(" " + "─" * max(0, w - L.w - 1), self.c("border"), bg)
        return L

    # ---------------------------------------------------------------- controls
    def bar(self, L, w, frac, bg, kind, fill_role="prog_fill", knob_role="prog_knob", muted=False):
        n = int(round(max(0.0, min(1.0, frac)) * (w - 1)))
        s = L.w
        rem_ch = "─" if self.style.depth == 0 else "━"
        fill = self.c("muted") if muted else self.c(fill_role)
        L.add("━" * n, fill, bg).add("●", self.c("muted") if muted else self.c(knob_role), bg)
        L.add(rem_ch * (w - 1 - n), self.c("rem"), bg)
        L.hits.append((s, s + w, kind, 0))

    def progress_values(self):
        e, t = self.engine, self.cur
        pos = e.position() if (t and e.active) else 0.0
        dur = t.duration if t else 0.0
        if self.drag == "bar" and self.drag_frac is not None and dur:
            pos = self.drag_frac * dur
        if dur:
            pos = min(pos, dur)
        return pos, dur, (pos / dur if dur else 0.0)

    def flashing(self, kind, arg):
        return self.flash.get((kind, arg), 0) > time.monotonic()

    def btn(self, L, label, hit, bg, active=False):
        on = self.flashing(*hit)
        if on:
            fg, b = bg, self.c("bright")
        elif active:
            fg, b = bg, self.c("accent")
        else:
            fg, b = self.c("text"), self.c("panel")
        L.add(" " + label + " ", fg, b, on or active, hit=hit)

    def mode_buttons(self, L, bg, short=False):
        q = self.q
        self.btn(L, "Shuf" if short else "Shuffle " + ("ON" if q.shuffle else "OFF"), ("key", "s"), bg, q.shuffle)
        L.add(" ", None, bg)
        lab = {"off": "Rep", "all": "Rep*", "one": "Rep1"}[q.repeat] if short else "Repeat " + REPEAT_LABEL[q.repeat]
        self.btn(L, lab, ("key", "r"), bg, q.repeat != "off")

    def vol_line(self, w, bg, label=True):
        e, v = self.engine, self.engine.volume
        L = Line()
        if label:
            L.add("VOL ", self.c("warn") if e.muted else self.c("text2"), bg, e.muted, hit=("mute", 0))
        for sym, kind in (("−", "volm"),):
            on = self.flashing(kind, 0)
            L.add("[" + sym + "]", self.c("bright") if on else self.c("text2"), bg, on, hit=(kind, 0))
        L.add(" ", None, bg)
        self.bar(L, max(6, min(14, w - 19)), v / 100.0, bg, "vol", "vol", "prog_knob", muted=e.muted)
        L.add(" ", None, bg)
        on = self.flashing("volp", 0)
        L.add("[+]", self.c("bright") if on else self.c("text2"), bg, on, hit=("volp", 0))
        if e.muted:
            L.add(" MUTE", self.c("warn"), bg, True, hit=("mute", 0))
        else:
            L.add(" %3d%%" % v, self.c("text"), bg, hit=("mute", 0))
        return L

    def now_lines(self, w, bg, rows_n):
        e, t = self.engine, self.cur
        rows = [(self.header("SIGNAL MONITOR", w, bg), False)]
        L = Line()
        for ch, col in self.eq(6):
            L.add(ch, col, bg)
        L.add("  " + ("STREAM LIVE" if e.playing else "PAUSED" if (e.active and e.paused) else "IDLE"),
              self.c("st_play") if e.playing else self.c("st_pause"), bg, True)
        rows.append((L, False))
        if t:
            rows.append((Line().add(fit(t.title, w), self.c("text"), bg, True), False))
            rows.append((Line().add(fit(t.artist or "Unknown artist", w), self.c("text2"), bg), False))
            alb = (t.album + " · " if t.album else "") + os.path.basename(t.path)
            rows.append((Line().add(fit(alb, w), self.c("muted"), bg), False))
        else:
            rows.append((Line().add("Nothing playing", self.c("text2"), bg), False))
            rows.append((Line().add("Press Enter on a track", self.c("muted"), bg), False))
            rows.append((Line(), False))
        rows.append((Line(), True))
        pos, dur, fr = self.progress_values()
        L = Line()
        self.bar(L, w, fr, bg, "bar")
        rows.append((L, False))
        rows.append((Line().add(fmt_time(pos), self.c("text"), bg).add(" / " + (fmt_time(dur) if dur else "--:--"), self.c("text2"), bg), False))
        rows.append((Line(), True))
        rows.append((self.vol_line(w, bg), False))
        rows.append((Line(), True))
        L = Line()
        self.btn(L, "Prev", ("btn", "prev"), bg)
        L.add(" ", None, bg)
        self.btn(L, "Pause" if e.playing else "Play", ("btn", "play"), bg)
        L.add(" ", None, bg)
        self.btn(L, "Next", ("btn", "next"), bg)
        if w >= 36:
            L.add(" ", None, bg)
            self.btn(L, "Stop", ("btn", "stop"), bg)
        rows.append((L, False))
        L = Line()
        self.mode_buttons(L, bg)
        rows.append((L, False))
        while len(rows) > rows_n and any(sp for _, sp in rows):     # drop spacer rows when space is tight
            for i in range(len(rows) - 1, -1, -1):
                if rows[i][1]:
                    del rows[i]
                    break
        return [r for r, _ in rows][:rows_n]

    def nav_items(self, w, bg):
        res = []
        for i, name in enumerate(NAV):
            active = i == self.nav and not self.query
            fl = self.flashing("nav", i)
            if active and self.focus == "nav":
                fg, b, bold = self.c("bright"), self.c("panel"), True
            elif active:
                fg, b, bold = self.c("accent"), bg, True
            else:
                fg, b, bold = self.c("text2"), bg, False
            if fl:
                fg, b = bg, self.c("bright")
            label = (" > " if active else "   ") + name
            if i == 2 and len(self.q):
                label += "  (%d)" % len(self.q)
            res.append(Line().add(fit(label, w).ljust(w), fg, b, bold, hit=("nav", i)))
        return res

    def row_label(self, kind, val):
        if kind == "dir":
            return "▸ " + os.path.basename(val) + "/"
        if kind in ("up", "plup"):
            return "↩ .."
        if kind == "pl":
            return "♪ %s (%d)" % (val, len(self.playlists.get(val)))
        if kind == "plnew":
            return "+ New playlist…"
        if kind == "plplay":
            return "▶ Play playlist"
        if kind == "missing":
            return "! %s (missing)" % os.path.basename(val)
        return str(val)

    def list_lines(self, w, rows_n, bg):
        """Header line + item rows; updates paging state."""
        e = self.engine
        items = self.items()
        n = len(items)
        cnt = "%d" % n
        if self.searching or self.query:
            h = Line().add("/ ", self.c("search"), bg, True).add(fit(self.query, w - 12), self.c("text"), bg)
            if self.searching:
                h.add("▏", self.c("hl"), bg)
            h.add(" " * max(1, w - h.w - len(cnt) - 6), None, bg).add("%s found" % cnt, self.c("muted"), bg)
        else:
            h = self.header(fit(self.view_title, w - len(cnt) - 3), w - len(cnt) - 1, bg, self.focus == "list")
            h.add(" " + cnt, self.c("muted"), bg)
        out = [h]
        R = max(1, rows_n - 1)
        self.list_rows = R
        self.top = max(0, min(self.top, max(0, n - R)))
        if n == 0:
            for m in self.empty_msgs()[:R]:
                out.append(Line().add(fit(m, w), self.c("text2") if m else self.c("muted"), bg))
            return out
        hl = max(0.0, (self.hl_until - time.monotonic()) / HL) if self.animate else 0.0
        thumb = round(self.top / (n - R) * (R - 1)) if n > R else -1
        words = self.query.lower().split() if self.query else []
        qpos = self.q.pos() if self.nav == 2 and not self.query else -1
        for off in range(R):
            idx = self.top + off
            if idx >= n:
                out.append(Line())
                continue
            kind, val = items[idx]
            selected = idx == self.sel
            track = val if kind == "track" else val.track if kind == "q" else None
            if kind == "q":
                playing = val is self.q.cur and e.active
            else:
                playing = track is not None and track is self.cur and e.active
            rb = self.c("panel") if selected else bg
            if playing and hl > 0:
                rb = Style.lerp(rb, self.c("accent"), 0.45 * hl)
            L = Line()
            L.add("▌" if selected else " ", self.c("sel_bar") if self.focus == "list" else self.c("muted"), rb)
            if playing:
                mk = "▁▃▅▇▅▃"[int(time.monotonic() * 8) % 6] if (e.playing and self.animate) else ("▶" if e.playing else "‖")
                L.add(mk + " ", self.c("playing"), rb, True)
            else:
                L.add("  ", None, rb)
            tw = w - 3 - 1 - 5 - 1
            if track is not None:
                past = kind == "q" and qpos >= 0 and idx < qpos
                fg = self.c("playing") if playing else self.c("text") if selected else self.c("muted") if past else self.c("text2")
                if track.bad:
                    fg = self.c("err")
                tl = fit(track.title, tw)
                for chunk, m in hl_spans(tl, words):
                    L.add(chunk, self.c("search") if m else fg, rb, playing or selected or m)
                if track.artist and cw(tl) + 4 < tw:
                    L.add(fit("  " + track.artist, tw - cw(tl)), self.c("muted"), rb)
                L.fill(3 + tw, rb)
                L.add(" " + (fmt_time(track.duration) if track.duration else "     "), self.c("muted"), rb)
            else:
                fg = self.c("err") if kind == "missing" else self.c("bright") if selected else self.c("text2")
                L.add(fit(self.row_label(kind, val), tw), fg, rb, selected)
                L.fill(3 + tw + 6, rb)
            L.add("┃" if off == thumb else ("│" if thumb >= 0 else " "), self.c("accent") if off == thumb else self.c("border"), bg)
            L.hits.append((0, L.w, "row", off))
            out.append(L)
        return out

    def empty_msgs(self):
        if self.query:
            return ["No matches.", "", "Esc to clear the search"]
        if self.nav in (0, 1):
            return ["No MP3 files found in", short(self.root), "", "Add .mp3 files, then press F5", "or run: xmusic --music-dir PATH"] + self.scan_errors[:1]
        if self.nav == 2:
            return ["The queue is empty.", "", "Press e on a track to add it,", "or Enter to start playing."]
        if self.nav == 3:
            return ["No playlists yet.", "Press N to create one."]
        return ["Nothing played yet."]

    # ---------------------------------------------------------------- footer
    def hint_list(self):
        """(key label, description, action key, priority) - lower priority number = shown first when space is tight."""
        if self.nav == 2 and not self.query:
            ctx, cp = [("d", "Remove", "d"), ("K/J", "Move", "K"), ("c", "Clear", "c")], 1
        elif self.nav == 3 and not self.query:
            ctx, cp = ([("N", "New", "N"), ("R", "Rename", "R"), ("D", "Delete", "D")] if self.pl_open is None
                       else [("d", "Remove", "d"), ("A", "Add to", "A")]), 1
        else:
            ctx, cp = [("e", "Queue", "e"), ("A", "Playlist", "A")], 3
        base = [("SPACE", "Play", "space", 0), ("s", "Shuffle", "s", 2), ("r", "Repeat", "r", 2),
                ("t", "Theme", "t", 2), ("/", "Search", "/", 4), ("?", "Help", "?", 0), ("q", "Quit", "q", 0)]
        return [(k, d, a, cp) for k, d, a in ctx] + base

    def hint_line(self, w, bg):
        hints = self.hint_list()
        chosen, used = set(), 0
        for i in sorted(range(len(hints)), key=lambda i: (hints[i][3], i)):   # pick by priority...
            k, d, _, _ = hints[i]
            need = cw(k) + 1 + cw(d) + (2 if chosen else 0)
            if used + need <= w:
                chosen.add(i)
                used += need
        L = Line()
        for i, (k, d, act, _) in enumerate(hints):                             # ...but show in natural order
            if i not in chosen:
                continue
            if L.w:
                L.add("  ", None, bg)
            on = self.flashing("key", act)
            L.add(k, self.c("bright"), bg, True, hit=("key", act)).add(" " + d, self.c("text") if on else self.c("muted"), bg, hit=("key", act))
        return L

    def footer_lines(self, w, bg):
        txt, until, kind = self.toast
        L = Line()
        if txt:
            L.add(fit(txt, w - 14), self.c({"ok": "ok", "warn": "warn", "err": "err"}.get(kind, "hl")), bg, True)
        else:
            L.add(fit(short(self.root), w - 40), self.c("text2"), bg)
        n = len(self.tracks)
        right = "%d TRACK%s" % (n, "" if n == 1 else "S")
        if self.total_dur:
            td = int(self.total_dur)
            right += " · %dh %02dm" % (td // 3600, td % 3600 // 60) if td >= 3600 else " · %dm" % (td // 60) if td >= 60 else " · %ds" % td
        if self._meta_i < n:
            right = "INDEXING %d%% · " % (100 * self._meta_i // max(1, n)) + right
        L.add(" " * max(1, w - L.w - cw(right)), None, bg).add(right, self.c("muted"), bg)
        return L, self.hint_line(w, bg)

    # ----------------------------------------------------------------- frames
    def frame_full(self, W, H):
        BG, B = self.c("bg"), self.c("border")
        rows = []

        def edge(l, r, mid="─"):
            rows.append(Line().add(l + mid * (W - 2) + r, B, BG))

        def box(content):
            L = Line().add("│", B, BG)
            content.fill(W - 2, BG)
            L.extend(content)
            L.add("│", B, BG)
            rows.append(L)

        tier = "big" if H >= 30 else "mid" if H >= 21 else "small"
        edge("╭", "╮")
        if tier == "small":
            for ln in self.logo_lines(tier, BG):
                box(ln)
            box(self.author_line(BG))
            tagline = "  // LOCAL AUDIO NODE"
            L = Line().add(tagline, self.c("text2"), BG)
            sc = self.status_chunk(BG)
            L.add(" " * max(1, W - 4 - L.w - sc.w), None, BG).extend(sc)
            box(L)
        else:
            for ln in self.logo_lines(tier, BG):
                box(ln)
            box(self.author_line(BG))
            tagline = "  // LOCAL AUDIO NODE  ·  NO CLOUD"
            L = Line().add(tagline, self.c("text2"), BG)
            sc = self.status_chunk(BG)
            L.add(" " * max(1, W - 4 - L.w - sc.w), None, BG).extend(sc)
            box(L)
        edge("├", "┤")
        top_rows = len(rows)
        body = H - top_rows - 4
        Lw = max(36, int((W - 7) * 0.52))
        Rw = W - 7 - Lw
        self.list_y0 = top_rows + 7
        left = [self.header("TRACK ARCHIVE", Lw, BG, self.focus == "nav")] + self.nav_items(Lw, BG)
        left += self.list_lines(Lw, body - 6, BG)
        right = self.now_lines(Rw, BG, body)
        for i in range(body):
            L = Line().add(" ", None, BG)
            a = left[i] if i < len(left) else Line()
            a.fill(Lw, BG)
            L.extend(a).add(" │ ", B, BG)
            r = right[i] if i < len(right) else Line()
            r.fill(Rw, BG)
            L.extend(r)
            box(L)
        edge("├", "┤")
        f1, f2 = self.footer_lines(W - 5, BG)
        box(Line().add("  ", None, BG).extend(f1))
        box(Line().add("  ", None, BG).extend(f2))
        edge("╰", "╯")
        return rows

    # ---------------------------------------------------------- Kali console
    def kali_logo_color(self, x: int, width: int) -> str:
        """A slow blue/cyan wave moves across both Kali-mode marks."""
        p = x / max(1, width - 1)
        if self.animate:
            blend = 0.5 + 0.5 * math.sin(time.monotonic() * 1.25 - p * math.tau)
            blend = 0.12 + 0.88 * blend
        else:
            blend = p
        return Style.lerp(self.c("brand_a"), self.c("brand_b"), blend)

    def kali_header_row(self, W: int, row_i: int, bg: str, frame: int, header_h: int, placements) -> Line:
        """Compose responsive logo art over blue Matrix rain."""
        chars = [" "] * W
        colors = [None] * W
        bold = [False] * W
        if self.animate:
            for x in range(W):
                cell = matrix_glyph(x, row_i, frame, header_h)
                if cell:
                    chars[x], level = cell
                    colors[x] = MATRIX_COLORS[level]
                    bold[x] = level == 0

        for kind, art, x0, y0, art_w in placements:
            if kind == "author":
                label = fit(AUTHOR_LINE, max(1, art_w))
                x0 += max(0, (art_w - cw(label)) // 2)
                for x, ch in enumerate(label):
                    pos = x0 + x
                    if 0 <= pos < W:
                        chars[pos], colors[pos], bold[pos] = ch, self.c("text2"), False
                continue

            for sy, line in enumerate(art):
                if y0 + sy != row_i:
                    continue
                for x, ch in enumerate(line):
                    pos = x0 + x
                    if 0 <= pos < W and ch != " ":
                        chars[pos] = ch
                        colors[pos] = self.kali_logo_color(x, max(1, art_w))
                        bold[pos] = True

        out = Line()
        start = 0
        for end in range(1, W + 1):
            if end == W or colors[end] != colors[start] or bold[end] != bold[start]:
                out.add("".join(chars[start:end]), colors[start], bg, bold[start])
                start = end
        return out.fill(W, bg)

    def kali_nav_line(self, W: int, bg: str) -> Line:
        """Clickable navigation tabs that shorten when the pane gets narrow."""
        names = ("ALL", "DIRECTORIES", "QUEUE", "PLAYLISTS", "RECENT") if W >= 48 else ("A", "DIR", "Q", "PL", "R")
        L = Line()
        for i, name in enumerate(names):
            label = " " + name + " "
            if L.w + cw(label) > W:
                continue
            active = i == self.nav and not self.query
            fl = self.flashing("tab", i)
            fg = bg if fl else self.c("bright") if active else self.c("text2")
            fill = self.c("accent") if fl else self.c("panel") if active else bg
            L.add(label, fg, fill, active or fl, hit=("tab", i))
        return L.fill(W, bg)

    def kali_player_lines(self, W: int, bg: str, rows_n: int) -> list[Line]:
        """Player details compact progressively to fit the pane."""
        if rows_n <= 0 or W <= 0:
            return []
        e, t = self.engine, self.cur
        title = t.title if t else "Nothing playing"
        artist = (t.artist or "Unknown artist") if t else ("Press Enter to start" if self.tracks else "No audio")
        rows = []
        rows.append(self.header("PLAYER", W, bg) if W >= 12 else
                    Line().add(fit("PLAYER", W), self.c("accent"), bg, True))
        if len(rows) < rows_n:
            rows.append(Line().add(fit(title, W), self.c("text") if t else self.c("text2"), bg, bool(t)))
        if len(rows) < rows_n and W >= 24:
            rows.append(Line().add(fit(artist, W), self.c("muted"), bg))
        if len(rows) < rows_n and W >= 14:
            pos, dur, fr = self.progress_values()
            a, b = fmt_time(pos), (fmt_time(dur) if dur else "--:--")
            progress = Line().add(a + " ", self.c("text"), bg)
            self.bar(progress, max(1, W - cw(a) - cw(b) - 2), fr, bg, "bar")
            progress.add(" " + b, self.c("text2"), bg)
            rows.append(progress.fill(W, bg))
        if len(rows) < rows_n:
            controls = Line()
            if W >= 20:
                self.btn(controls, "Prev", ("btn", "prev"), bg)
                controls.add(" ", None, bg)
                self.btn(controls, "Pause" if e.playing else "Play", ("btn", "play"), bg)
                controls.add(" ", None, bg)
                self.btn(controls, "Next", ("btn", "next"), bg)
            elif W >= 9:
                self.btn(controls, "P", ("btn", "prev"), bg)
                self.btn(controls, "▶" if e.playing else ">", ("btn", "play"), bg)
                self.btn(controls, "N", ("btn", "next"), bg)
            else:
                controls.add(fit("▶" if e.playing else "Ⅱ", W), self.c("accent"), bg)
            rows.append(controls.fill(W, bg))
        if len(rows) < rows_n and W >= 20:
            rows.append(self.vol_line(W, bg, label=False).fill(W, bg))
        status, status_col, dot = self.status()
        if len(rows) < rows_n and W >= 12:
            rows.append(Line().add("● ", dot, bg).add(fit(status, max(1, W - 2)), status_col, bg, True).fill(W, bg))
        return rows[:rows_n]

    def kali_list_lines(self, W: int, rows_n: int, bg: str) -> list[Line]:
        """Library list fallback for narrow terminals."""
        if rows_n <= 0 or W <= 0:
            self.list_rows = 1
            return []
        if W >= 12:
            return self.list_lines(W, rows_n, bg)
        items = self.items()
        visible = max(0, rows_n - 1)
        self.list_rows = max(1, visible)
        self.top = max(0, min(self.top, max(0, len(items) - self.list_rows)))
        out = [Line().add(fit("LIB %d" % len(items), W), self.c("accent"), bg, True)]
        for off in range(visible):
            idx = self.top + off
            if idx >= len(items):
                out.append(Line().fill(W, bg))
                continue
            kind, value = items[idx]
            label = value.title if kind == "track" else value.track.title if kind == "q" else self.row_label(kind, value)
            line = Line().add(fit(label, W), self.c("text") if idx == self.sel else self.c("text2"), bg, idx == self.sel)
            line.hits.append((0, W, "row", off))
            out.append(line)
        return out[:rows_n]

    def frame_kali(self, W: int, H: int) -> list[Line]:
        """Kali layout adapts continuously; no terminal-size minimum is imposed."""
        BG, B = self.c("bg"), self.c("border")
        if W <= 0 or H <= 0:
            return []
        rows: list[Line] = []

        # For a one- or two-row terminal, preserve usability with a clipped
        # identity/player strip rather than refusing to render.
        if H <= 2:
            label = "KALI / XMUSIC" if W > 4 else "X"
            rows.append(Line().add(fit(label, W), self.c("brand_b"), BG, True).fill(W, BG))
            if H == 2:
                rows.append(Line().add(fit("▶ " + (self.cur.title if self.cur else "READY"), W), self.c("text2"), BG).fill(W, BG))
            return rows[:H]

        inner_w = max(1, W - 4)
        header_budget = max(1, min(19, H - 7))
        dragon_source, xmusic_source = logo.kali_lines(), logo.xmusic_lines()
        placements = []
        if W >= 60:
            # Wide composition. The original full-size pair returns when the
            # available dimensions permit it; otherwise each logo scales down.
            dragon_slot = min(logo.kali_width(), max(1, int(inner_w * 0.38)))
            gap = min(3, max(0, inner_w - dragon_slot - 1))
            xmusic_slot = max(1, inner_w - dragon_slot - gap)
            dragon_lines = logo.fit_lines(dragon_source, dragon_slot, header_budget)
            show_author = header_budget >= 5
            xmusic_lines = logo.fit_lines(xmusic_source, xmusic_slot, max(1, header_budget - (1 if show_author else 0)))
            header_h = max(len(dragon_lines), len(xmusic_lines) + (1 if show_author else 0))
            placements.append(("art", dragon_lines, 2, max(0, (header_h - len(dragon_lines)) // 2), dragon_slot))
            xmusic_y = max(0, (header_h - len(xmusic_lines) - (1 if show_author else 0)) // 2)
            placements.append(("art", xmusic_lines, 2 + dragon_slot + gap, xmusic_y, xmusic_slot))
            if show_author:
                placements.append(("author", [], 2 + dragon_slot + gap, xmusic_y + len(xmusic_lines), xmusic_slot))
        else:
            # Narrow composition. Stack the two scaled marks vertically.
            show_author = header_budget >= 5
            art_budget = max(2, header_budget - (1 if show_author else 0))
            dragon_h = max(1, int(art_budget * 0.58))
            xmusic_h = max(1, art_budget - dragon_h)
            dragon_lines = logo.fit_lines(dragon_source, inner_w, dragon_h)
            xmusic_lines = logo.fit_lines(xmusic_source, inner_w, xmusic_h)
            header_h = len(dragon_lines) + 1 + len(xmusic_lines) + (1 if show_author else 0)
            dragon_w = max(map(len, dragon_lines))
            xmusic_w = max(map(len, xmusic_lines))
            placements.append(("art", dragon_lines, max(0, (W - dragon_w) // 2), 0, dragon_w))
            xmusic_y = len(dragon_lines) + 1
            placements.append(("art", xmusic_lines, max(0, (W - xmusic_w) // 2), xmusic_y, xmusic_w))
            if show_author:
                placements.append(("author", [], max(0, (W - xmusic_w) // 2), xmusic_y + len(xmusic_lines), xmusic_w))

        frame = int(time.monotonic() * 8) if self.animate else 0
        for y in range(header_h):
            rows.append(self.kali_header_row(W, y, BG, frame, header_h, placements))

        body_h = H - len(rows)
        if body_h <= 0:
            return rows[:H]
        if body_h >= 2 and W >= 8:
            rows.append(Line().add("─" * W, B, BG))
            body_h -= 1
        if body_h <= 0:
            return rows[:H]

        if W >= 60 and body_h >= 4:
            # Two panes while there is enough horizontal room.
            panel_w = max(1, W - 7)
            player_w = max(1, int(panel_w * 0.40))
            playlist_w = max(1, panel_w - player_w)
            player = self.kali_player_lines(player_w, BG, body_h)
            playlist = [
                self.header("PLAYLIST / ARCHIVE", playlist_w, BG, self.focus == "list") if playlist_w >= 12
                else Line().add(fit("LIBRARY", playlist_w), self.c("accent"), BG, True),
                self.kali_nav_line(playlist_w, BG),
            ]
            self.list_y0 = len(rows) + 2
            playlist.extend(self.kali_list_lines(playlist_w, max(0, body_h - 2), BG))
            for i in range(body_h):
                left = player[i] if i < len(player) else Line()
                right = playlist[i] if i < len(playlist) else Line()
                L = Line().add("  ", None, BG).extend(left.fill(player_w, BG))
                L.add(" │ ", B, BG).extend(right.fill(playlist_w, BG)).add("  ", None, BG)
                rows.append(L.fill(W, BG))
        else:
            # Narrow or short screens stack player, navigation, then library.
            player_rows = min(2 if W < 24 else 3, max(1, body_h // 3))
            pad = 1 if W >= 3 else 0
            pane_w = max(1, W - 2 * pad)
            player = self.kali_player_lines(pane_w, BG, player_rows)
            for line in player:
                rows.append(Line().add(" " * pad, None, BG).extend(line).fill(W, BG))
            remaining = H - len(rows)
            if remaining > 0 and W >= 10:
                nav = self.kali_nav_line(pane_w, BG)
                rows.append(Line().add(" " * pad, None, BG).extend(nav).fill(W, BG))
            remaining = H - len(rows)
            if remaining > 0:
                self.list_y0 = len(rows)
                rows.extend(
                    Line().add(" " * pad, None, BG).extend(line).fill(W, BG)
                    for line in self.kali_list_lines(pane_w, remaining, BG)
                )
        return rows[:H]

    def frame_compact(self, W, H):
        """Standard layout with the supplied XMusic artwork fitted to the viewport."""
        BG = self.c("bg")
        if W <= 0 or H <= 0:
            return []
        rows = []
        header_h = max(1, min(6, max(1, (H - 3) // 3)))
        art = self.logo_lines("compact", BG, max(1, W), header_h, margin=0)
        rows.extend(line.fill(W, BG) for line in art)

        if H - len(rows) >= 6:
            rows.append(self.author_line(BG, start=0, width=W).fill(W, BG))

        remaining = H - len(rows)
        if remaining >= 4 and W >= 8:
            tabs = Line()
            names = NAV if W >= 66 else NAV_SHORT
            for i, name in enumerate(names):
                label = " " + name + " "
                if tabs.w + cw(label) > W:
                    continue
                active = i == self.nav and not self.query
                fl = self.flashing("tab", i)
                tabs.add(label, BG if fl else self.c("bright") if active else self.c("text2"),
                         self.c("bright") if fl else self.c("panel") if active else BG,
                         active, hit=("tab", i))
            rows.append(tabs.fill(W, BG))
            remaining -= 1

        player_rows = min(3, max(1, remaining // 3)) if remaining else 0
        list_rows = max(0, remaining - player_rows)
        self.list_y0 = len(rows)
        if list_rows:
            if W >= 12:
                rows.extend(self.list_lines(W, list_rows, BG))
            else:
                items = self.items()
                visible = max(0, list_rows - 1)
                self.list_rows = max(1, visible)
                rows.append(Line().add(fit("LIB %d" % len(items), W), self.c("accent"), BG, True))
                for off in range(visible):
                    idx = self.top + off
                    if idx < len(items):
                        kind, value = items[idx]
                        label = value.title if kind == "track" else value.track.title if kind == "q" else self.row_label(kind, value)
                        line = Line().add(fit(label, W), self.c("text2"), BG, idx == self.sel)
                        line.hits.append((0, W, "row", off))
                    else:
                        line = Line().fill(W, BG)
                    rows.append(line)

        if player_rows:
            title = self.cur.title if self.cur else "Nothing playing"
            prefix = "▶ " if self.engine.playing else "Ⅱ " if self.engine.paused else ""
            rows.append(Line().add(fit(prefix + title, W), self.c("text") if self.cur else self.c("text2"), BG, bool(self.cur)))
            if len(rows) < H and player_rows >= 2 and W >= 12:
                pos, dur, frac = self.progress_values()
                a, b = fmt_time(pos), (fmt_time(dur) if dur else "--:--")
                line = Line().add(a + " ", self.c("text"), BG)
                self.bar(line, max(1, W - cw(a) - cw(b) - 2), frac, BG, "bar")
                line.add(" " + b, self.c("text2"), BG)
                rows.append(line.fill(W, BG))
            if len(rows) < H and player_rows >= 3:
                line = Line()
                if W >= 20:
                    self.btn(line, "Prev", ("btn", "prev"), BG)
                    self.btn(line, "Play" if not self.engine.playing else "Pause", ("btn", "play"), BG)
                    self.btn(line, "Next", ("btn", "next"), BG)
                elif W >= 9:
                    self.btn(line, "P", ("btn", "prev"), BG)
                    self.btn(line, "▶" if self.engine.playing else ">", ("btn", "play"), BG)
                    self.btn(line, "N", ("btn", "next"), BG)
                else:
                    line.add(fit("▶" if self.engine.playing else "Ⅱ", W), self.c("accent"), BG)
                rows.append(line.fill(W, BG))
        return rows[:H]

    def frame_help(self, W, H):
        BG = self.c("bg")
        rows = []
        L = Line()
        if self.kali_mode:
            L.add(fit("KALI // ", W), self.c("brand_b"), BG, True)
        else:
            art = self.logo_lines("help", BG, max(1, W - 1), 1, margin=0)
            if art:
                L.extend(art[0].slice(0, max(0, W - 1)))
            if L.w < W:
                L.add(" ", None, BG).add(fit("KEYBOARD & MOUSE", max(0, W - L.w)), self.c("text2"), BG)
        rows.append(L.fill(W, BG))
        rows.append(Line().add("─" * W, self.c("border"), BG))
        two = W >= 76
        cw_ = (W - 4) // 2 if two else W - 2
        entries = list(HELP)
        avail = H - 3
        if two:                                         # two columns, split at a section boundary near the middle
            half = (len(entries) + 1) // 2
            cut = min((i for i, (k, d) in enumerate(entries) if d is None and i >= half - 2), default=half)
            cols = [entries[:cut], entries[cut:]]
        else:
            cols = [entries[self.help_top:self.help_top + avail]]
        for r in range(avail):
            L = Line().add(" ", None, BG)
            for col in cols:
                if r < len(col):
                    k, d = col[r]
                    seg = Line()
                    if d is None:
                        seg.add(k, self.c("accent"), BG, True)
                    else:
                        seg.add(k.ljust(13), self.c("bright"), BG, True).add(fit(d, cw_ - 14), self.c("text2"), BG)
                else:
                    seg = Line()
                seg.fill(cw_ + (2 if two else 0), BG)
                L.extend(seg)
            rows.append(L.fill(W, BG))
        rows.append(Line().add("  Esc / ? / click to close" + ("" if two else "   ↑↓ scroll"), self.c("muted"), BG).fill(W, BG))
        return rows[:H]

    # ----------------------------------------------------------------- dialogs
    def draw_modal(self, rows, W, H):
        m = self.modal
        bg, panel, acc = self.c("bg"), self.c("panel"), self.c("accent")
        mw = max(28, min(W - 4, 48))
        inner = mw - 4
        body: list[Line] = []
        hits: list[tuple] = []                           # (row index inside body, kind, arg)

        def row(L, hit=None):
            if hit:
                hits.append((len(body), hit[0], hit[1]))
            body.append(L)

        kind = m["kind"]
        if kind in ("theme", "picker"):
            entries = m["entries"]
            vis = max(3, min(len(entries), H - 8))
            m["top"] = max(0, min(m.get("top", 0), max(0, len(entries) - vis)))
            if m["sel"] < m["top"]:
                m["top"] = m["sel"]
            if m["sel"] >= m["top"] + vis:
                m["top"] = m["sel"] - vis + 1
            for i in range(m["top"], min(len(entries), m["top"] + vis)):
                sel = i == m["sel"]
                rb = Style.lerp(panel, acc, 0.28) if sel else panel
                L = Line().add("● " if sel else "  ", acc, rb, True)
                if kind == "theme":
                    th = THEMES[entries[i]]
                    L.add(th["name"].ljust(15), self.c("text") if sel else self.c("text2"), rb, sel)
                    for role in ("accent", "bright", "hl"):
                        L.add("██", th[role], rb)
                    L.add(" ", None, rb)
                    if th["id"] == m["saved"]:
                        L.add("✓ saved", self.c("ok"), rb)
                else:
                    L.add(fit(entries[i][0], inner - 2), self.c("text") if sel else self.c("text2"), rb, sel)
                L.fill(inner, rb)
                row(L, ("mrow", i))
            foot = "↑↓ preview · Enter apply · Esc cancel" if kind == "theme" else "↑↓ choose · Enter add · Esc cancel"
            if kind == "theme":
                body.append(Line().add(fit(THEMES[entries[m["sel"]]]["desc"], inner), self.c("muted"), panel))
        elif kind == "prompt":
            row(Line().add(fit(m["label"], inner), self.c("text2"), panel))
            L = Line().add("› ", self.c("search"), panel, True).add(fit(m["text"], inner - 3), self.c("text"), panel, True).add("▏", self.c("hl"), panel)
            row(L)
            body.append(Line().add(fit(m.get("err", ""), inner), self.c("err"), panel))
            foot = "Enter confirm · Esc cancel"
        else:                                            # confirm
            for ln in m["lines"]:
                row(Line().add(fit(ln, inner), self.c("text"), panel))
            row(Line())
            L = Line()
            for label, key in (("Yes", "yes"), ("No", "no")):
                sel = m["sel"] == key
                L.add(" " + label + " ", bg if sel else self.c("text"), acc if sel else bg, True, hit=("mbtn", key))
                L.add("  ", None, panel)
            hits.append((len(body), "mbtn_row", None))
            body.append(L)
            foot = "y yes · n no · Esc cancel"
        out = []
        title = " " + m["title"] + " "
        out.append(Line().add("╭─", acc, panel).add(title, self.c("bright"), panel, True).add("─" * max(0, mw - 3 - cw(title)) + "╮", acc, panel))
        hit_rows = {i: (k, a) for i, k, a in hits}
        for i, ln in enumerate(body):
            seg = Line().add("│ ", acc, panel)
            ln.fill(inner, panel)
            seg.extend(ln)
            seg.add(" │", acc, panel)
            out.append(seg)
        out.append(Line().add("│ ", acc, panel).add(fit(foot, inner).ljust(inner), self.c("muted"), panel).add(" │", acc, panel))
        out.append(Line().add("╰" + "─" * (mw - 2) + "╯", acc, panel))
        x0, y0 = (W - mw) // 2, max(0, (H - len(out)) // 2)
        for i, ln in enumerate(out):
            if 0 <= y0 + i < len(rows):
                rows[y0 + i] = rows[y0 + i].overlay(x0, ln)
        # modal owns all mouse input
        for i, ln in enumerate(out):
            for a, b, k, g in ln.hits:
                if k == "mbtn":
                    self.hits.append((y0 + i, x0 + a, x0 + b, k, g))
        for bi, (k, a) in hit_rows.items():
            if k == "mrow":
                self.hits.append((y0 + 1 + bi, x0 + 1, x0 + mw - 1, "mrow", a))
        m["geo"] = (x0, y0, mw, len(out))
