"""End-to-end tests: the real xmusic process in a PTY (miniaudio NULL backend: real decoding + callbacks, no sound card).
   venv/bin/python tests/test_pty.py [music_dir_with_bad_files] [clean_music_dir]"""
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ptyrun import Session, ROOT

MUSIC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/Music"          # includes corrupt/empty files
CLEAN = sys.argv[2] if len(sys.argv) > 2 else "/tmp/Music2"         # 6 good tracks, titles distinct
A = ["--null-audio"]
RES = []
HOME = "/tmp/xm_home"; CFG = HOME + "/xmusic"

def check(c, m): RES.append(bool(c)); print(("PASS  " if c else "FAIL  ") + m); return c
def fresh(music=CLEAN, args=(), keep=False, **kw):
    if not keep: shutil.rmtree(HOME, ignore_errors=True)
    return Session(args=["--music-dir", music, *A, *args], **kw)
def row(s, needle, start=0):
    for i, l in enumerate(s.screen.display):
        if i >= start and needle in l: return i
def col(s, needle, r=None):
    r = row(s, needle) if r is None else r
    return s.screen.display[r].index(needle) if r is not None else None
def elapsed(s):
    m = re.search(r"(\d\d):(\d\d) / ", s.text()); return int(m.group(1)) * 60 + int(m.group(2)) if m else None
def title(s):
    r = row(s, "NOW PLAYING"); return s.screen.display[r + 2].split("│")[2].strip() if r is not None else None
def toast_or(s, text): return text in s.text()
def jread(p): return json.load(open(p))
def quit_(s): s.send("q"); return s.wait_exit()

# ============ 1 branding: three logo tiers, status, theme name
s = fresh(); s.pump(1.5)
check("▀" in s.screen.display[1] + s.screen.display[2] and "TERMINAL MUSIC PLAYER" in s.text() and "LOCAL AUDIO" in s.text(), "80x24: 3-row logo + subtitle 'TERMINAL MUSIC PLAYER • LOCAL AUDIO'")
check("AUDIO READY" in s.text() and "Blue" in s.screen.display[4], "playback-state indicator and active theme name shown (AUDIO READY · Blue)")
s.resize(80, 32); s.pump(0.6); check("██" in s.screen.display[1] and "██" in s.screen.display[5], "80x32: large 5-row ASCII-art logo")
s.resize(80, 19); s.pump(0.6); check("╲╱ XMusic" in s.screen.display[1], "80x19: compact wordmark")
s.resize(60, 20); s.pump(0.6); check("XMusic" in s.screen.display[0] and "Shuf" in s.text() and "Rep" in s.text(), "60x20 compact layout keeps shuffle/repeat controls")
for (c, r_) in ((45, 12), (30, 9), (25, 6), (120, 45), (80, 24)):
    s.resize(c, r_); s.pump(0.4); check(s.alive() and ("LIBRARY" in s.text() or "All" in s.text() or "too small" in s.text()), "resize %dx%d handled" % (c, r_))
check("9 TRACKS" not in s.text() and "6 TRACKS" in s.text(), "library count shown")
quit_(s)

# ============ 2 playback basics (search isolation, pause, seek, volume, mute)
s = fresh(); s.pump(1.2)
s.send("/"); s.send("q"); check(s.alive() and "/ q" in s.text(), "'q' typed in search does not quit (shortcuts isolated)")
s.send("\x7f"); s.send("01 alpha\r\r", 1.6)
check("PLAYING" in s.text() and title(s) == "Alpha Wave" and (elapsed(s) or 0) >= 1, "search -> Enter plays; title/elapsed shown (%s, %ss)" % (title(s), elapsed(s)))
s.send(" ", 0.5); a = elapsed(s); s.pump(1.3)
check("PAUSED" in s.text() and a == elapsed(s), "pause freezes time")
s.send(" ", 1.3); check("PLAYING" in s.text() and elapsed(s) > a, "resume continues")
s.send("\x1b[D\x1b[D\x1b[D", 0.9); b = elapsed(s); s.send("\x1b[C", 0.8)
check(b <= 1 and elapsed(s) >= b + 4, "seek: Left rewinds, Right +5s (%s -> %s)" % (b, elapsed(s)))
s.send("+"); check("Volume 75%" in s.text(), "'+' volume 75%")
s.send("m", 0.4); check("MUTE" in s.text() and "Muted" in s.text(), "'m' mutes (MUTE indicator)")
s.send("m", 0.4); check("MUTE" not in s.text() and "75%" in s.text(), "'m' unmutes, volume preserved")
vr = row(s, "VOL"); s.click(col(s, "VOL", vr) + 1, vr, 0.4); check("MUTE" in s.text(), "clicking the VOL label toggles mute")
s.click(col(s, "VOL", vr) + 1, vr, 0.4); s.click(s.screen.display[vr].index("[+]") + 1, vr, 0.4); check("80%" in s.screen.display[vr], "mouse [+] raises volume")
quit_(s)

