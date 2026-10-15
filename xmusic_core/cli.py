"""Command line entry point (used by xmusic.py, `python -m xmusic_core` and the `xmusic` console script)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__, paths, themes
from .config import Settings, State
from .playlists import Playlists

EPILOG = """settings precedence: command line > saved settings (config.json) > defaults.
  --music-dir is remembered for next time; --theme and --no-animation apply to this launch only
  (change them permanently from inside the app: t = theme, z = animations).
themes: """ + ", ".join(themes.theme_ids())


def _first_run_dir(default: Path) -> Path | None:
    """No usable music directory: ask once (only possible on an interactive terminal)."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    print("XMusic: your music folder (%s) doesn't exist." % default)
    try:
        ans = input("Enter the path to your music folder (or press Enter to quit): ").strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        return None
    p = Path(ans).expanduser() if ans else None
    return p if p and p.is_dir() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xmusic", description="XMusic - lightweight terminal MP3 player with themes, "
                                 "queue, playlists, shuffle/repeat and mouse support.", epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--music-dir", "-d", metavar="DIR", help="music directory (default: last used, else ~/Music)")
    ap.add_argument("--theme", metavar="ID", help="colour theme for this launch: " + ", ".join(themes.theme_ids()))
    ap.add_argument("--no-animation", action="store_true", help="disable the intro, equalizer and transition effects")
    ap.add_argument("--ascii", action="store_true", help="use plain ASCII instead of box-drawing/block characters")
    ap.add_argument("--null-audio", action="store_true", help=argparse.SUPPRESS)   # silent backend for tests
    ap.add_argument("--version", action="version", version="XMusic " + __version__)
    args = ap.parse_args(argv)

    theme_id = None
    if args.theme:
        theme_id = themes.resolve(args.theme)
        if theme_id is None:
            ap.error("unknown theme %r (choose from: %s)" % (args.theme, ", ".join(themes.theme_ids())))

    settings = Settings().load()
    if args.music_dir:
        root = Path(args.music_dir).expanduser()
    else:
        last = settings["music_dir"]
        root = Path(last) if last and Path(last).is_dir() else paths.default_music_dir()
    if not root.is_dir():
        if args.music_dir:
            sys.stderr.write("xmusic: music directory not found: %s\nChoose another with:  xmusic --music-dir PATH\n" % root)
            return 2
        picked = _first_run_dir(root)
        if picked is None:
            sys.stderr.write("xmusic: no music directory. Run:  xmusic --music-dir PATH\n")
            return 2
        root = picked
    root = root.resolve()

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.stderr.write("xmusic: needs an interactive terminal (stdin/stdout must be a TTY).\n")
        return 2

    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    ascii_mode = args.ascii or bool(os.environ.get("XMUSIC_ASCII")) or (sys.platform != "win32" and "utf" not in enc)

    playlists = Playlists().load()
    playlists.import_legacy(settings.legacy.get("playlists"))
    state = State().load()
    if not state.recent and isinstance(settings.legacy.get("recent"), list):
        state.recent = [p for p in settings.legacy["recent"] if isinstance(p, str)][:50]

    from .app import App
    try:
        app = App(str(root), settings, state, playlists, animate=settings["animation"] and not args.no_animation,
                  null_audio=args.null_audio, ascii_mode=ascii_mode, theme_id=theme_id)
        app.run()
    except KeyboardInterrupt:
        pass
    except OSError as e:                                    # e.g. console without VT support on old Windows
        sys.stderr.write("xmusic: %s\n" % e)
        return 1
    return 0
