"""Idle and playing RSS/CPU for a given library (fast PTY drain, no emulator). Usage: bench_big.py DIR"""
import fcntl, os, pty, select, shutil, struct, sys, termios, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); root = sys.argv[1]
shutil.rmtree("/tmp/xm_home", ignore_errors=True)
pid, fd = pty.fork()
if pid == 0:
    os.chdir(ROOT); env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor", XMUSIC_HOME="/tmp/xm_home/xmusic", HOME="/tmp/xm_home")
    os.execve(ROOT + "/venv/bin/python", [ROOT + "/venv/bin/python", "xmusic.py", "--music-dir", root, "--null-audio"], env)
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
T = os.sysconf("SC_CLK_TCK")
cpu = lambda: (lambda f: (int(f[11]) + int(f[12])) / T)(open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split())
rss = lambda: [int(l.split()[1]) for l in open("/proc/%d/status" % pid) if l.startswith("VmRSS")][0] / 1024
def drain(secs):
    end = time.time() + secs
    while time.time() < end:
        if select.select([fd], [], [], 0.05)[0]: os.read(fd, 65536)
def measure(label, secs):
    c0, t0 = cpu(), time.time(); drain(secs); print("%-34s RSS %.1f MB  CPU %.2f%%" % (label, rss(), 100 * (cpu() - c0) / (time.time() - t0)))
if os.environ.get("TIMELINE"):
    last = cpu()
    for i in range(30):
        drain(1.0); c = cpu(); print("t=%2ds cpu %.0f%%" % (i + 1, 100 * (c - last))); last = c
drain(14)                                   # let indexing finish
measure("idle (stopped)", 8)
os.write(fd, b"\r"); drain(1.5); measure("playing, animation on", 12)
os.write(fd, b" "); drain(3); measure("paused", 8)
os.write(fd, b"q"); time.sleep(0.5)
