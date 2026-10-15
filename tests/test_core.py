"""Unit tests for the pure-logic modules: queue/shuffle/repeat, playlists, config, themes, paths."""
import json, os, random, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xmusic_core import config, paths, themes
from xmusic_core.playlists import Playlists
from xmusic_core.playqueue import PlayQueue

RES = []
def check(c, m): RES.append(bool(c)); print(("PASS  " if c else "FAIL  ") + m)

class T:
    def __init__(s, n): s.n, s.bad = n, False
    def __repr__(s): return "T%d" % s.n
tr = lambda n: [T(i) for i in range(n)]
def play_all(q, limit=10000):
    out = [q.cur.track.n] if q.cur else []
    for _ in range(limit):
        it = q.advance(auto=True)
        if it is None: break
        out.append(it.track.n)
    return out

# ---------------------------------------------------------------- queue: basics + repeat
q = PlayQueue(random.Random(1)); q.set_tracks(tr(5), 0)
check(play_all(q) == [0, 1, 2, 3, 4], "sequential playback, repeat off: plays 0..4 then ends")
check(q.advance(auto=True) is None, "repeat off: advance at end returns None (stop)")
q.set_repeat("all"); q.set_tracks(tr(3), 0)
seen = [q.cur.track.n] + [q.advance(auto=True).track.n for _ in range(7)]
check(seen == [0, 1, 2, 0, 1, 2, 0, 1], "repeat all wraps around: %s" % seen)
q.set_repeat("one")
check([q.advance(auto=True).track.n for _ in range(4)] == [q.cur.track.n] * 4, "repeat one replays the same track on natural end")
n0 = q.cur.track.n; q.advance(auto=False)
check(q.cur.track.n == (n0 + 1) % 3, "repeat one: manual Next still skips ahead")
q.set_repeat("off"); q.set_tracks(tr(4), 2)
check(q.retreat().track.n == 1 and q.retreat().track.n == 0 and q.retreat() is None, "Previous walks back then reports 'restart'")

# ---------------------------------------------------------------- queue: shuffle
ok_perm, ok_first = True, True
for seed in range(200):
    q = PlayQueue(random.Random(seed)); q.set_shuffle(True); q.set_tracks(tr(12), seed % 12)
    first = q.cur.track.n
    order = play_all(q)
    ok_perm &= sorted(order) == list(range(12)) and len(order) == 12
    ok_first &= order[0] == first
check(ok_perm, "shuffle plays every track exactly once per cycle (200 seeds)")
check(ok_first, "shuffle keeps the chosen track first")
q = PlayQueue(random.Random(5)); q.set_shuffle(True); q.set_repeat("all"); q.set_tracks(tr(6), 0)
imm, seq, nat = 0, [q.cur.track.n], list(range(6))
for _ in range(600):
    prev = q.cur.track.n; it = q.advance(auto=True); seq.append(it.track.n); imm += (it.track.n == prev)
check(imm == 0, "shuffle + repeat all: never plays the same track twice in a row across 600 transitions")
check(seq != (nat * 101)[:len(seq)], "shuffled order differs from list order")
cycles = [seq[i:i + 6] for i in range(0, 600, 6)]
check(all(sorted(c) == nat for c in cycles), "every shuffle cycle is a complete permutation")
q = PlayQueue(random.Random(2)); q.set_shuffle(True); q.set_tracks(tr(1), 0)
check(q.advance(auto=True) is None, "one-track library, shuffle + repeat off: ends safely")
q.set_repeat("all"); check(q.advance(auto=True).track.n == 0, "one-track library, shuffle + repeat all: replays safely")
q = PlayQueue(); q.set_shuffle(True)
check(q.advance() is None and q.retreat() is None and q.pos() == -1, "empty queue is safe")
q = PlayQueue(random.Random(3)); q.set_shuffle(True); q.set_tracks(tr(10), 0)
a = [q.advance().track.n for _ in range(4)]; back = [q.retreat().track.n for _ in range(4)]
check(back == [a[2], a[1], a[0], 0], "Previous under shuffle retraces the actual play history")
q.set_shuffle(False); check([x.track.n for x in q.seq] == list(range(10)), "turning shuffle off restores natural order")

