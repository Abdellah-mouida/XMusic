"""Playback queue with shuffle and repeat. Pure logic (no I/O) so it is fully unit-testable.

Model
-----
* ``items``  - the queue in its natural order; each entry is a unique ``QItem`` (a track may be queued twice).
* ``order``  - the play order while shuffle is ON (a permutation of ``items``), else ``None``.
* ``cur``    - the current ``QItem`` (may be None).  Queue edits never change ``cur``, so they can never
               interrupt audio that is already playing.
* ``hist``   - bounded stack of previously played items, so Previous behaves predictably under shuffle.

Shuffle is a real permutation (every track once per cycle, current track first); when a cycle ends
with Repeat All the queue is reshuffled and the first track is never the one that just played.
"""
from __future__ import annotations

import random

HIST_MAX = 200


class QItem:
    __slots__ = ("track",)

    def __init__(self, track):
        self.track = track


class PlayQueue:
    def __init__(self, rng: random.Random | None = None):
        self.items: list[QItem] = []
        self.order: list[QItem] | None = None
        self.cur: QItem | None = None
        self.hist: list[QItem] = []
        self.shuffle = False
        self.repeat = "off"                       # off | all | one
        self.rng = rng or random.Random()

    # ----------------------------------------------------------------- views
    @property
    def seq(self) -> list[QItem]:
        """Items in the order they will be played."""
        return self.order if self.order is not None else self.items

    def pos(self) -> int:
        c = self.cur
        for i, x in enumerate(self.seq):
            if x is c:
                return i
        return -1

    def upcoming(self) -> list[QItem]:
        i = self.pos()
        return self.seq[i + 1:] if i >= 0 else list(self.seq)

    # ------------------------------------------------------------- shuffling
    def _reshuffle(self, keep: QItem | None = None, avoid: QItem | None = None):
        if keep is not None:
            rest = [x for x in self.items if x is not keep]
            self.rng.shuffle(rest)
            self.order = [keep] + rest
        else:
            self.order = self.items[:]
            self.rng.shuffle(self.order)
            if avoid is not None and len(self.order) > 1 and self.order[0] is avoid:
                j = self.rng.randrange(1, len(self.order))
                self.order[0], self.order[j] = self.order[j], self.order[0]

    def set_shuffle(self, on: bool):
        self.shuffle = bool(on)
        if self.shuffle:
            self._reshuffle(keep=self.cur)
        else:
            self.order = None

    def set_repeat(self, mode: str):
        self.repeat = mode if mode in ("off", "all", "one") else "off"

    # --------------------------------------------------------------- loading
    def set_tracks(self, tracks, start: int = 0) -> QItem | None:
        """Replace the queue (e.g. when the user plays a track from a list). Returns the new current item."""
        self.items = [QItem(t) for t in tracks]
        self.hist.clear()
        self.cur = self.items[start] if 0 <= start < len(self.items) else None
        self.order = None
        if self.shuffle:
            self._reshuffle(keep=self.cur)
        return self.cur

    # ------------------------------------------------------------ navigation
    def _commit(self, it: QItem) -> QItem:
        c = self.cur
        if c is not None and c is not it and not c.track.bad:
            self.hist.append(c)
            del self.hist[:-HIST_MAX]
        self.cur = it
        return it

    def advance(self, auto: bool = False) -> QItem | None:
        """Move to the next item and return it, or None when the queue has ended (repeat off).
        ``auto`` = natural end of track (Repeat One replays; a manual Next skips ahead)."""
        seq, c = self.seq, self.cur
        if not seq:
            return None
        if c is None:
            return self._commit(seq[0])
        if auto and self.repeat == "one" and not c.track.bad:
            return c
        i = self.pos()
        if 0 <= i + 1 < len(seq):
            return self._commit(seq[i + 1])
        if self.repeat == "off":
            return None
        if self.order is not None:                # Repeat All + shuffle: new cycle, never an immediate repeat
            self._reshuffle(avoid=c)
            nxt = self.order[0]
        else:
            nxt = self.items[0]
        return self._commit(nxt)

    def retreat(self) -> QItem | None:
        """Previous item (via history first); None means 'nothing earlier - restart the current track'."""
        while self.hist:
            it = self.hist.pop()
            if any(x is it for x in self.items):
                self.cur = it
                return it
        i = self.pos()
        if self.order is None and self.items:
            if i > 0:
                self.cur = self.items[i - 1]
                return self.cur
            if self.repeat == "all" and len(self.items) > 1:
                self.cur = self.items[-1]
                return self.cur
        return None

    def jump(self, it: QItem) -> QItem:
        return self._commit(it)

    # ------------------------------------------------------------ queue edits
    def enqueue(self, track, play_next: bool = False) -> QItem:
        """Append to the queue (or insert right after the current item). Never touches ``cur``."""
        it = QItem(track)
        for lst in (self.items, self.order):
            if lst is None:
                continue
            at = len(lst)
            if play_next and self.cur is not None:
                at = next((k + 1 for k, x in enumerate(lst) if x is self.cur), len(lst))
            lst.insert(at, it)
        if self.cur is None and len(self.items) == 1:
            pass                                  # nothing playing: first queued item stays 'upcoming'
        return it

    def remove(self, it: QItem) -> bool:
        """Remove a queued item. The currently playing item can't be removed (would interrupt audio)."""
        if it is self.cur:
            return False
        self.items = [x for x in self.items if x is not it]
        if self.order is not None:
            self.order = [x for x in self.order if x is not it]
        self.hist = [x for x in self.hist if x is not it]
        return True

    def clear(self):
        """Drop everything except the item that is currently playing."""
        keep = [self.cur] if self.cur is not None else []
        self.items = keep[:]
        self.order = keep[:] if self.order is not None else None
        self.hist.clear()

    def move(self, it: QItem, delta: int) -> bool:
        lst = self.seq
        for i, x in enumerate(lst):
            if x is it:
                j = i + delta
                if 0 <= j < len(lst):
                    lst[i], lst[j] = lst[j], lst[i]
                    return True
                return False
        return False

    def __len__(self):
        return len(self.items)
