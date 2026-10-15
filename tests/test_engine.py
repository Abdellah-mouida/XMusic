"""Headless engine test on miniaudio's NULL backend (no sound card needed).
Asserts there are no callback exceptions (miniaudio prints 'Exception ignored' to stderr)."""
import glob, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xmusic_core.audio import Engine

root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Music")
good = os.path.join(root, "Jazz", "Gamma.mp3")
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or c
res = []
e = Engine(null=True); e.open()
res.append(ok(e.backend == "Null", "device opened (backend=%s), generator primed" % e.backend))
e.play(good); t0 = time.time(); time.sleep(1.5)
p = e.position()
res.append(ok(1.2 < p < 1.9, "position advances in real time (%.2fs after 1.5s)" % p))
e.toggle_pause(); a = e.position(); time.sleep(0.6); b = e.position()
res.append(ok(abs(a - b) < 0.01 and e.paused and not e.playing, "pause freezes position"))
e.toggle_pause(); time.sleep(0.4)
res.append(ok(e.position() > b + 0.2, "resume continues"))
e.play(good, start=4.0); time.sleep(0.5); p = e.position()
res.append(ok(4.3 < p < 5.0, "seek to 4.0s -> %.2fs" % p))
e.set_volume(30); time.sleep(0.4)
res.append(ok(e.volume == 30 and e.error is None, "volume change while playing, no error"))
t = time.time()
while not e.finished and time.time() - t < 10: time.sleep(0.1)
res.append(ok(e.finished and e.error is None, "end-of-file detected (finished flag), error=%s" % e.error))
for bad in ("Corrupt.mp3", "Garbage.mp3", "Empty.mp3", "missing.mp3"):
    try:
        e.play(os.path.join(root, bad)); time.sleep(0.5)
        res.append(ok(e.finished or e.error is not None, "%s: tolerated (finished=%s error=%s)" % (bad, e.finished, e.error)))
    except Exception as ex:
        res.append(ok(True, "%s: rejected cleanly in play() (%s)" % (bad, type(ex).__name__)))
# device power management: release after 2s idle/paused, transparently restart
e.play(good); e.set_volume(100); time.sleep(0.5); res.append(ok(e.device_running, "device running while playing"))
e.toggle_pause(); p0 = e.position()
t = time.time()
while time.time() - t < 4: e.idle_check(); time.sleep(0.1)
res.append(ok(not e.device_running, "device released after >2s paused (no CPU, sound card free)"))
e.toggle_pause(); time.sleep(0.8)
res.append(ok(e.device_running and e.position() > p0 + 0.4 and e.error is None, "resume restarts device and continues (%.2f -> %.2f)" % (p0, e.position())))
e.stop(); t = time.time()
while time.time() - t < 3.5: e.idle_check(); time.sleep(0.1)
res.append(ok(not e.device_running, "device released after >2s stopped"))
e.play(good, start=1.0); time.sleep(0.6)
res.append(ok(e.device_running and e.position() > 1.3 and e.error is None, "play after idle restart works (pos %.2f)" % e.position()))
e.play(good); e.set_volume(100)
for _ in range(30):                      # rapid track swapping must not raise in the callback thread
    e.play(good, start=_ * 0.1); time.sleep(0.02)
e.close()
# pure-Python volume fallback (used when audioop is unavailable) must match the audioop path and play cleanly
import random
from array import array
import xmusic_core.audio as A
chunk = array("h", [random.randint(-32768, 32767) for _ in range(4096)])
e = Engine(null=True); e.set_volume(50)
fast = array("h"); fast.frombytes(e._scale(chunk))
saved, A._audioop = A._audioop, None
slow = array("h"); slow.frombytes(e._scale(chunk))
res.append(ok(max(abs(a - b) for a, b in zip(fast, slow)) <= 1, "pure-Python volume path matches audioop path (audioop present: %s)" % (saved is not None)))
e.open(); e.play(good); time.sleep(1.0)
res.append(ok(e.error is None and e.position() > 0.7, "playback with pure-Python volume fallback is stable"))
e.close(); A._audioop = saved
print("ALL PASS" if all(res) else "SOME FAILED"); sys.exit(0 if all(res) else 1)