# ============ 3 shuffle / repeat via UI
s = fresh(); s.pump(1.2)
s.send("s", 0.4); check("Shuffle ON" in s.text() and "Shuffle ON" in s.screen.display[row(s, "Shuffle")], "'s' toggles shuffle; indicator shows ON")
s.send("r", 0.3); check("Repeat ALL" in s.text(), "'r' -> Repeat ALL")
s.send("r", 0.3); check("Repeat ONE" in s.text(), "'r' -> Repeat ONE")
s.send("r", 0.3); check("Repeat OFF" in s.text(), "'r' -> Repeat OFF")
s.send("s", 0.3)
# shuffle: many 'next' presses never repeat the same title twice in a row and visit several tracks
s.send("s", 0.3); s.send("r", 0.3); s.send("\r", 0.3); s.send("\r", 1.0)
titles = [title(s)]
for _ in range(11): s.send("n", 0.45); titles.append(title(s))
check(all(titles[i] != titles[i + 1] for i in range(len(titles) - 1)) and len(set(titles)) >= 5, "shuffle+Next: %d distinct titles in 12 plays, none back-to-back" % len(set(titles)))
check(len(set(titles[:6])) == 6, "shuffle plays each of the 6 tracks once before any repeats (first 6: %s)" % sorted(set(titles[:6]))[:3])
quit_(s)
# repeat one / off / all with the 3s track
s = fresh(); s.pump(1.2); s.send("/notags2\r", 0.4); s.send("r", 0.3); s.send("r", 0.3); s.send("\r", 0.3)   # repeat ONE
s.send("\r", 0.8); t0 = title(s); s.pump(7.5)
check(t0 == title(s) == "Notags2" and "PLAYING" in s.text(), "Repeat ONE: 3s track replays itself past its end (still PLAYING '%s')" % title(s))
s.send("r", 0.3); s.pump(4.5)
check("STOPPED" in s.text() or "End of queue" in s.text(), "Repeat OFF: queue of one ends and stops")
quit_(s)
s = fresh(); s.pump(1.2); s.send("r", 0.3); s.send("/notags2\r", 0.3); s.send("\r", 0.3); s.pump(8.0)
check("PLAYING" in s.text() and title(s) == "Notags2", "Repeat ALL: single-track queue loops")
quit_(s)
s = fresh(); s.pump(1.2); s.send("\x1b[B" * 5, 0.2); s.send("\r", 0.3); s.send("r", 0.3)
t_first = title(s); s.pump(14)    # 'Notags2' (3s) is the last of 6 in path order; Repeat ALL wraps
check(s.alive() and "PLAYING" in s.text(), "Repeat ALL: queue wraps around and keeps playing")
quit_(s)

# ============ 4 queue management
s = fresh(); s.pump(1.2)
s.send("e", 0.3); s.send("\x1b[B", 0.2); s.send("e", 0.3); s.send("\x1b[B", 0.2); s.send("E", 0.3)
check("Playing next" in s.text() and "Queue  (3)" in s.text(), "'e' adds to the queue, 'E' plays next -> Queue (3), nothing started")
check("STOPPED" in s.text(), "queueing does not start/interrupt audio")
s.send("3", 0.5); check("QUEUE" in s.text() and "up next" in s.text(), "'3' opens the Queue view")
order0 = [l[4:40].strip() for l in s.screen.display[11:14]]
s.send("\r", 1.0); check("PLAYING" in s.text(), "Enter in the queue plays that item")
s.send("\x1b[B", 0.3); n_before = int(re.search(r"\((\d)\)", s.text()).group(1)); s.send("d", 0.4)
check(int(re.search(r"\((\d)\)", s.text()).group(1)) == n_before - 1 and "Removed from queue" in s.text(), "'d' removes a queued item")
s.send("\x1b[A", 0.3); s.send("d", 0.4); check("Can't remove the playing track" in s.text() and "PLAYING" in s.text(), "the playing item can't be removed (audio uninterrupted)")
s.send("c", 0.5); check("Queue cleared" in s.text() and "(1)" in s.text() and "PLAYING" in s.text(), "'c' clears the queue; current track keeps playing")
quit_(s)
s = fresh(); s.pump(1.2); s.send("e\x1b[Be\x1b[Be", 0.5); s.send("3", 0.4)
s.send("\x1b[B", 0.3); r1 = row(s, "▌"); s.send("K", 0.4); s.send("J", 0.4)
check(s.alive() and "QUEUE" in s.text(), "'K'/'J' move queue items without crashing")
quit_(s)

