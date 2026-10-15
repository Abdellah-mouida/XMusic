# Contributing to XMusic

Thanks for helping! XMusic's goals are **reliable playback first**, then low resource use, then polish.

## Setup
```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

## Before opening a PR
```bash
./tests/make_test_music.sh /tmp/Music          # needs ffmpeg; also create a clean 6-file /tmp/Music2 (see README > Testing)
./venv/bin/python tests/test_core.py           # pure logic: queue, shuffle, playlists, config, themes, paths
./venv/bin/python tests/test_platform.py       # cross-platform static/simulated checks
./venv/bin/python tests/test_engine.py /tmp/Music
./venv/bin/python tests/test_pty.py /tmp/Music /tmp/Music2    # end-to-end in a pseudo-terminal (Linux/macOS)
```

## Ground rules
* **Never reintroduce the miniaudio callback bug**: the generator passed to `PlaybackDevice.start()` must be
  primed with `next()` first (see `audio.py`). Keep the audio callback free of I/O, locking and terminal code.
* Colours come from `themes.py` roles only - no hex literals in drawing code.
* New themes: add a `_make(...)` entry in `themes.py`; `tests/test_core.py` checks that every role is defined.
* Keep dependencies at zero beyond `miniaudio` and `mutagen`.
* Don't claim a platform works unless you ran it there. Report what you tested in the PR.
* No licence file is included yet - the maintainer must choose one before external contributions are merged.
