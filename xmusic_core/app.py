"""XMusic application: state, playback orchestration, input handling and the single event loop."""
from __future__ import annotations

import os
import random
import time

from . import library, themes
from .audio import Engine
from .config import REPEAT_MODES, Settings, State
from .playlists import FAVORITES, Playlists
from .playqueue import PlayQueue
from .render import HL, INTRO, NAV, SORTS, Renderer
from .term import make_terminal
from .themes import Style
from .ui import fit


class App(Renderer):
    def __init__(self, root: str, settings: Settings, state: State, playlists: Playlists, *, animate=True,
                 null_audio=False, ascii_mode=False, theme_id: str | None = None):
        self.root, self.settings, self.state, self.playlists = root, settings, state, playlists
        self.animate, self.ascii = animate, ascii_mode
        self.term = make_terminal()
        self.style = Style()
        self.theme = themes.get(theme_id or settings["theme"])
        self.engine = Engine(null=null_audio)
        self.engine.set_volume(settings["volume"])
        self.engine.set_muted(settings["muted"])
        self.q = PlayQueue()
        self.q.set_shuffle(settings["shuffle"])
        self.q.set_repeat(settings["repeat"])
        self.audio_err = None
        self.tracks, self.by_path, self.scan_errors = [], {}, []
        self._tree = self._sorted = self._items = None
        self._meta_i, self.total_dur = 0, 0.0
        self.nav, self.folder, self.pl_open, self.sort = 0, root, None, 0
        self.query, self.searching, self.focus = "", False, "list"
        self.sel = self.top = 0
        self.view_title = "TRACKS"
        self.cur = None                                   # Track loaded in the engine
        self.help, self.help_top, self.modal = False, 0, None
        self.toast = ("", 0.0, "info")
        self.flash, self.hl_until = {}, 0.0
        self.hits, self.list_y0, self.list_rows, self.mode = [], 0, 10, "full"
        self.bar_geo = self.vol_geo = None
        self.drag = self.drag_frac = None
        self._last_click = (0.0, None)
        self._pending_seek = None
        self.dirty, self._prev = True, None
        self.t0 = time.monotonic()
        self.intro = animate
        self.fade = 0.0 if animate else 1.0
        self._tick = (-1, -1)
        self.quit = False

    # ------------------------------------------------------------------ lifecycle
    def run(self):
        self.term.start()
        try:
            try:
                self.engine.open()
            except Exception as e:
                self.audio_err = str(e) or type(e).__name__
            self.rescan()
            self.restore_queue()
            if self.settings.warning:
                self.say(self.settings.warning, "warn", 4)
            self.loop()
        finally:
            self.persist()
            self.engine.close()
            self.term.stop()

    def persist(self):
        s = self.settings
        s["volume"], s["muted"] = self.engine.volume, self.engine.muted
        s["shuffle"], s["repeat"], s["music_dir"] = self.q.shuffle, self.q.repeat, self.root
        s.save()
        items = [x.track.path for x in self.q.items]
        cur = self.q.cur.track.path if self.q.cur else None
        if len(items) > 1000:                             # keep a window around the current item
            i = next((k for k, x in enumerate(self.q.items) if x is self.q.cur), 0)
            items = items[max(0, i - 100):max(0, i - 100) + 1000]
        self.state.queue, self.state.current = items, cur
        self.state.save()

    def rescan(self):
        old = self.by_path
        self.scan_errors = []
        found = library.scan(self.root, self.scan_errors)
        self.tracks = [old.get(t.path, t) for t in found]        # keep loaded metadata for known files
        self.by_path = {t.path: t for t in self.tracks}
        self._tree = self._sorted = self._items = None
        self._meta_i, self.total_dur = 0, 0.0
        self.reset_view()
        self.dirty = True

    def restore_queue(self):
        tracks = [self.by_path[p] for p in self.state.queue if p in self.by_path]
        if tracks:
            idx = next((i for i, t in enumerate(tracks) if t.path == self.state.current), None)
            self.q.set_tracks(tracks, idx or 0)
            if idx is None:
                self.q.cur = None

    # --------------------------------------------------------------- view model
    def reset_view(self):
        self._items, self.sel, self.top = None, 0, 0

    def sorted_all(self):
        if self._sorted is None:
            ts, k = list(self.tracks), SORTS[self.sort]
            if k == "title":
                ts.sort(key=lambda t: t.title.lower())
            elif k == "artist":
                ts.sort(key=lambda t: (t.artist.lower() or "\uffff", t.title.lower()))
            elif k == "album":
                ts.sort(key=lambda t: (t.album.lower() or "\uffff", t.path.lower()))
            elif k == "length":
                ts.sort(key=lambda t: t.duration)
            self._sorted = ts
        return self._sorted

    def track_for(self, path: str):
        t = self.by_path.get(path)
        if t is None and os.path.isfile(path):            # playlist entry outside the scanned library
            t = self.by_path[path] = library.Track(path)
        return t

    def items(self):
        if self._items is not None:
            return self._items
        q, it = self.query.strip().lower(), []
        if q:
            words = q.split()
            it = [("track", t) for t in self.sorted_all() if all(w in t.haystack() for w in words)]
            self.view_title = "SEARCH"
        elif self.nav == 0:
            it = [("track", t) for t in self.sorted_all()]
            self.view_title = "TRACKS" + (" · by " + SORTS[self.sort] if self.sort else "")
        elif self.nav == 1:
            if self._tree is None:
                self._tree = library.build_tree(self.tracks, self.root)
            dirs, trs = self._tree.get(self.folder, ([], []))
            if self.folder != self.root:
                it.append(("up", None))
            it += [("dir", os.path.join(self.folder, d)) for d in dirs] + [("track", t) for t in trs]
            rel = os.path.relpath(self.folder, self.root)
            self.view_title = "FOLDERS" + ("" if rel == "." else " · " + rel)
        elif self.nav == 2:
            it = [("q", x) for x in self.q.seq]
            self.view_title = "QUEUE · %d up next" % len(self.q.upcoming())
        elif self.nav == 3:
            if self.pl_open is None:
                it = [("plnew", None)] + [("pl", n) for n in self.playlists.names()]
                self.view_title = "PLAYLISTS"
            else:
                it = [("plup", None), ("plplay", self.pl_open)]
                for p in self.playlists.get(self.pl_open):
                    t = self.track_for(p)
                    it.append(("track", t) if t else ("missing", p))
                self.view_title = "PLAYLIST · " + self.pl_open
        else:
            it = [("track", t) for t in (self.track_for(p) for p in self.state.recent) if t]
            self.view_title = "RECENTLY PLAYED"
        self._items = it
        self.sel = max(0, min(self.sel, len(it) - 1))
        return it

    def set_nav(self, i):
        self.nav, self.pl_open, self.query, self.searching = i, None, "", False
        if i == 1:
            self.folder = self.root
        self.reset_view()
        if i == 2:
            self.items()
            self.sel = max(0, self.q.pos())
            self.move(0)
        self.dirty = True

    def invalidate_queue_view(self):
        if self.nav == 2 and not self.query:
            self._items = None
        self.dirty = True

    def selected(self):
        items = self.items()
        return items[self.sel] if items else (None, None)

    def selected_track(self):
        kind, val = self.selected()
        return val if kind == "track" else val.track if kind == "q" else None

    # ---------------------------------------------------------------- playback
    def say(self, text, kind="info", dur=1.8):
        self.toast = (text, time.monotonic() + dur, kind)
        self.dirty = True

    def try_play(self, track, start=0.0) -> bool:
        if self.audio_err:
            self.say("No audio device: " + fit(self.audio_err, 40), "err", 3)
            return False
        try:
            if not track.loaded:
                track.load_meta()
            self.engine.play(track.path, start)
        except Exception:
            track.bad = True
            self.say("Can't play " + fit(os.path.basename(track.path), 32), "err", 2.5)
            return False
        self.cur = track
        self.hl_until = time.monotonic() + HL
        rec = self.state.recent
        if track.path in rec:
            rec.remove(track.path)
        rec.insert(0, track.path)
        del rec[50:]
        if self.nav == 4:
            self._items = None
        self.invalidate_queue_view()
        return True

    def go(self, getter) -> bool:
        """Move through the queue with `getter` until something plays; skips undecodable tracks."""
        for _ in range(len(self.q.items) + 1):
            it = getter()
            if it is None:
                self.engine.stop()
                self.cur = None
                self.say("End of queue")
                self.invalidate_queue_view()
                return False
            if self.try_play(it.track):
                return True
            getter = lambda: self.q.advance(auto=False)
        self.engine.stop()
        self.cur = None
        self.say("No playable tracks", "err")
        return False

    def play_context(self, items, sel_idx, random_start=False):
        tracks = [v for k, v in items if k == "track"]
        if not tracks:
            return
        start = sum(1 for k, _ in items[:sel_idx] if k == "track")
        if random_start and self.q.shuffle:
            start = random.randrange(len(tracks))
        if self.try_play(tracks[start]):
            self.q.set_tracks(tracks, start)
            self.invalidate_queue_view()

    def jump_to(self, item):
        if self.try_play(item.track):
            self.q.jump(item)
            self.invalidate_queue_view()

    def next_track(self):
        if not self.q.seq:
            self.say("The queue is empty")
            return
        self.go(lambda: self.q.advance(auto=False))

    def prev_track(self):
        if self.engine.active and self.engine.position() > 3:
            self.apply_seek(0.0)
            return
        it = self.q.retreat()
        if it is not None:
            if not self.try_play(it.track):
                self.q.advance(auto=False)
        elif self.cur:
            self.apply_seek(0.0)

    def toggle_play(self):
        e = self.engine
        if e.active and self.cur:
            e.toggle_pause()
            self.dirty = True
            return
        kind, _ = self.selected()
        items = self.items()
        if kind in ("track", "plplay") and self.nav != 2:
            self.play_context(items, self.sel, random_start=(kind == "plplay"))
        elif self.q.cur:
            if self.try_play(self.q.cur.track):
                self.invalidate_queue_view()
        elif self.q.seq:
            it = self.q.seq[0]
            if self.try_play(it.track):
                self.q.jump(it)
                self.invalidate_queue_view()
        elif any(k == "track" for k, _ in items):
            self.play_context(items, next(i for i, (k, _) in enumerate(items) if k == "track"))
        else:
            self.say("Nothing to play")

    def stop(self):
        self.engine.stop()
        self.cur = None
        self.dirty = True

    def apply_seek(self, target):
        if not (self.cur and self.engine.active):
            return
        dur, target = self.cur.duration, max(0.0, target)
        if dur and target >= dur - 0.5:
            self.go(lambda: self.q.advance(auto=False))
            return
        try:
            self.engine.play(self.cur.path, target, paused=self.engine.paused)
        except Exception:
            self.say("Seek failed", "err")
        self.dirty = True

    def set_volume(self, v, toast=True):
        self.engine.set_volume(v)
        if self.engine.muted and v > 0:
            self.engine.set_muted(False)
        if toast:
            self.say("Volume %d%%" % self.engine.volume, dur=1.0)
        self.dirty = True

    def toggle_mute(self):
        self.engine.set_muted(not self.engine.muted)
        self.say("Muted" if self.engine.muted else "Unmuted", "warn" if self.engine.muted else "info", 1.2)

    def toggle_shuffle(self):
        self.q.set_shuffle(not self.q.shuffle)
        self.say("Shuffle " + ("ON" if self.q.shuffle else "OFF"), dur=1.2)
        self.invalidate_queue_view()

    def cycle_repeat(self):
        self.q.set_repeat(REPEAT_MODES[(REPEAT_MODES.index(self.q.repeat) + 1) % 3])
        self.say("Repeat " + {"off": "OFF", "all": "ALL (queue)", "one": "ONE (track)"}[self.q.repeat], dur=1.2)
        self.dirty = True

    # -------------------------------------------------------------- queue ops
    def enqueue(self, play_next=False):
        t = self.selected_track()
        if t is None:
            self.say("Select a track first")
            return
        self.q.enqueue(t, play_next=play_next)
        self.say(("Playing next: " if play_next else "Queued: ") + fit(t.title, 30), "ok")
        self.invalidate_queue_view()

    def queue_remove(self):
        kind, val = self.selected()
        if self.nav != 2 or kind != "q":
            return
        if not self.q.remove(val):
            self.say("Can't remove the playing track", "warn")
            return
        self._items = None
        self.items()
        self.move(0)
        self.say("Removed from queue")

    def queue_move(self, d):
        kind, val = self.selected()
        if self.nav != 2 or kind != "q":
            return
        if self.q.move(val, d):
            self._items = None
            self.items()
            self.move(d)
        self.dirty = True

    def queue_clear(self):
        if not self.q.items:
            return
        self.q.clear()
        self.reset_view()
        self.say("Queue cleared (current track keeps playing)")

    # --------------------------------------------------------------- playlists
    def toggle_fav(self):
        t = self.selected_track()
        if t is None:
            return
        on = self.playlists.toggle(FAVORITES, t.path)
        self.say(("Added to " if on else "Removed from ") + FAVORITES, "ok")
        if self.nav == 3:
            self._items = None

    def open_picker(self):
        t = self.selected_track()
        if t is None:
            self.say("Select a track first")
            return
        entries = [(n + (" ✓" if self.playlists.contains(n, t.path) else ""), n) for n in self.playlists.names()]
        entries.append(("+ New playlist…", None))
        self.modal = {"kind": "picker", "title": "ADD TO PLAYLIST", "entries": entries, "sel": 0, "track": t, "top": 0}
        self.dirty = True

    def prompt(self, title, label, text, on_ok):
        self.modal = {"kind": "prompt", "title": title, "label": label, "text": text, "on_ok": on_ok}
        self.dirty = True

    def confirm(self, title, lines, on_yes):
        self.modal = {"kind": "confirm", "title": title, "lines": lines, "sel": "no", "on_yes": on_yes}
        self.dirty = True

    def new_playlist(self, then_add=None):
        def ok(text):
            err = self.playlists.valid_name(text)
            if err:
                return err
            n = self.playlists.create(text)
            if then_add is not None:
                self.playlists.add(n, then_add.path)
            self.say("Created playlist " + n + (" with 1 track" if then_add else ""), "ok")
            self._items = None
            return None
        self.prompt("NEW PLAYLIST", "Playlist name", "", ok)

    def rename_playlist(self):
        kind, name = self.selected()
        if self.nav != 3 or kind != "pl":
            return
        if name == FAVORITES:
            self.say("Favorites can't be renamed", "warn")
            return

        def ok(text):
            err = self.playlists.valid_name(text, ignore=name)
            if err:
                return err
            self.playlists.rename(name, text)
            self.say("Renamed", "ok")
            self._items = None
            return None
        self.prompt("RENAME PLAYLIST", "New name for " + name, name, ok)

    def delete_playlist(self):
        kind, name = self.selected()
        if self.nav != 3 or kind != "pl":
            return
        if name == FAVORITES:
            self.say("Favorites can't be deleted", "warn")
            return

        def yes():
            self.playlists.delete(name)
            self.say("Deleted " + name, "ok")
            self._items = None
            self.sel = 0
        self.confirm("DELETE PLAYLIST", ["Delete '%s' (%d tracks)?" % (name, len(self.playlists.get(name))), "This can't be undone."], yes)

    def playlist_remove_track(self):
        kind, val = self.selected()
        if self.nav != 3 or self.pl_open is None or kind not in ("track", "missing"):
            return
        self.playlists.remove(self.pl_open, val if kind == "missing" else val.path)
        self._items = None
        self.items()
        self.move(0)
        self.say("Removed from " + self.pl_open)

    # ---------------------------------------------------------------- activation
    def activate(self):
        items = self.items()
        if not items:
            return
        kind, val = items[self.sel]
        if kind == "track":
            self.play_context(items, self.sel)
        elif kind == "q":
            self.jump_to(val)
        elif kind == "dir":
            self.folder = val
            self.reset_view()
        elif kind == "up":
            old, self.folder = self.folder, os.path.dirname(self.folder)
            self.reset_view()
            for i, (k, v) in enumerate(self.items()):
                if k == "dir" and v == old:
                    self.sel = i
                    self.move(0)
                    break
        elif kind == "pl":
            self.pl_open = val
            self.reset_view()
        elif kind == "plup":
            self.pl_open = None
            self.reset_view()
        elif kind == "plplay":
            if not any(k == "track" for k, _ in items):
                self.say("Playlist has no playable tracks", "warn")
            else:
                self.play_context(items, next(i for i, (k, _) in enumerate(items) if k == "track"), random_start=True)
        elif kind == "plnew":
            self.new_playlist()
        elif kind == "missing":
            self.say("File not found: " + fit(os.path.basename(val), 30), "warn")
        self.dirty = True

    def go_back(self):
        if self.nav == 1 and self.folder != self.root:
            self.folder = os.path.dirname(self.folder)
            self.reset_view()
        elif self.nav == 3 and self.pl_open is not None:
            self.pl_open = None
            self.reset_view()
        self.dirty = True

    # ------------------------------------------------------------------ dialogs
    def open_theme_picker(self):
        ids = themes.theme_ids()
        self.modal = {"kind": "theme", "title": "THEME", "entries": ids, "sel": ids.index(self.theme["id"]),
                      "saved": self.theme["id"], "top": 0}
        self.dirty = True

    def close_modal(self, revert=True):
        m, self.modal = self.modal, None
        if m and m["kind"] == "theme" and revert:
            self.theme = themes.THEMES[m["saved"]]
        self.dirty = True

    def modal_choose(self, i=None):
        m = self.modal
        if i is not None:
            m["sel"] = i
        if m["kind"] == "theme":
            tid = m["entries"][m["sel"]]
            self.theme = themes.THEMES[tid]
            self.settings["theme"] = tid
            self.settings.save()
            self.modal = None
            self.say("Theme: " + self.theme["name"], "ok")
        elif m["kind"] == "picker":
            label, name = m["entries"][m["sel"]]
            self.modal = None
            if name is None:
                self.new_playlist(then_add=m["track"])
            else:
                added = self.playlists.add(name, m["track"].path)
                self.say(("Added to " if added else "Already in ") + name, "ok" if added else "warn")
                self._items = None
        self.dirty = True

    def modal_key(self, k):
        m = self.modal
        kind = m["kind"]
        self.dirty = True
        if kind in ("theme", "picker"):
            n = len(m["entries"])
            if k in ("up", "down", "pgup", "pgdn", "home", "end"):
                d = {"up": -1, "down": 1, "pgup": -3, "pgdn": 3}.get(k)
                m["sel"] = 0 if k == "home" else n - 1 if k == "end" else max(0, min(n - 1, m["sel"] + d))
                if kind == "theme":
                    self.theme = themes.THEMES[m["entries"][m["sel"]]]      # live preview
            elif k == "enter":
                self.modal_choose()
            elif k in ("esc", "q") or (k == "t" and kind == "theme"):
                self.close_modal()
        elif kind == "prompt":
            if k == "esc":
                self.close_modal()
            elif k == "enter":
                err = m["on_ok"](m["text"])
                if err:
                    m["err"] = err
                else:
                    self.modal = None
            elif k == "backspace":
                m["text"], m["err"] = m["text"][:-1], ""
            elif k == "space" or len(k) == 1:
                if len(m["text"]) < 40:
                    m["text"] += " " if k == "space" else k
                m["err"] = ""
        else:
            if k in ("y", "Y") or (k == "enter" and m["sel"] == "yes"):
                self.modal = None
                m["on_yes"]()
            elif k in ("n", "N", "esc") or (k == "enter" and m["sel"] == "no"):
                self.close_modal()
            elif k in ("left", "right", "tab", "backtab"):
                m["sel"] = "yes" if m["sel"] == "no" else "no"

    # ------------------------------------------------------------------- input
    def on_key(self, k):
        if self.intro:
            self.intro, self.fade = False, 1.0
        if k == "ctrl-c":
            self.quit = True
            return
        self.dirty = True
        if self.modal:
            self.modal_key(k)
            return
        if self.help:
            if k in ("esc", "?", "q", "enter"):
                self.help, self._prev = False, None
            elif k in ("up", "down", "pgup", "pgdn"):
                self.help_top = max(0, self.help_top + {"up": -1, "down": 1, "pgup": -8, "pgdn": 8}[k])
            return
        if self.searching:
            if k == "esc":
                self.query, self.searching = "", False
                self.reset_view()
            elif k == "enter":
                self.searching = False
            elif k == "backspace":
                self.query = self.query[:-1]
                self.reset_view()
            elif k in ("up", "down", "pgup", "pgdn"):
                self.nav_key(k)
            elif k == "space" or len(k) == 1:
                self.query += " " if k == "space" else k
                self.reset_view()
            return
        simple = {"q": lambda: setattr(self, "quit", True), "space": self.toggle_play, "x": self.stop,
                  "n": self.next_track, "p": self.prev_track, "m": self.toggle_mute, "s": self.toggle_shuffle,
                  "r": self.cycle_repeat, "t": self.open_theme_picker, "e": self.enqueue,
                  "E": lambda: self.enqueue(True), "a": self.toggle_fav, "A": self.open_picker,
                  "c": self.queue_clear, "K": lambda: self.queue_move(-1), "J": lambda: self.queue_move(1),
                  "N": self.new_playlist, "R": self.rename_playlist, "D": self.delete_playlist,
                  "go_back": self.go_back, "backspace": self.go_back, "f5": self.rescan_cmd, "z": self.toggle_animation}
        if k in simple:
            simple[k]()
        elif k == "enter":
            if self.focus == "nav":
                self.focus = "list"
            else:
                self.activate()
        elif k in ("up", "down", "pgup", "pgdn", "home", "end"):
            self.nav_key(k)
        elif k in ("left", "right"):
            if self.engine.active:
                base = self._pending_seek if self._pending_seek is not None else self.engine.position()
                self._pending_seek = base + (5 if k == "right" else -5)
        elif k in ("+", "="):
            self.set_volume(self.engine.volume + 5)
        elif k in ("-", "_"):
            self.set_volume(self.engine.volume - 5)
        elif k == "/":
            self.searching, self.focus = True, "list"
        elif k in ("tab", "backtab"):
            self.focus = "nav" if self.focus == "list" else "list"
        elif k == "l":
            self.set_nav(0)
        elif k == "f":
            self.set_nav(1)
            self.focus = "list"
        elif k in ("1", "2", "3", "4", "5"):
            self.set_nav(int(k) - 1)
        elif k == "Q":
            self.set_nav(2)
        elif k == "?":
            self.help, self.help_top, self._prev = True, 0, None
        elif k == "esc":
            if self.query:
                self.query = ""
                self.reset_view()
        elif k in ("d", "delete"):
            if self.nav == 3 and self.pl_open is None:
                self.delete_playlist()
            elif self.nav == 3:
                self.playlist_remove_track()
            else:
                self.queue_remove()
        elif k == "o":
            self.sort = (self.sort + 1) % len(SORTS)
            self._sorted = self._items = None
            self.say("Sort: " + SORTS[self.sort])

    def rescan_cmd(self):
        self.rescan()
        self.say("Rescanned: %d tracks" % len(self.tracks))

    def toggle_animation(self):
        self.animate = not self.animate
        self.intro = False
        self.fade = 1.0
        self.settings["animation"] = self.animate
        self.settings.save()
        self.say("Animations " + ("ON" if self.animate else "OFF"))

    def nav_key(self, k):
        if self.focus == "nav" and not self.searching:
            d = {"up": -1, "down": 1, "home": -9, "end": 9, "pgup": -1, "pgdn": 1}[k]
            self.set_nav(max(0, min(len(NAV) - 1, self.nav + d)))
            return
        R = max(1, self.list_rows)
        if k == "up":
            self.move(-1)
        elif k == "down":
            self.move(1)
        elif k == "pgup":
            self.move(-R)
        elif k == "pgdn":
            self.move(R)
        elif k == "home":
            self.move(0, 0)
        else:
            self.move(0, len(self.items()) - 1)

    def move(self, d, absolute=None):
        n = len(self.items())
        if n == 0:
            return
        self.sel = max(0, min(n - 1, absolute if absolute is not None else self.sel + d))
        R = max(1, self.list_rows)
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + R:
            self.top = self.sel - R + 1
        self.dirty = True

    def scroll(self, d):
        n, R = len(self.items()), max(1, self.list_rows)
        self.top = max(0, min(max(0, n - R), self.top + d))
        self.sel = max(self.top, min(self.sel, self.top + R - 1, n - 1))
        self.dirty = True

    # ------------------------------------------------------------------- mouse
    def hit_at(self, x, y):
        for hy, a, b, k, g in self.hits:
            if hy == y and a <= x < b:
                return k, g
        return None

    @staticmethod
    def frac(geo, x):
        x0, _, w = geo
        return max(0.0, min(1.0, (x - x0) / max(1, w - 1)))

    def on_mouse(self, b, x, y, press):
        if self.intro:
            self.intro, self.fade = False, 1.0
        now = time.monotonic()
        self.dirty = True
        if self.modal:
            self.modal_mouse(b, x, y, press, now)
            return
        if b & 64:                                                    # wheel
            if not press or self.help:
                return
            d = -1 if (b & 1) == 0 else 1
            if self.list_y0 <= y < self.list_y0 + self.list_rows:
                self.scroll(3 * d)
            else:
                self.set_volume(self.engine.volume - 5 * d)
            return
        if (b & 3) != 0:
            return
        if press and not (b & 32):
            if self.help:
                self.help, self._prev = False, None
                return
            h = self.hit_at(x, y)
            if not h:
                return
            kind, g = h
            self.flash[(kind, g)] = now + 0.18
            if kind in ("nav", "tab"):
                if kind == "nav":
                    self.focus = "nav"
                self.set_nav(g)
            elif kind == "row":
                idx = self.top + g
                if idx < len(self.items()):
                    self.sel, self.focus = idx, "list"
                    if self._last_click[1] == ("row", idx) and now - self._last_click[0] < 0.4:
                        self.activate()
                    self._last_click = (now, ("row", idx))
            elif kind == "btn":
                {"prev": self.prev_track, "play": self.toggle_play, "next": self.next_track, "stop": self.stop}[g]()
            elif kind == "key":
                self.on_key(g)
            elif kind == "mute":
                self.toggle_mute()
            elif kind == "bar":
                if self.cur and self.cur.duration and self.bar_geo:
                    self.drag, self.drag_frac = "bar", self.frac(self.bar_geo, x)
            elif kind == "vol":
                self.drag = "vol"
                if self.vol_geo:
                    self.set_volume(round(self.frac(self.vol_geo, x) * 100), toast=False)
            elif kind == "volm":
                self.set_volume(self.engine.volume - 5)
            elif kind == "volp":
                self.set_volume(self.engine.volume + 5)
        elif press and self.drag:
            if self.drag == "bar" and self.bar_geo:
                self.drag_frac = self.frac(self.bar_geo, x)
            elif self.drag == "vol" and self.vol_geo:
                self.set_volume(round(self.frac(self.vol_geo, x) * 100), toast=False)
        elif not press:
            if self.drag == "bar" and self.drag_frac is not None and self.cur:
                self.apply_seek(self.drag_frac * self.cur.duration)
            self.drag = self.drag_frac = None

    def modal_mouse(self, b, x, y, press, now):
        m = self.modal
        if b & 64:
            if press and m["kind"] in ("theme", "picker"):
                self.modal_key("down" if (b & 1) else "up")
            return
        if not press or (b & 3) != 0 or (b & 32):
            return
        h = self.hit_at(x, y)
        if h and h[0] == "mrow":
            i = h[1]
            if self._last_click[1] == ("m", i) and now - self._last_click[0] < 0.6:
                self.modal_choose(i)
            else:
                m["sel"] = i
                if m["kind"] == "theme":
                    self.theme = themes.THEMES[m["entries"][i]]      # click = preview, click again = apply
            self._last_click = (now, ("m", i))
        elif h and h[0] == "mbtn":
            if h[1] == "yes":
                self.modal = None
                m["on_yes"]()
            else:
                self.close_modal()
        else:
            gx, gy, gw, gh = m.get("geo", (0, 0, 0, 0))
            if not (gx <= x < gx + gw and gy <= y < gy + gh):         # click outside the dialog cancels it
                self.close_modal()

    # ------------------------------------------------------------------- loop
    def next_timeout(self, now):
        e, t = self.engine, 5.0
        if self.intro:
            return 1 / 15
        if self._meta_i < len(self.tracks):
            return 0.005
        if e.playing:
            t = min(0.25, 1.01 - e.position() % 1.0)
            if self.animate:
                t = min(t, (1 + int(now * 8)) / 8 - now + 0.002)
                if now < self.hl_until:
                    t = min(t, 1 / 15)
        if e.device_running and not e.playing:
            t = min(t, 2.1)
        for until in list(self.flash.values()) + [self.toast[1]]:
            if until > now:
                t = min(t, until - now + 0.01)
        return max(0.0, t)

    def loop(self):
        while not self.quit:
            now = time.monotonic()
            if self.intro:
                p = (now - self.t0) / INTRO
                if p >= 1.0:
                    self.intro, self.fade = False, 1.0
                else:
                    self.fade = min(1.0, p * 2.2)
                self.dirty = True
            if self.flash:
                self.flash = {k: v for k, v in self.flash.items() if v > now}
                self.dirty = True
            if self.toast[1] and now > self.toast[1]:
                self.toast, self.dirty = ("", 0.0, "info"), True
            e = self.engine
            e.idle_check()
            if e.finished:
                self.go(lambda: self.q.advance(auto=True))
            if e.playing:
                key = (int(e.position()), int(now * 8) if self.animate else 0)
                if key != self._tick or now < self.hl_until:
                    self._tick, self.dirty = key, True
            if self.dirty:
                self.dirty = False
                self.render()
            evs = self.term.wait(self.next_timeout(time.monotonic()))
            for ev in evs:
                if ev[0] == "key":
                    self.on_key(ev[1])
                elif ev[0] == "mouse":
                    self.on_mouse(*ev[1:])
                elif ev[0] == "resize":
                    self._prev, self.dirty = None, True
                elif ev[0] == "eof":
                    self.quit = True
            if self._pending_seek is not None:
                tgt, self._pending_seek = self._pending_seek, None
                self.apply_seek(tgt)
            if not evs and self._meta_i < len(self.tracks):
                self.load_some()

    def load_some(self):
        end, n = time.monotonic() + 0.02, len(self.tracks)
        while self._meta_i < n and time.monotonic() < end:
            t = self.tracks[self._meta_i]
            self._meta_i += 1
            if not t.loaded:
                t.load_meta()
        if self._meta_i >= n:
            self._sorted = None
            self.total_dur = sum(t.duration for t in self.tracks)
            if SORTS[self.sort] != "path":
                self._items = None
        if self.query:
            self._items = None
        self.dirty = True
