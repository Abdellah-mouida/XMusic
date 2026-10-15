"""Cross-platform checks that do NOT need macOS/Windows: shared input parser, simulated-OS behaviour, static scans.
These are static/simulated validations, not substitutes for running on those systems."""
import ast, importlib, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RES = []
def check(c, m): RES.append(bool(c)); print(("PASS  " if c else "FAIL  ") + m)
SRC = sorted((ROOT / "xmusic_core").glob("*.py")) + [ROOT / "xmusic.py"]

# ---- every module parses; Windows backend imports on any OS (ctypes only touched inside start())
for f in SRC: ast.parse(f.read_text(encoding="utf-8"), str(f))
check(True, "all %d source files parse" % len(SRC))
tw = importlib.import_module("xmusic_core.term_win")
check(hasattr(tw.WinTerminal(), "wait") and tw.WinTerminal().size == (80, 24), "Windows backend module imports on non-Windows and can be constructed")

# ---- shared escape-sequence parser (used by POSIX and Windows backends)
from xmusic_core.term import parse_input
ev, rest = parse_input("a\x1b[A\x1b[B\x1b[C\x1b[D \r\t\x7f\x1b[5~\x1b[6~\x1b[3~\x1b[15~\x1bOH\x1b[Z")
check([e[1] for e in ev] == ["a", "up", "down", "right", "left", "space", "enter", "tab", "backspace", "pgup", "pgdn", "delete", "f5", "home", "backtab"] and rest == "", "keys: letters, arrows, space, enter, tab, backspace, PgUp/PgDn, Delete, F5, Home, Shift+Tab")
ev, rest = parse_input("\x1b[<0;10;5M\x1b[<0;10;5m\x1b[<64;3;4M\x1b[<32;11;6M")
check(ev == [("mouse", 0, 9, 4, True), ("mouse", 0, 9, 4, False), ("mouse", 64, 2, 3, True), ("mouse", 32, 10, 5, True)], "SGR mouse: press, release, wheel, drag (0-based coordinates)")
ev, rest = parse_input("x\x1b[<0;10"); check(ev == [("key", "x")] and rest == "\x1b[<0;10", "incomplete mouse sequence is kept for the next read")
ev, rest = parse_input("\x1b"); check(ev == [("key", "esc")], "lone ESC is the Escape key")
ev, rest = parse_input("é日\U0001F3B5"); check([e[1] for e in ev] == ["é", "日", "\U0001F3B5"], "UTF-8 text input (accents, CJK, emoji)")
ev, rest = parse_input("\x1b[1;5Z\x1bx"); check(not any(e[0] == "mouse" for e in ev), "unknown / Alt sequences are ignored safely")

# ---- simulated operating systems
from xmusic_core import audio, themes, paths
def as_platform(plat, fn, **env):
    old, oe = sys.platform, dict(os.environ); sys.platform = plat
    for k in list(os.environ):
        if k in ("COLORTERM", "TERM", "TERM_PROGRAM", "WT_SESSION", "VTE_VERSION", "NO_COLOR", "XMUSIC_HOME", "KITTY_WINDOW_ID", "WEZTERM_EXECUTABLE"): del os.environ[k]
    os.environ.update(env)
    try: return fn()
    finally: sys.platform = old; os.environ.clear(); os.environ.update(oe)
check(as_platform("win32", audio.backend_names) == ("WASAPI", "DSOUND", "WINMM"), "Windows audio backends: WASAPI, DirectSound, WinMM")
check(as_platform("darwin", audio.backend_names) == ("COREAUDIO",), "macOS audio backend: CoreAudio")
lb = as_platform("linux", audio.backend_names); check(lb[0] == "PULSEAUDIO" and "ALSA" in lb and "NULL" not in lb, "Linux audio backends: PulseAudio (PipeWire-compatible), ALSA, JACK ...")
import miniaudio
check(all(hasattr(miniaudio.Backend, n) for p in ("win32", "darwin", "linux") for n in as_platform(p, audio.backend_names)), "every backend name exists in the installed miniaudio")
check(as_platform("win32", themes.detect_depth) == 24 and as_platform("darwin", themes.detect_depth, TERM="xterm-256color", TERM_PROGRAM="Apple_Terminal") == 8
      and as_platform("darwin", themes.detect_depth, TERM="xterm-256color", COLORTERM="truecolor", TERM_PROGRAM="iTerm.app") == 24, "colour depth: Windows 24-bit, Terminal.app 256, iTerm2 truecolor")