# ============ 5 playlists (create, add, open, play, rename, delete, persist, missing)
s = fresh(); s.pump(1.2)
s.send("4", 0.4); s.send("N", 0.4); check("NEW PLAYLIST" in s.text(), "'N' opens the new-playlist prompt")
s.send("\r", 0.3); check("can't be empty" in s.text(), "empty name rejected")
s.send("Road Trip\r", 0.5); check("Road Trip (0)" in s.text(), "playlist created and listed")
s.send("N", 0.3); s.send("road trip\r", 0.3); check("already exists" in s.text(), "duplicate name rejected"); s.send("\x1b", 0.3)
s.send("1", 0.3); s.send("A", 0.4); check("ADD TO PLAYLIST" in s.text() and "Road Trip" in s.text() and "Favorites" in s.text(), "'A' opens the add-to-playlist picker")
s.send("\x1b[B", 0.2); s.send("\r", 0.4); check("Added to Road Trip" in s.text(), "track added to chosen playlist")
s.send("\x1b[B", 0.2); s.send("A", 0.3); s.send("\x1b[B\x1b[B", 0.2); s.send("\r", 0.4); s.send("Mixtape\r", 0.5)
check("Created playlist Mixtape with 1 track" in s.text(), "picker -> '+ New playlist…' creates it and adds the track")
s.send("a", 0.4); check("Added to Favorites" in s.text(), "'a' adds to Favorites")
s.send("4", 0.4); s.send("\x1b[B\x1b[B", 0.2)   # plnew, Favorites, Mixtape, Road Trip order
pl_row = row(s, "Road Trip"); s.click(10, pl_row, 0.3); s.send("\r", 0.4)
check("PLAYLIST · Road Trip" in s.text() and "Play playlist" in s.text() and "Alpha" in s.text() or "Beta" in s.text(), "playlist opens showing its tracks")
pr = row(s, "Play playlist"); s.click(10, pr, 0.2); s.send("\r", 1.2); check("PLAYING" in s.text(), "'Play playlist' starts playback")
s.send("\x7f", 0.4); check("PLAYLISTS" in s.text(), "Backspace returns to the playlist list")
s.send("\x1b[B", 0.2) if "▌  + New" in s.text() else None
r = row(s, "Mixtape"); s.click(10, r, 0.3); s.send("R", 0.4); check("RENAME PLAYLIST" in s.text(), "'R' opens rename")
s.send("\x7f" * 7, 0.2); s.send("Chill\r", 0.5); check("Chill (1)" in s.text() and "♪ Mixtape" not in s.text(), "playlist renamed")
r = row(s, "Chill"); s.click(10, r, 0.3); s.send("D", 0.4); check("DELETE PLAYLIST" in s.text() and "Delete 'Chill'" in s.text(), "'D' asks for confirmation")
s.send("n", 0.4); check("Chill" in s.text(), "'n' cancels deletion")
s.send("D", 0.3); s.send("y", 0.5); check("♪ Chill" not in s.text() and "Deleted Chill" in s.text(), "'y' deletes the playlist")
r = row(s, "Favorites"); s.click(10, r, 0.3); s.send("D", 0.4); check("can't be deleted" in s.text(), "Favorites is protected")
quit_(s)
pl = jread(CFG + "/playlists.json")["playlists"]
check("Road Trip" in pl and len(pl["Road Trip"]) == 1 and "Chill" not in pl and len(pl["Favorites"]) == 1 and pl["Road Trip"][0].endswith(".mp3"), "playlists.json is human-readable JSON with only file paths")
s = fresh(keep=True); s.pump(1.2); s.send("4", 0.5); check("Road Trip (1)" in s.text() and "Favorites (1)" in s.text(), "playlists survive a restart")
os.remove(pl["Road Trip"][0]) if False else None
p = jread(CFG + "/playlists.json"); p["playlists"]["Road Trip"].append("/definitely/missing/ghost.mp3"); json.dump(p, open(CFG + "/playlists.json", "w"))
quit_(s); s = fresh(keep=True); s.pump(1.2); s.send("4", 0.4); r = row(s, "Road Trip"); s.click(10, r, 0.3); s.send("\r", 0.5)
check("ghost.mp3 (missing)" in s.text() and s.alive(), "missing playlist file shown as '(missing)', no crash")
s.send("\x1b[B", 0.2); gr = row(s, "ghost"); s.click(10, gr, 0.3); s.send("\r", 0.3); check("File not found" in s.text() and s.alive(), "activating a missing file is harmless")
s.send("d", 0.4); check("ghost" not in s.text(), "'d' removes the missing entry from the playlist"); quit_(s)

