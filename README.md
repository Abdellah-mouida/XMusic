<div align="center">

<pre>
██╗  ██╗ ███╗   ███╗  ██╗   ██╗  ███████╗  ██╗   ██████╗
╚██╗██╔╝ ████╗ ████║  ██║   ██║  ██╔════╝  ██║  ██╔════╝
 ╚███╔╝  ██╔████╔██║  ██║   ██║  ███████╗  ██║  ██║     
 ██╔██╗  ██║╚██╔╝██║  ██║   ██║  ╚════██║  ██║  ██║     
██╔╝ ██╗ ██║ ╚═╝ ██║  ╚██████╔╝  ███████║  ██║  ╚██████╗
╚═╝  ╚═╝ ╚═╝     ╚═╝   ╚═════╝   ╚══════╝  ╚═╝   ╚═════╝
</pre>                                              


# XMusic

### Terminal-native music. Minimal footprint. Maximum atmosphere.

A lightweight, hacker-styled **MP3 player for your terminal** — with vivid themes, interactive controls, playlists, and a dedicated Kali-inspired console.

<p>
  <img src="https://img.shields.io/badge/Version-2.0.0-367BF5?style=for-the-badge" alt="Version 2.0.0" />
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/Interface-Terminal-111827?style=for-the-badge" alt="Terminal interface" />
  <img src="https://img.shields.io/badge/Audio-MP3-8B5CF6?style=for-the-badge" alt="MP3 audio" />
  <img src="https://img.shields.io/badge/Platforms-Linux%20%7C%20macOS%20%7C%20Windows-16A085?style=for-the-badge" alt="Linux, macOS and Windows" />
</p>

