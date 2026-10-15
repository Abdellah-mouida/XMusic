import os, sys, time, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ptyrun import Session
from bench import measure, rss  # noqa (bench.py main code is guarded below)
def go(label, extra=(), keys=""):
    shutil.rmtree("/tmp/xm_home", ignore_errors=True)
    s = Session(args=["--music-dir", "/tmp/Long", "--null-audio", *extra]); s.pump(2.0)
    s.send("\r", 0.3); s.send("\r", 1.0); s.send(keys, 0.3)
    return s
s = go("a"); assert "PLAYING" in s.text()
measure("10-min track: playing, anim on, vol 70% (audioop)", s, 15)
s.send("+++++++", 0.3); measure("10-min track: playing, anim on, vol 100%", s, 15)
s.send("-" * 9, 0.3); measure("10-min track: playing, anim on, vol 55%", s, 15)
s.send(" ", 0.3); measure("10-min track: paused >2s (device released)", s, 10)
s.send(" ", 0.3); s.send("q"); s.wait_exit(); s.kill()
s = go("b", ["--no-animation"]); measure("10-min track: playing, --no-animation, vol 70%", s, 15); s.send("q"); s.wait_exit()
