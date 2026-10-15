"""Windows console backend (Windows 10 1809+ / Windows Terminal): VT input + output via the Win32 console API.

NOTE: written against the documented Win32 API and checked statically; it has NOT been run on a real
Windows machine by the author.  See README "Platform status".
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

from .term import ENTER, LEAVE, parse_input, write_all

STD_INPUT, STD_OUTPUT = -10, -11
IN_PROCESSED, IN_LINE, IN_ECHO, IN_MOUSE, IN_QUICKEDIT, IN_EXTENDED, IN_VT = 0x1, 0x2, 0x4, 0x10, 0x40, 0x80, 0x200
OUT_PROCESSED, OUT_VT, OUT_NO_NL = 0x1, 0x4, 0x8
KEY_EVENT, WINDOW_BUFFER_SIZE_EVENT = 0x1, 0x4
CP_UTF8 = 65001


class _KeyEvent(ctypes.Structure):
    _fields_ = [("bKeyDown", wintypes.BOOL), ("wRepeatCount", wintypes.WORD), ("wVirtualKeyCode", wintypes.WORD),
                ("wVirtualScanCode", wintypes.WORD), ("uChar", ctypes.c_wchar), ("dwControlKeyState", wintypes.DWORD)]


class _Event(ctypes.Union):
    _fields_ = [("KeyEvent", _KeyEvent), ("_pad", ctypes.c_byte * 16)]


class _InputRecord(ctypes.Structure):
    _fields_ = [("EventType", wintypes.WORD), ("Event", _Event)]


class WinTerminal:
    caps_note = "Windows console"

    def __init__(self):
        self.active = False
        self.size = (80, 24)
        self._buf = ""
        self._k32 = None
        self._hin = self._hout = None
        self._old_in = self._old_out = None
        self._old_cp = None

    def start(self):
        k = self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k.GetStdHandle.restype = wintypes.HANDLE
        self._hin, self._hout = k.GetStdHandle(STD_INPUT), k.GetStdHandle(STD_OUTPUT)
        mi, mo = wintypes.DWORD(), wintypes.DWORD()
        if not k.GetConsoleMode(self._hin, ctypes.byref(mi)) or not k.GetConsoleMode(self._hout, ctypes.byref(mo)):
            raise OSError("stdin/stdout must be a Windows console (use Windows Terminal or PowerShell)")
        self._old_in, self._old_out = mi.value, mo.value
        out_mode = mo.value | OUT_PROCESSED | OUT_VT | OUT_NO_NL
        if not k.SetConsoleMode(self._hout, out_mode):
            raise OSError("this console does not support ANSI/VT sequences; use Windows Terminal or Windows 10 1809+")
        in_mode = (mi.value | IN_VT | IN_EXTENDED) & ~(IN_LINE | IN_ECHO | IN_PROCESSED | IN_QUICKEDIT)
        k.SetConsoleMode(self._hin, in_mode)
        self._old_cp = k.GetConsoleOutputCP()
        k.SetConsoleOutputCP(CP_UTF8)
        self.active = True
        self.write(ENTER)
        self.refresh_size()

    def stop(self):
        if not self.active:
            return
        self.active = False
        try:
            self.write(LEAVE)
            k = self._k32
            k.SetConsoleMode(self._hin, self._old_in)
            k.SetConsoleMode(self._hout, self._old_out)
            if self._old_cp:
                k.SetConsoleOutputCP(self._old_cp)
        except Exception:
            pass

    def write(self, s: str):
        write_all(sys.stdout.fileno(), s)

    def refresh_size(self):
        try:
            c, r = os.get_terminal_size(sys.stdout.fileno())
            self.size = (c or 80, r or 24)
        except OSError:
            pass
        return self.size

    def _read_chars(self) -> str:
        k, chars = self._k32, []
        n = wintypes.DWORD()
        if not k.GetNumberOfConsoleInputEvents(self._hin, ctypes.byref(n)) or n.value == 0:
            return ""
        buf = (_InputRecord * min(n.value, 256))()
        got = wintypes.DWORD()
        if not k.ReadConsoleInputW(self._hin, buf, len(buf), ctypes.byref(got)):
            return ""
        for i in range(got.value):
            r = buf[i]
            if r.EventType == KEY_EVENT and r.Event.KeyEvent.bKeyDown and r.Event.KeyEvent.uChar != "\x00":
                chars.append(r.Event.KeyEvent.uChar * max(1, r.Event.KeyEvent.wRepeatCount))
        s = "".join(chars)
        try:                                              # re-join UTF-16 surrogate pairs
            s = s.encode("utf-16", "surrogatepass").decode("utf-16")
        except UnicodeError:
            pass
        return s

    def wait(self, timeout):
        """Event-driven wait on the console input handle; wakes at least every 250 ms to notice resizes
        (Windows has no SIGWINCH)."""
        end = None if timeout is None else time.monotonic() + timeout
        while True:
            slice_ms = 250 if end is None else max(0, min(250, int((end - time.monotonic()) * 1000)))
            if self._k32.WaitForSingleObject(self._hin, slice_ms) == 0:
                text = self._read_chars()
                if text:
                    self._buf += text
                    evs, self._buf = parse_input(self._buf)
                    if evs:
                        return evs
            old = self.size
            if self.refresh_size() != old:
                return [("resize",)]
            if end is not None and time.monotonic() >= end:
                return []