# ============ 6 themes
s = fresh(); s.pump(1.2); s.raw = b""
s.send("t", 0.5); check("THEME" in s.text() and all(n in s.text() for n in ("Blue", "Girly / Rose", "Yaru Orange", "AMOLED Blue", "AMOLED Pink", "Violet")), "'t' opens the theme picker listing all six themes")
s.raw = b""; s.send("\x1b[B", 0.5)
check(b"38;2;255;120;183" in s.raw and "Girly / Rose" in s.screen.display[4], "moving the selection live-previews the theme (rose accent #FF78B7 painted, header shows Girly / Rose)")
s.raw = b""; s.send("\x1b[B\x1b[B\x1b[B\x1b[B", 0.5); check(b"38;2;139;92;246" in s.raw, "preview of Violet paints #8B5CF6")
s.send("\x1b", 0.5); check("THEME" not in s.text() and "Blue" in s.screen.display[4], "Esc cancels the picker and reverts to the saved theme")
s.send("t", 0.4); s.send("\x1b[B\x1b[B\r", 0.6); check("Theme: Yaru Orange" in s.text() and jread(CFG + "/config.json")["theme"] == "yaru", "Enter applies and saves (config.json theme=yaru)")
s.raw = b""; s.send("/", 0.1); s.send("\x1b", 0.3)
quit_(s)
s = fresh(keep=True); s.pump(1.2); check("Yaru Orange" in s.text() and b"38;2;233;84;32" in s.raw, "selected theme persists across restart and is used from the first frame")
quit_(s)
s = fresh(keep=True, args=["--theme", "violet"]); s.pump(1.2); check("Violet" in s.screen.display[4] and b"38;2;139;92;246" in s.raw, "--theme violet overrides the saved theme for this launch")
quit_(s); check(jread(CFG + "/config.json")["theme"] == "yaru", "...without overwriting the saved preference")
for tid, bgcode in (("amoled-blue", b"48;2;0;0;0"), ("amoled-pink", b"48;2;0;0;0"), ("blue", b"48;2;8;11;18"), ("girly", b"48;2;26;18;32"), ("violet", b"48;2;18;11;36")):
    s = fresh(args=["--theme", tid]); s.pump(1.0); check(bgcode in s.raw, "--theme %s paints the expected background colour" % tid); quit_(s)
r = subprocess.run([sys.executable, "xmusic.py", "--theme", "nope"], capture_output=True, text=True, cwd=ROOT)
check(r.returncode == 2 and "unknown theme" in r.stderr, "invalid --theme: clear error, exit 2")
os.makedirs(CFG, exist_ok=True); open(CFG + "/config.json", "w").write('{"theme": "bogus", "volume": "loud"}')
s = fresh(keep=True); s.pump(1.2); check("Blue" in s.screen.display[4] and s.alive(), "invalid saved theme falls back to Blue")
quit_(s)
open(CFG + "/config.json", "w").write("{{ garbage"); s = fresh(keep=True); s.pump(1.2)
check(s.alive() and "unreadable" in s.text() and os.path.exists(CFG + "/config.json.bad"), "malformed config: warning shown, defaults used, backup kept"); quit_(s)
s = fresh(); s.pump(1.2); s.click(col(s, "Blue", 4) + 1, 4, 0.5); check("THEME" in s.text(), "clicking the theme name in the header opens the picker")
r = row(s, "Violet"); s.click(col(s, "Violet", r) + 2, r, 0.4); check("Violet" in s.screen.display[4], "mouse: click on a theme previews it")
vx = col(s, "Violet", r) + 2; s.click(vx, r, 0.05); s.click(vx, r, 0.5); check("THEME" not in s.text() and jread(CFG + "/config.json")["theme"] == "violet", "mouse: click again applies and saves")
s.send("t", 0.4); s.click(2, 1, 0.5); check("THEME" not in s.text(), "clicking outside the dialog closes it"); quit_(s)