from xmusic_core.term import make_terminal
def mk(): return type(make_terminal()).__name__
check(as_platform("win32", mk) == "WinTerminal" and as_platform("linux", mk) == "Terminal" and as_platform("darwin", mk) == "Terminal", "terminal backend chosen per platform (WinTerminal on win32, termios backend on Linux/macOS)")
check(as_platform("win32", lambda: str(paths.config_dir()), APPDATA=r"C:\Users\A\AppData\Roaming").replace("\\", "/").endswith("AppData/Roaming/XMusic") or "XMusic" in as_platform("win32", lambda: str(paths.config_dir()), APPDATA=r"C:\Users\A\AppData\Roaming"), "Windows config directory resolves under %APPDATA%")

# ---- the app can be constructed (no terminal needed) with each backend selected
from xmusic_core.config import Settings, State
from xmusic_core.playlists import Playlists
def build():
    d = Path(tempfile.mkdtemp()); from xmusic_core.app import App
    a = App(str(d), Settings(d).load(), State(d), Playlists(d), animate=False, null_audio=True)
    a.rescan(); return type(a.term).__name__
check(as_platform("win32", build) == "WinTerminal" and as_platform("darwin", build) == "Terminal", "App constructs and scans with the Windows and macOS backends selected")

# ---- static scans for portability problems
HARD = re.compile(r"""["'](/home/|/tmp/|/usr/|/etc/|/var/|/Users/|C:\\)""")
offenders = [f.name for f in SRC if HARD.search(f.read_text(encoding="utf-8"))]
check(not offenders, "no hardcoded OS paths in source %s" % offenders)
bad_calls = []
for f in SRC:
    t = ast.parse(f.read_text(encoding="utf-8"))
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("system", "popen", "Popen", "run", "call", "check_output"):
            if isinstance(n.func.value, ast.Name) and n.func.value.id in ("os", "subprocess"): bad_calls.append("%s:%d" % (f.name, n.lineno))
check(not bad_calls, "no shell/subprocess calls in the application %s" % bad_calls)
PLAT_ONLY = {"termios", "tty", "fcntl", "select", "msvcrt", "signal", "ctypes"}
top = []
for f in SRC:
    if f.name == "term_win.py": continue
    for n in ast.parse(f.read_text(encoding="utf-8")).body:
        mods = [a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import) else [(n.module or "").split(".")[0]] if isinstance(n, ast.ImportFrom) and n.level == 0 else []
        top += ["%s imports %s" % (f.name, m) for m in mods if m in PLAT_ONLY]
check(not top, "no module-level POSIX-only imports outside the platform backends %s" % top)
tsrc = (ROOT / "xmusic_core/term.py").read_text()
check('hasattr(signal, "SIGWINCH")' in tsrc and "signal.SIGTERM" not in tsrc and "signal.SIGHUP" not in tsrc, "POSIX-only signals (SIGWINCH/SIGHUP) are looked up defensively")
# every non-ASCII glyph the UI draws has an ASCII fallback
from xmusic_core.ui import ASCII_MAP
glyphs = set()
for name in ("render.py", "app.py", "logo.py", "ui.py"):
    t = ast.parse((ROOT / "xmusic_core" / name).read_text(encoding="utf-8"))
    doc = {id(b[0].value) for b in [n.body for n in ast.walk(t) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))] if b and isinstance(b[0], ast.Expr)}
    for n in ast.walk(t):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc and name != "ui.py":
            glyphs |= {c for c in n.value if ord(c) > 126}
glyphs -= {chr(0xA0), chr(0xFFFF)}
missing = sorted(c for c in glyphs if ord(c) not in ASCII_MAP)
check(not missing, "every non-ASCII UI glyph has an ASCII fallback (missing: %s)" % "".join(missing))
check(all(len(v) == 1 if isinstance(v, str) else True for v in ASCII_MAP.values()), "ASCII fallbacks are width-preserving (1 char each)")
print("\n%d/%d platform checks passed" % (sum(RES), len(RES))); sys.exit(0 if all(RES) else 1)