**Made by [Abdellah Mouida](https://github.com/Abdellah-mouida)**

[Features](#-features) · [Kali console](#-kali-console) · [Themes](#-themes) · [Installation](#-installation) · [Controls](#-keyboard--mouse-controls)

</div>

---

## ✦ What is XMusic?

XMusic brings your local music library into a fast, keyboard-friendly terminal interface. It is built with Python, uses streamed audio decoding, and keeps the interface deliberately lightweight.

- **No browser, web server, or telemetry.**
- **No heavyweight GUI** — just your terminal.
- **Eight dark themes**, including AMOLED palettes and a Kali-inspired blue/cyan style.
- **Persistent queue and playlists**, with shuffle, repeat, search, and folder browsing.
- **Mouse and keyboard support**, with clickable controls and draggable progress/volume bars.
- **Peak-safe playback path** with a fast-attack limiter for unusually hot audio.

## ⚡ Features

| Area | What you get |
|:--|:--|
| <span style="color:#60A5FA">**Playback**</span> | Play, pause, stop, next/previous, seek, volume, mute, automatic next track, streamed decoding |
| <span style="color:#A78BFA">**Queue**</span> | Add to end, play next, remove, reorder, clear without interrupting the current track |
| <span style="color:#F472B6">**Playlists**</span> | Create, rename, delete, add/remove tracks, play playlists, persistent JSON storage |
| <span style="color:#34D399">**Library**</span> | Recursive scanning, folder browser, search by title/artist/album/filename, sorting, recently played |
| <span style="color:#FBBF24">**Themes**</span> | Eight palettes, live theme preview, saved preferences, theme launch option |
| <span style="color:#22D3EE">**Interface**</span> | Clickable navigation, double-click playback, wheel scrolling, drag-to-seek and drag-to-adjust volume |
| <span style="color:#4ADE80">**Motion**</span> | Logo reveal, equalizer, track-change highlight, Kali Matrix rain and animated logo colours |

## 🐉 Kali console

Launch the dedicated Kali-inspired interface:

~~~bash
xmusic --kali --music-dir ~/Music
~~~

The Kali console gets its own composition rather than merely recolouring the standard screen:

- **Dual-logo header:** the full-size Kali dragon beside the original XMusic block logo enlarged proportionally by 3×.
- **Author signature:** <code>Made by Abdellah Mouida</code> directly beneath the XMusic mark.
- **Blue Matrix rain:** animated blue characters flow behind the logos, leaving the lettering crisp.
- **Colour motion:** a blue-to-cyan wave moves across both marks.
- **Split lower deck:** a dedicated **PLAYER** pane beside the **PLAYLIST / ARCHIVE** pane.
- **Preserved artwork:** the original XMusic glyphs are repeated evenly in both directions — no redraw, distortion, or cropping.

<blockquote>
  <strong>Terminal size:</strong> the full dual-logo header requires at least <code>216 columns × 26 rows</code>. Increase the terminal size to see the complete layout.
</blockquote>

Animations are enabled by default. Press <code>z</code> to toggle them during a session, or launch with <code>--no-animation</code> to disable the intro, Matrix effect, equalizer, and other motion.

The Kali palette can also be used without changing the regular XMusic layout:

~~~bash
xmusic --theme kali --music-dir ~/Music
~~~

> The Kali-inspired theme is a community styling choice and is not affiliated with or endorsed by Offensive Security.

## 🎨 Themes

Pick a theme with <code>t</code> inside XMusic, or pass <code>--theme ID</code> when launching. The picker previews colours live; press <code>Enter</code> to save or <code>Esc</code> to cancel.

| Theme ID | Look | Accent palette |
|:--|:--|:--|
| <code>amoled-blue</code> **(default)** | Pure black + electric blue | <span style="color:#3D8BFF">●</span> <code>#3D8BFF</code> <span style="color:#60A5FA">●</span> <code>#60A5FA</code> <span style="color:#38BDF8">●</span> <code>#38BDF8</code> |
| <code>amoled-pink</code> | Pure black + neon rose | <span style="color:#FF2E93">●</span> <code>#FF2E93</code> <span style="color:#FF8AC4">●</span> <code>#FF8AC4</code> |
| <code>amoled-orange</code> | Pure black + signal orange | <span style="color:#FF861F">●</span> <code>#FF861F</code> <span style="color:#FFB15C">●</span> <code>#FFB15C</code> |
| <code>kali</code> | AMOLED black + Kali blue/cyan | <span style="color:#367BF5">●</span> <code>#367BF5</code> <span style="color:#00D6C5">●</span> <code>#00D6C5</code> |
| <code>blue</code> | Deep navy + electric blue | <span style="color:#3D8BFF">●</span> <code>#3D8BFF</code> <span style="color:#38BDF8">●</span> <code>#38BDF8</code> |
| <code>girly</code> | Plum + blush pink | <span style="color:#FF78B7">●</span> <code>#FF78B7</code> <span style="color:#F9A8D4">●</span> <code>#F9A8D4</code> |
| <code>yaru</code> | Charcoal + Ubuntu orange | <span style="color:#E95420">●</span> <code>#E95420</code> <span style="color:#FFB86B">●</span> <code>#FFB86B</code> |
| <code>violet</code> | Deep purple + lavender | <span style="color:#8B5CF6">●</span> <code>#8B5CF6</code> <span style="color:#C4B5FD">●</span> <code>#C4B5FD</code> |

Aliases: <code>rose</code>/<code>pink</code> → <code>girly</code>, <code>orange</code>/<code>ubuntu</code> → <code>yaru</code>, <code>amoled</code> → <code>amoled-blue</code>, <code>amoled-amber</code> → <code>amoled-orange</code>, <code>kali-linux</code> → <code>kali</code>, and <code>purple</code> → <code>violet</code>.

## 🚀 Installation

**Requirements:** Python 3.9 or newer. XMusic uses [miniaudio](https://github.com/irmen/pyminiaudio) for decoding/playback and [Mutagen](https://mutagen.readthedocs.io/) for MP3 metadata.

### Linux

~~~bash
git clone https://github.com/Abdellah-mouida/XMusic.git
cd XMusic
./install.sh
xmusic --music-dir ~/Music
~~~

If virtual-environment support is missing:

~~~bash
sudo apt install python3-venv
~~~

Manual setup:

~~~bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python xmusic.py --music-dir ~/Music
~~~

Audio uses PulseAudio (including PipeWire's PulseAudio compatibility layer) or ALSA. XMusic does not modify system audio settings.

### macOS

~~~bash
git clone https://github.com/Abdellah-mouida/XMusic.git
cd XMusic
./install.sh
xmusic --music-dir ~/Music
~~~

If pip needs to compile miniaudio, install the Xcode command-line tools first with <code>xcode-select --install</code>. iTerm2 is recommended.

### Windows 10 / 11

Use Windows Terminal with PowerShell:

~~~powershell
git clone https://github.com/Abdellah-mouida/XMusic.git
cd XMusic
.\install.ps1
xmusic --music-dir "$env:USERPROFILE\Music"
~~~

Manual setup:

~~~powershell
py -3 -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python.exe xmusic.py --music-dir "$env:USERPROFILE\Music"
~~~

### Install with pip

~~~bash
pip install .
xmusic --music-dir ~/Music
~~~

## ▶ Quick start

~~~bash
# Standard XMusic interface
xmusic --music-dir ~/Music

# Kali dragon + Matrix console
xmusic --kali --music-dir ~/Music

# Select a colour palette
xmusic --theme amoled-orange --music-dir ~/Music

# Disable animation effects for this launch
xmusic --no-animation --music-dir ~/Music

# Plain ASCII fallback
xmusic --ascii --music-dir ~/Music
~~~

On first launch, XMusic remembers the selected music folder. Press <code>Enter</code> on a track to start playback and <code>?</code> to open the help screen.

## ⌨ Keyboard & mouse controls

| Key | Action | Key | Action |
|:--|:--|:--|:--|
| <code>Space</code> | Play / pause | <code>/</code> | Search |
| <code>Enter</code> | Play selected / open | <code>o</code> | Cycle sort order |
| <code>x</code> | Stop | <code>Tab</code> | Switch panel focus |
| <code>n</code> / <code>p</code> | Next / previous | <code>1</code>–<code>5</code> | All / folders / queue / playlists / recent |
| <code>←</code> / <code>→</code> | Seek −/+ 5 seconds | <code>F5</code> | Rescan music folder |
| <code>+</code> / <code>-</code> | Volume up / down | <code>m</code> | Mute / unmute |
| <code>s</code> | Shuffle | <code>r</code> | Repeat: off / all / one |
| <code>e</code> / <code>E</code> | Add to queue / play next | <code>d</code> / <code>Del</code> | Remove selected item |
| <code>K</code> / <code>J</code> | Move queue item up / down | <code>c</code> | Clear queue |
| <code>a</code> / <code>A</code> | Toggle Favorites / add to playlist | <code>N</code> / <code>R</code> / <code>D</code> | New / rename / delete playlist |
| <code>t</code> | Theme picker | <code>z</code> | Toggle animations |
| <code>?</code> | Help | <code>Esc</code> | Close / clear |
| <code>q</code> / <code>Ctrl+C</code> | Quit | Mouse | Click, double-click, wheel, drag bars |

Mouse support uses xterm SGR reporting. In tmux, enable it with:

~~~tmux
set -g mouse on
~~~

The keyboard remains fully usable in terminals without mouse support. XMusic respects <code>NO_COLOR</code>, and falls back from truecolor to 256, 16, or no colour depending on terminal capabilities. Use <code>--ascii</code> if your font cannot render the block and box-drawing characters.

## 🎧 Audio & library notes

- **Format enabled:** MP3. Missing tags fall back to the filename.
- **Decoder:** miniaudio streamed decoding; Mutagen reads metadata lazily.
- **Peak limiter:** fast attack with a 30,000 / 32,767 ceiling and 150 ms release.
- **Output buffer:** 180 ms to make playback more tolerant of brief scheduling stalls.
- **No-device behaviour:** if no audio backend opens, browsing still works and the UI reports **NO AUDIO DEVICE** rather than silently pretending to play.

Miniaudio can decode other formats, but WAV/FLAC/Vorbis are not enabled in the library scanner yet.

## ⚙ Configuration

| File | Location |
|:--|:--|
| Settings: <code>config.json</code> | Linux: <code>$XDG_CONFIG_HOME/xmusic</code> or <code>~/.config/xmusic</code>; macOS: <code>~/Library/Application Support/XMusic</code>; Windows: <code>%APPDATA%\XMusic</code> |
| Playlists and state | Linux: <code>$XDG_DATA_HOME/xmusic</code> or <code>~/.local/share/xmusic</code>; macOS/Windows: same folder as config |

Set <code>XMUSIC_HOME</code> to store all configuration and data in one custom directory. A malformed settings file falls back to defaults and is preserved as <code>*.bad</code>. Legacy XMusic 1.x playlist/recent data is imported automatically.

**Settings precedence:** command line → saved settings → defaults. <code>--music-dir</code> is remembered. <code>--theme</code> and <code>--no-animation</code> apply to the current launch; use <code>t</code> and <code>z</code> to change saved preferences interactively.

### Command-line options

~~~text
xmusic [--music-dir DIR] [--theme ID | --kali] [--no-animation] [--ascii] [--version] [--help]
~~~

| Option | Purpose |
|:--|:--|
| <code>--music-dir DIR</code>, <code>-d DIR</code> | Select the music library |
| <code>--theme ID</code> | Launch with one of the eight themes |
| <code>--kali</code> | Launch the dedicated dual-logo Kali console |
| <code>--no-animation</code> | Disable motion effects |
| <code>--ascii</code> | Use plain ASCII characters |
| <code>--version</code> | Print the installed version |

## 🧪 Development & testing

~~~bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Run the pure-logic suite
./venv/bin/python tests/test_core.py

# The remaining suites need a test music library
./tests/make_test_music.sh /tmp/Music
./venv/bin/python tests/test_engine.py /tmp/Music
./venv/bin/python tests/test_pty.py /tmp/Music /tmp/Music2
./venv/bin/python tests/test_platform.py
~~~

The test music generator requires ffmpeg. The engine suite uses miniaudio's null backend: it checks decoding, timing, state, and UI behaviour, not audible output.

### Project structure

~~~text
xmusic.py               CLI launcher
pyproject.toml           package metadata and console entry point
install.sh / install.ps1 platform installers
xmusic_core/
  app.py                 application state, playback, input and event loop
  render.py              terminal rendering, panels, logos and animation
  themes.py              palettes, colour-depth detection and NO_COLOR
  logo.py                XMusic wordmark and original Kali dragon art
  audio.py               streaming audio engine and peak limiter
  library.py             MP3 scanning and lazy metadata loading
  playqueue.py           queue, shuffle and repeat logic
  playlists.py            persistent playlist data
  config.py              settings and state persistence
  term.py / term_win.py  POSIX and Windows terminal backends
tests/                   pure-logic, engine, platform and pseudo-terminal tests
~~~

## 🖥 Platform status

| Platform | Status |
|:--|:--|
| **Linux** | Main development platform; the documented baseline was measured in a Linux sandbox. Audible output depends on the host audio device/backend. |
| **macOS** | Not runtime-tested; shares the POSIX terminal implementation. |
| **Windows 10 / 11** | Not runtime-tested; uses a separate console backend. Windows 10 version 1809+ with VT support is required. |

Miniaudio may compile from source on systems without a matching wheel. A C compiler and Python development headers may be required, especially on less common architectures or newer Python versions.

## 📊 Performance reference

Historical measurements from the author's Linux sandbox (Python 3.12, miniaudio null audio backend, 80×24 terminal, 192 kbps stereo MP3). These are reference figures, not a guarantee for every system or a fresh benchmark of every revision.

| Scenario | RSS | CPU |
|:--|--:|--:|
| Idle, 6 tracks | 19.0 MB | 0.00% |
| Playing, animation on | 19.7 MB | 1.5% |
| Playing, <code>--no-animation</code> | 19.4 MB | 0.66% |
| Paused, audio device released | 19.7 MB | ~0.1% |
| 5,000-track library, idle / playing | 21.4 / 22.2 MB | 0.0% / 1.5–2.3% |

## 🛠 Troubleshooting

| Issue | Try this |
|:--|:--|
| **NO AUDIO DEVICE** | Check ALSA/PulseAudio libraries and <code>pactl info</code>; try from a normal desktop session. |
| **miniaudio fails to build** | Install a C compiler and Python headers (for example, <code>build-essential python3-dev</code> on Debian/Ubuntu). |
| **Mouse does nothing** | Enable mouse support in your terminal; in tmux, set <code>set -g mouse on</code>. |
| **Strange glyphs** | Use a UTF-8 locale and a monospace font, or launch with <code>--ascii</code>. |
| **Colours look wrong** | Ensure truecolor support with <code>COLORTERM=truecolor</code>; check that <code>NO_COLOR</code> is not set. |
| **Terminal looks corrupted after a forced kill** | Run <code>reset</code>. |
| **A track is marked red** | The file failed to decode and is skipped automatically. |

## 🤝 Contributing

Issues, bug reports, and improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a contribution.

## 📄 License

No licence has been selected yet, so no permissions beyond the default copyright law are granted by this repository.

---

<div align="center">

**XMusic — your library, your terminal, your control.**

Made with care by [Abdellah Mouida](https://github.com/Abdellah-mouida).

</div>