# ---------------------------------------------------------------- queue: editing keeps things valid
q = PlayQueue(random.Random(4)); q.set_tracks(tr(5), 1); cur = q.cur
extra = T(99); it = q.enqueue(extra)
check(q.items[-1] is it and q.cur is cur, "enqueue appends without changing the current track")
it2 = q.enqueue(T(98), play_next=True)
check(q.seq[q.pos() + 1] is it2 and q.cur is cur, "play-next inserts right after the current track")
check(q.remove(it) and it not in q.items and q.cur is cur, "remove deletes a queued item, current unaffected")
check(q.remove(cur) is False and q.cur is cur, "the playing item cannot be removed (no interruption)")
q.move(it2, +1); check(q.seq[q.pos() + 2] is it2, "move down reorders")
q.move(it2, -1); check(q.seq[q.pos() + 1] is it2, "move up reorders")
q.clear(); check(q.items == [cur] and q.cur is cur and q.upcoming() == [], "clear keeps only the playing track")
q = PlayQueue(random.Random(6)); q.set_shuffle(True); q.set_tracks(tr(8), 0)
added = q.enqueue(T(50)); q.enqueue(T(51), play_next=True)
check(len(q.items) == 10 and sorted(map(id, q.items)) == sorted(map(id, q.order)), "shuffle: items/order stay consistent after adds")
q.remove(added); check(len(q.items) == len(q.order) == 9 and all(x is not added for x in q.order), "shuffle: removal purges both lists and history")
dupe = T(7); q = PlayQueue(); q.set_tracks([dupe, dupe, dupe], 0)
check(len({id(x) for x in q.items}) == 3 and play_all(q) == [7, 7, 7], "same track queued 3x: distinct entries, all play")
bad = tr(4); bad[1].bad = True; q = PlayQueue(); q.set_tracks(bad, 0); q.advance(); q.advance()
check(all(not x.track.bad for x in q.hist), "failed tracks never enter the Previous history")

# ---------------------------------------------------------------- playlists
d = Path(tempfile.mkdtemp()); p = Playlists(d).load()
check(p.names() == ["Favorites"], "fresh install has a Favorites playlist")
check(p.create("Road trip") == "Road trip" and p.create("road TRIP") is None, "create + duplicate (case-insensitive) rejection")
check(p.create("   ") is None and p.valid_name("") is not None, "blank names rejected")
p.add("Road trip", "/m/a.mp3"); p.add("Road trip", "/m/b.mp3"); check(p.add("Road trip", "/m/a.mp3") is False, "add + duplicate add ignored")
p2 = Playlists(d).load(); check(p2.get("Road trip") == ["/m/a.mp3", "/m/b.mp3"], "playlists persist across restarts")
check(p2.rename("Road trip", "Drive") == "Drive" and "Road trip" not in p2.data and p2.get("Drive"), "rename keeps contents")
check(p2.rename("Favorites", "X") is None and p2.delete("Favorites") is False, "Favorites can't be renamed/deleted")
p2.remove("Drive", "/m/a.mp3"); check(p2.get("Drive") == ["/m/b.mp3"], "remove track")
check(p2.toggle("Favorites", "/m/z.mp3") is True and p2.toggle("Favorites", "/m/z.mp3") is False, "toggle favorite on/off")
check(p2.delete("Drive") and "Drive" not in Playlists(d).load().data, "delete persists")
(d / "playlists.json").write_text("{ not json"); p3 = Playlists(d).load()
check(p3.names() == ["Favorites"] and (d / "playlists.json.bad").exists(), "corrupt playlists file: recovered, original kept as .bad")
leg = Playlists(Path(tempfile.mkdtemp())); leg.import_legacy({"Favorites": ["/old.mp3"], "Mix": ["/x.mp3"]})
check(leg.get("Mix") == ["/x.mp3"], "XMusic 1.x playlists migrate into playlists.json")

# ---------------------------------------------------------------- config
d = Path(tempfile.mkdtemp()); s = config.Settings(d).load()
check(s["theme"] == "blue" and s["volume"] == 70 and s.warning is None, "defaults on first run")
s["theme"] = "violet"; s["volume"] = 33; s["repeat"] = "all"; s["shuffle"] = True; s.save()
s2 = config.Settings(d).load(); check((s2["theme"], s2["volume"], s2["repeat"], s2["shuffle"]) == ("violet", 33, "all", True), "settings round-trip")
(d / "config.json").write_text(json.dumps({"theme": "nonsense", "volume": 9999, "repeat": "weird", "shuffle": "yes", "music_dir": 5}))
s3 = config.Settings(d).load()
check((s3["theme"], s3["volume"], s3["repeat"], s3["shuffle"], s3["music_dir"]) == ("blue", 100, "off", False, None), "invalid values fall back safely (theme -> blue, volume clamped)")
(d / "config.json").write_text("{{{ broken"); s4 = config.Settings(d).load()
check(s4["theme"] == "blue" and s4.warning and (d / "config.json.bad").exists(), "malformed config.json: defaults + backup, no crash")
(d / "config.json").write_text(json.dumps({"theme": "ROSE"})); check(config.Settings(d).load()["theme"] == "girly", "theme alias/case-insensitive ('ROSE' -> girly)")
(d / "config.json").write_text(json.dumps({"volume": 50, "recent": ["/a.mp3"], "playlists": {"Favorites": ["/a.mp3"]}}))
check(config.Settings(d).load().legacy.get("recent") == ["/a.mp3"], "1.x config: legacy recent/playlists detected for migration")
st = config.State(d); st.recent, st.queue, st.current = ["/a"], ["/a", "/b"], "/b"; st.save()
st2 = config.State(d).load(); check((st2.recent, st2.queue, st2.current) == (["/a"], ["/a", "/b"], "/b"), "recent + queue state round-trip")