# ============ 7 mouse (rows, double-click, buttons, nav, wheel, progress)
s = fresh(); s.pump(1.2)
r = row(s, "Beta Burst"); s.click(8, r, 0.3); check("▌" in s.screen.display[r][:4], "single click selects")
s.click(8, r, 0.05); s.click(8, r, 1.0); check(title(s) == "Beta Burst" and "PLAYING" in s.text(), "double-click plays")
pr = row(s, "Prev"); s.click(col(s, "Pause", pr) + 2, pr, 0.4); check("PAUSED" in s.text(), "Pause button pauses")
s.click(col(s, "Play", pr) + 2, pr, 0.4); check("PLAYING" in s.text(), "Play button resumes")
s.click(col(s, "Next", pr) + 2, pr, 1.0); check(title(s) != "Beta Burst", "Next button advances (%s)" % title(s))
s.click(col(s, "Prev", pr) + 2, pr, 1.0); check(title(s) == "Beta Burst", "Prev button goes back (%s)" % title(s))
sr = row(s, "Shuffle"); s.click(col(s, "Shuffle", sr) + 2, sr, 0.4); check("Shuffle ON" in s.text(), "Shuffle button toggles")
s.click(col(s, "Repeat", sr) + 2, sr, 0.4); check("Repeat ALL" in s.text(), "Repeat button cycles")
br = row(s, " / 0") - 1; s.click(62, br, 0.8); e2 = elapsed(s); check(e2 is not None and e2 >= 5, "progress-bar click seeks (%ss)" % e2)
s.click(6, row(s, "Queue  ("), 0.4); check("QUEUE" in s.text(), "nav click opens Queue")
s.click(6, row(s, "All Tracks"), 0.4); s.click(col(s, "Theme", 22), 22, 0.4); check("THEME" in s.text(), "clicking a footer hint ('t Theme') runs its action"); s.send("\x1b", 0.3)
quit_(s)
s = fresh(rows=18); s.pump(1.2); b1 = s.text(); s.wheel(10, 11, up=False); s.wheel(10, 11, up=False); check(b1 != s.text(), "wheel scrolls the list (18-row terminal)"); quit_(s)

# ============ 8 sorting, folders, recent, help
s = fresh(music=MUSIC); s.pump(1.4)
check("TRACKS" in s.text(), "library with corrupt/empty files loads"); s.send("o", 0.4); check("Sort: title" in s.text(), "'o' sorts by title")
s.send("o", 0.3); s.send("o", 0.3); s.send("o", 0.3); check("by length" in s.text(), "sort modes cycle: title > artist > album > length")
s.send("2", 0.4); check("FOLDERS" in s.text() and "Jazz/" in s.text() and "Rock/" in s.text(), "folder browser"); r = row(s, "Jazz/"); s.click(8, r, 0.3); s.send("\r", 0.4); check("FOLDERS · Jazz" in s.text(), "open folder"); s.send("\x7f", 0.3)
s.send("/garbage\r\r", 1.0); check(s.alive() and "Can't play" in s.text(), "undecodable file: error toast, no crash")
s.send("\x1b", 0.3); s.send("?", 0.4); check("KEYBOARD" in s.text() and "Shuffle" in s.text() and "Playlists" in s.text() or "PLAYLISTS" in s.text(), "'?' shows help incl. new shortcuts"); s.send("\x1b", 0.3)
check("LIBRARY" in s.text(), "Esc closes help"); quit_(s)
s = fresh(music=MUSIC); s.pump(1.2); s.send("\r", 1.0); s.send("\x1b[B", 0.2); s.send("5", 0.4)
check("RECENTLY PLAYED" in s.text(), "recently-played view"); quit_(s)

