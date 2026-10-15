"""Library scan / indexing time in a real PTY, draining output without a slow emulator."""
import fcntl, os, pty, select, struct, sys, termios, time, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/Big"
shutil.rmtree("/tmp/xm_home", ignore_errors=True)
pid, fd = pty.fork()
if pid == 0:
    os.chdir(ROOT); env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor", XMUSIC_HOME="/tmp/xm_home/xmusic", HOME="/tmp/xm_home")
    os.execve(ROOT + "/venv/bin/python", [ROOT + "/venv/bin/python", "xmusic.py", "--music-dir", root, "--null-audio"], env)
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
TICK = os.sysconf("SC_CLK_TCK")
def cpu(p):
    f = open("/proc/%d/stat" % p).read().rsplit(")", 1)[1].split(); return (int(f[11]) + int(f[12])) / TICK
t0 = time.time(); first = done = None; tail = b""; last = (time.time(), 0.0); quiet = 0
while time.time() - t0 < 90:
    r, _, _ = select.select([fd], [], [], 0.05)
    if r:
        tail = (tail + os.read(fd, 65536))[-4000:]
        if first is None and b"TRACKS" in tail: first = time.time() - t0
    now = time.time()
    if first and now - last[0] >= 0.5:               # indexing is finished when CPU use falls to ~idle
        c = cpu(pid); quiet = quiet + 1 if (c - last[1]) / (now - last[0]) < 0.05 else 0
        last = (now, c)
        if quiet >= 3: done = now - t0 - 1.5; break
def rss(p):
    return [int(l.split()[1]) for l in open("/proc/%d/status" % p) if l.startswith("VmRSS")][0] / 1024
print("%s: first frame %.2fs, metadata fully indexed after %.1fs, RSS %.1f MB" % (root, first or -1, done or -1, rss(pid)))
os.write(fd, b"q"); time.sleep(0.5)