# ---------------------------------------------------------------- themes
req = {"bg", "panel", "border", "accent", "bright", "hl", "text", "text2", "muted", "rem", "ok", "warn", "err", "brand_a", "brand_b",
       "playing", "sel_bar", "prog_fill", "prog_knob", "vol", "st_play", "st_pause", "st_idle", "search", "anim_a", "anim_b"}
check(themes.theme_ids() == ["blue", "girly", "yaru", "amoled-blue", "amoled-pink", "violet"], "six themes with the documented IDs")
check(all(req <= set(t) for t in themes.THEMES.values()), "every theme defines every colour role")
check(all(all(len(v) == 6 and int(v, 16) >= 0 for k, v in t.items() if k not in ("id", "name", "desc")) for t in themes.THEMES.values()), "all colour values are valid 6-digit hex")
check(themes.THEMES["amoled-blue"]["bg"] == "000000" and themes.THEMES["amoled-pink"]["bg"] == "000000", "AMOLED themes use pure black #000000 backgrounds")
check(all(themes.THEMES[t]["bg"] != "000000" for t in ("blue", "girly", "yaru", "violet")), "non-AMOLED themes keep tinted surfaces")
check(themes.get("does-not-exist")["id"] == "blue" and themes.resolve(None) is None, "unknown theme id -> blue fallback")
check(themes.THEMES["blue"]["accent"] == "3D8BFF" and themes.THEMES["girly"]["accent"] == "FF78B7" and themes.THEMES["yaru"]["accent"] == "E95420" and themes.THEMES["violet"]["accent"] == "8B5CF6", "palettes match the specified accents")
def dist(a, b): return sum((int(a[i:i+2], 16) - int(b[i:i+2], 16)) ** 2 for i in (0, 2, 4)) ** .5
check(all(dist(t["accent"], t["bg"]) > 150 and dist(t["text"], t["bg"]) > 300 for t in themes.THEMES.values()), "accent/text contrast against background is sufficient in all themes")
os.environ["NO_COLOR"] = "1"; check(themes.detect_depth() == 0 and themes.Style().sgr("FF0000", "000000", True) == "\x1b[0;1m", "NO_COLOR: no colour codes, bold only")
del os.environ["NO_COLOR"]
for env, want in (({"COLORTERM": "truecolor"}, 24), ({"TERM": "xterm-256color", "COLORTERM": ""}, 8), ({"TERM": "linux", "COLORTERM": ""}, 4), ({"TERM_PROGRAM": "Apple_Terminal", "COLORTERM": "", "TERM": "xterm-256color"}, 8)):
    saved = {k: os.environ.get(k) for k in ("COLORTERM", "TERM", "TERM_PROGRAM", "VTE_VERSION", "WT_SESSION")}
    for k in saved: os.environ.pop(k, None)
    os.environ.update(env); got = themes.detect_depth()
    for k, v in saved.items(): (os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v))
    check(got == want, "colour depth detection %s -> %d" % (env, got))

# ---------------------------------------------------------------- paths (simulating other operating systems)
def with_platform(plat, env, fn):
    old = (sys.platform, dict(os.environ)); sys.platform = plat
    for k in ("XMUSIC_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "APPDATA"): os.environ.pop(k, None)
    os.environ.update(env)
    try: return fn()
    finally: sys.platform = old[0]; os.environ.clear(); os.environ.update(old[1])
w = with_platform("win32", {"APPDATA": r"C:\Users\Ann\AppData\Roaming"}, lambda: (paths.config_dir(), paths.data_dir()))
check(str(w[0]).endswith("XMusic") and "AppData" in str(w[0]) and w[0] == w[1], "Windows: %%APPDATA%%\\XMusic (%s)" % w[0])
m = with_platform("darwin", {}, lambda: paths.config_dir())
check(str(m).endswith("Library/Application Support/XMusic"), "macOS: ~/Library/Application Support/XMusic")
l = with_platform("linux", {"XDG_CONFIG_HOME": "/x/cfg", "XDG_DATA_HOME": "/x/data"}, lambda: (paths.config_dir(), paths.data_dir()))
check((str(l[0]), str(l[1])) == (os.path.join("/x/cfg", "xmusic"), os.path.join("/x/data", "xmusic")), "Linux honours XDG_CONFIG_HOME / XDG_DATA_HOME")
check(with_platform("linux", {"XMUSIC_HOME": "/tmp/xm"}, lambda: paths.config_dir()) == Path("/tmp/xm"), "XMUSIC_HOME overrides everything")
check(paths.short(Path.home() / "Music" / "a") .startswith("~"), "short(): home abbreviated")

print("\n%d/%d core checks passed" % (sum(RES), len(RES))); sys.exit(0 if all(RES) else 1)