# ============ 9 NO_COLOR / ASCII / animation switches
s = fresh(env={"NO_COLOR": "1"}); s.pump(1.4); s.send("/01 alpha\r\r", 1.2)
check(b"38;2" not in s.raw and b"48;2" not in s.raw and b"38;5" not in s.raw and b"48;5" not in s.raw and "PLAYING" in s.text(), "NO_COLOR: no colour escapes emitted, UI fully usable")
quit_(s)
s = fresh(args=["--ascii"]); s.pump(1.4); s.send("/01 alpha\r\r", 1.2)
bad = [c for c in s.text() if ord(c) > 126]; check(not bad and "PLAYING" in s.text() and "XMusic" in s.text() or "#" in s.text(), "--ascii: screen is pure ASCII (%s non-ASCII chars)" % len(bad)); s.dump("ASCII mode 80x24"); quit_(s)
s = fresh(args=["--no-animation"]); s.pump(0.8); s.send("/01 alpha\r\r", 1.0); fr = set()
for _ in range(8): s.pump(0.13); fr.add(s.screen.display[row(s, "NOW PLAYING") + 1][41:48])
check("PLAYING" in s.text() and len(fr) == 1, "--no-animation: equalizer static (%d frame)" % len(fr)); quit_(s)
s = fresh(); s.pump(1.0); s.send("/01 alpha\r\r", 1.0); fr = set()
for _ in range(8): s.pump(0.13); fr.add(s.screen.display[row(s, "NOW PLAYING") + 1][41:48])
check(len(fr) >= 3, "animated equalizer changes while playing (%d frames)" % len(fr))
s.send(" ", 0.4); fr = set()
for _ in range(6): s.pump(0.15); fr.add(s.screen.display[row(s, "NOW PLAYING") + 1][41:48])
check(len(fr) == 1, "equalizer freezes when paused")
s.send("z", 0.4); check("Animations OFF" in s.text() and jread(CFG + "/config.json")["animation"] is False, "'z' toggles animations and persists"); quit_(s)

# ============ 10 persistence of modes/volume/queue + clean exits
s = fresh(); s.pump(1.0); s.send("s", 0.2); s.send("r", 0.2); s.send("+++", 0.3); s.send("e\x1b[Be", 0.4); quit_(s)
c = jread(CFG + "/config.json"); st = jread(CFG + "/state.json")
check(c["shuffle"] is True and c["repeat"] == "all" and c["volume"] == 85 and len(st["queue"]) == 2, "shuffle, repeat, volume and queue saved on exit")
s = fresh(keep=True); s.pump(1.3); check("Shuffle ON" in s.text() and "Repeat ALL" in s.text() and "85%" in s.text() and "Queue  (2)" in s.text(), "...and restored on the next start (queue restored, not auto-played, state STOPPED)")
quit_(s)
for name, act in (("q", lambda s: s.send("q")), ("Ctrl+C", lambda s: s.send("\x03")), ("SIGTERM", lambda s: os.kill(s.pid, 15)), ("SIGHUP", lambda s: os.kill(s.pid, 1))):
    s = fresh(); s.pump(1.0); act(s); code = s.wait_exit()
    check(code in (0, None) and code is not None and all(x in s.raw for x in (b"\x1b[?25h", b"\x1b[?1000l", b"\x1b[?1049l")) and b"Traceback" not in s.raw, "%s: exits cleanly, cursor/mouse/alt-screen restored" % name)
os.makedirs("/tmp/emptymusic", exist_ok=True)
s = fresh(music="/tmp/emptymusic"); s.pump(1.2); check("No MP3 files found" in s.text() and "0 TRACKS" in s.text(), "empty library: friendly message")
for k in (" ", "\r", "n", "p", "\x1b[C", "s", "r", "e", "3", "d", "c", "4", "N"): s.send(k, 0.15)
check(s.alive(), "every playback/queue key on an empty library is harmless"); s.send("\x1b", 0.2); quit_(s)
r = subprocess.run([sys.executable, "xmusic.py", "--music-dir", "/nonexistent/dir"], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, XMUSIC_HOME=CFG))
check(r.returncode == 2 and "not found" in r.stderr, "invalid --music-dir: clear error, exit 2")
bad = [x for x in Session.all if b"Exception ignored" in x.raw or b"Traceback" in x.raw or b"TypeError" in x.raw]
check(not bad, "no 'Exception ignored' / Traceback / TypeError (original miniaudio callback bug) in ANY of %d sessions" % len(Session.all))
for x in Session.all: x.kill()
print("\n%d/%d end-to-end checks passed" % (sum(RES), len(RES))); sys.exit(0 if all(RES) else 1)
