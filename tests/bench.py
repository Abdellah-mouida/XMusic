"""Measure RSS / CPU of a live xmusic process (read from /proc). Usage: bench.py"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ptyrun import Session
TICK = os.sysconf("SC_CLK_TCK")

def rss(pid):
    for l in open("/proc/%d/status" % pid):
        if l.startswith("VmRSS"): return int(l.split()[1]) / 1024
def hwm(pid):
    for l in open("/proc/%d/status" % pid):
        if l.startswith("VmHWM"): return int(l.split()[1]) / 1024
def cpu(pid):
    f = open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / TICK
def threads(pid): return len(os.listdir("/proc/%d/task" % pid))
def measure(label, s, secs=10):
    c0, t0 = cpu(s.pid), time.time(); s.pump(secs); c1, t1 = cpu(s.pid), time.time()
    print("%-46s RSS %5.1f MB  (peak %5.1f)  CPU %5.2f%%  threads %d" % (label, rss(s.pid), hwm(s.pid), 100 * (c1 - c0) / (t1 - t0), threads(s.pid)))

def run(root, extra=(), vol100=False):
    return Session(args=["--music-dir", root, "--null-audio", *extra])

if __name__ == "__main__":
    import shutil
    for root, name, wait in (("/tmp/Music", "9 tracks", 2), ("/tmp/Big", "5000 tracks", 0)):
        shutil.rmtree("/tmp/xm_home", ignore_errors=True)
        s = run(root); t0 = time.time()
        if name.startswith("5000"):
            while "INDEXING" not in s.text() and time.time() - t0 < 5: s.pump(0.1)
            print("[%s] first frame after %.2fs, metadata indexing in progress: %s" % (name, time.time() - t0, "INDEXING" in s.text()))
            measure("%s: while indexing" % name, s, 3)
            while "INDEXING" in s.text() and time.time() - t0 < 120: s.pump(0.5)
            print("[%s] indexing finished after %.1fs" % (name, time.time() - t0))
        else:
            s.pump(2.5)
        measure("%s: idle (stopped)" % name, s, 8)
        s.send("\r", 0.5); s.send("\r", 0.5) if False else None
        s.send("/gamma\r", 0.4) if name.startswith("9") else None
        s.send("\r" if name.startswith("9") else "\r", 0.5)
        measure("%s: playing, animation on, vol 70%%" % name, s, 10)
        s.send("+++++", 0.3)
        s.send("+" * 3, 0.3)
        measure("%s: playing, animation on, vol 100%%" % name, s, 8)
        s.send(" ", 0.3); measure("%s: paused" % name, s, 8)
        s.send(" ", 0.3); s.send("q"); s.wait_exit(); s.kill()
    shutil.rmtree("/tmp/xm_home", ignore_errors=True)
    s = run("/tmp/Music", ["--no-animation"]); s.pump(2); s.send("/gamma\r\r", 0.8)
    s.send("---", 0.3); measure("9 tracks: playing, --no-animation, vol 55%", s, 10); s.send("q"); s.wait_exit()
