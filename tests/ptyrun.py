"""PTY test harness: runs xmusic in a pseudo-terminal and renders its output with pyte (test-only dependency)."""
import fcntl, os, pty, select, signal, struct, sys, termios, time
try:
    import pyte                      # pip install pyte  (test-only dependency, see requirements-dev.txt)
except ImportError:
    sys.path.insert(0, os.environ.get("PYTELIB", "/tmp/pytelib"))
    import pyte

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Session:
    all = []

    def __init__(self, cols=80, rows=24, args=(), env=None, home="/tmp/xm_home"):
        os.makedirs(home, exist_ok=True)
        self.cols, self.rows = cols, rows
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.raw = b""
        e = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor", HOME=home, XMUSIC_HOME=home + "/xmusic")
        e.pop("NO_COLOR", None); e.pop("XMUSIC_ASCII", None)
        e.update(env or {})
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(ROOT)
            os.execve(os.path.join(ROOT, "venv/bin/python"),
                      [os.path.join(ROOT, "venv/bin/python"), "xmusic.py", *args], e)
        self.pid, self.fd = pid, fd
        Session.all.append(self)
        self.resize(cols, rows)

    def resize(self, cols, rows):
        self.cols, self.rows = cols, rows
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.screen.resize(rows, cols)
        try:
            os.kill(self.pid, signal.SIGWINCH)
        except ProcessLookupError:
            pass

    def pump(self, secs=0.5):
        end = time.time() + secs
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if r:
                try:
                    d = os.read(self.fd, 65536)
                except OSError:
                    return
                if not d:
                    return
                self.raw += d
                self.stream.feed(d)

    def send(self, data, wait=0.4):
        os.write(self.fd, data.encode() if isinstance(data, str) else data)
        self.pump(wait)

    def click(self, x, y, wait=0.4):          # x,y 0-based
        self.send("\x1b[<0;%d;%dM\x1b[<0;%d;%dm" % (x + 1, y + 1, x + 1, y + 1), wait)

    def wheel(self, x, y, up=True, wait=0.3):
        self.send("\x1b[<%d;%d;%dM" % (64 if up else 65, x + 1, y + 1), wait)

    def text(self):
        return "\n".join(self.screen.display)

    def dump(self, title=""):
        print("┄┄ %s ┄┄" % title)
        print("\n".join(l.rstrip() for l in self.screen.display))

    def alive(self):
        try:
            p, _ = os.waitpid(self.pid, os.WNOHANG)
            return p == 0
        except ChildProcessError:
            return False

    def wait_exit(self, secs=3):
        end = time.time() + secs
        while time.time() < end:
            self.pump(0.1)
            try:
                p, st = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                return 0
            if p:
                return os.waitstatus_to_exitcode(st)
        return None

    def kill(self):
        try:
            os.kill(self.pid, signal.SIGKILL); os.waitpid(self.pid, 0)
        except Exception:
            pass
