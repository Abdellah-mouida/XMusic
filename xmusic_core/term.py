"""Terminal I/O: alt screen, SGR mouse, key/mouse parsing, guaranteed restore.

`parse_input` is platform independent (and unit-tested).  `Terminal` is the POSIX backend
(Linux/macOS); Windows uses `term_win.WinTerminal` which feeds the same parser.
"""
from __future__ import annotations

import sys

# ?7l  autowrap off | ?1049h alt screen | ?25l hide cursor | ?1000/1002/1006 mouse (clicks, drag, SGR encoding)
ENTER = "\x1b[?7l\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1002h\x1b[?1006h"
LEAVE = "\x1b[?7h\x1b[?1006l\x1b[?1002l\x1b[?1000l\x1b[?25h\x1b[0m\x1b[?1049l"

_KEYS = {
    "[A": "up", "[B": "down", "[C": "right", "[D": "left", "OA": "up", "OB": "down", "OC": "right", "OD": "left",
    "[H": "home", "[F": "end", "OH": "home", "OF": "end", "[1~": "home", "[4~": "end", "[7~": "home", "[8~": "end",
    "[5~": "pgup", "[6~": "pgdn", "[Z": "backtab", "[3~": "delete", "[15~": "f5", "OT": "f5",
}


def parse_input(s: str):
    """Parse a text buffer into events. Returns (events, unconsumed_rest).
    Events: ("key", name) | ("mouse", button, x, y, pressed)   (x, y are 0-based)."""
    i, out, n = 0, [], len(s)
    while i < n:
        ch = s[i]
        if ch != "\x1b":
            i += 1
            if ch in "\r\n":
                out.append(("key", "enter"))
            elif ch == "\t":
                out.append(("key", "tab"))
            elif ch in "\x7f\x08":
                out.append(("key", "backspace"))
            elif ch == "\x03":
                out.append(("key", "ctrl-c"))
            elif ch == " ":
                out.append(("key", "space"))
            elif ch >= " ":
                out.append(("key", ch))
            continue
        if i + 1 >= n:                                   # lone ESC
            out.append(("key", "esc"))
            i += 1
            continue
        if s.startswith("[<", i + 1):                    # SGR mouse: ESC [ < b ; x ; y (M|m)
            j = i + 3
            while j < n and s[j] not in "Mm":
                j += 1
            if j >= n:
                break                                    # incomplete - wait for more bytes
            try:
                b, x, y = (int(v) for v in s[i + 3:j].split(";"))
                out.append(("mouse", b, x - 1, y - 1, s[j] == "M"))
            except ValueError:
                pass
            i = j + 1
            continue
        if s[i + 1] in "[O":                             # CSI / SS3
            j = i + 2
            while j < n and not (s[j].isalpha() or s[j] == "~"):
                j += 1
            if j >= n:
                break
            k = _KEYS.get(s[i + 1:j + 1])
            if k:
                out.append(("key", k))
            i = j + 1
            continue
        i += 2                                           # Alt+key etc: ignored
    return out, s[i:]


def write_all(fd: int, s: str):
    import os
    import select
    data = s.encode("utf-8", "replace")
    while data:
        try:
            n = os.write(fd, data)
        except BlockingIOError:
            select.select([], [fd], [], 0.05)
            continue
        data = data[n:]


class Terminal:
    """POSIX backend (Linux, macOS)."""
    caps_note = ""

    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.active = False
        self._old = None
        self._buf = ""
        self._wake_r = self._wake_w = None
        self.size = (80, 24)

    def start(self):
        import atexit
        import os
        import signal
        import termios
        import tty
        self._old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        a = termios.tcgetattr(self.fd)
        a[0] &= ~(termios.IXON | termios.ICRNL)          # no Ctrl-S freeze, CR stays CR
        termios.tcsetattr(self.fd, termios.TCSADRAIN, a)
        self._wake_r, self._wake_w = os.pipe()
        os.set_blocking(self._wake_r, False)
        os.set_blocking(self._wake_w, False)
        signal.set_wakeup_fd(self._wake_w)
        if hasattr(signal, "SIGWINCH"):
            signal.signal(signal.SIGWINCH, lambda *_: None)   # wakes select() through the wakeup fd
        for name in ("SIGTERM", "SIGHUP"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), lambda *_: sys.exit(0))
        self.active = True
        atexit.register(self.stop)
        self.write(ENTER)
        self.refresh_size()

    def stop(self):
        if not self.active:
            return
        import os
        import signal
        import termios
        self.active = False
        try:
            self.write(LEAVE)
        except Exception:
            pass
        try:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._old)
        except Exception:
            pass
        try:
            signal.set_wakeup_fd(-1)
            os.close(self._wake_r)
            os.close(self._wake_w)
        except Exception:
            pass

    def write(self, s: str):
        write_all(sys.stdout.fileno(), s)

    def refresh_size(self):
        import os
        try:
            c, r = os.get_terminal_size(sys.stdout.fileno())
            self.size = (c or 80, r or 24)
        except OSError:
            pass
        return self.size

    def wait(self, timeout):
        """Block until input / resize / timeout. Returns a list of events."""
        import os
        import select
        try:
            ready, _, _ = select.select([self.fd, self._wake_r], [], [], timeout)
        except InterruptedError:
            ready = []
        evs = []
        if self._wake_r in ready:
            try:
                os.read(self._wake_r, 256)
            except OSError:
                pass
            old = self.size
            if self.refresh_size() != old:
                evs.append(("resize",))
        if self.fd in ready:
            try:
                data = os.read(self.fd, 4096)
            except OSError:
                data = b""
            if not data:
                return [("eof",)]
            self._buf += data.decode("utf-8", "ignore")
            parsed, self._buf = parse_input(self._buf)
            evs.extend(parsed)
        return evs


def make_terminal():
    if sys.platform == "win32":
        from .term_win import WinTerminal
        return WinTerminal()
    return Terminal()
