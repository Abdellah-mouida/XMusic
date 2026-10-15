"""Streaming MP3 playback on a miniaudio PlaybackDevice.

Callback contract (verified against miniaudio.py): the generator handed to
PlaybackDevice.start() must ALREADY be started (primed with next()), then each
.send(framecount) must return <= framecount frames of device-format PCM.  The old
crash ("can't send non-None value to just-started generator") is exactly an
un-primed generator.  Here one long-lived generator (_pcm) is primed once, and
tracks are swapped by replacing an immutable-ish _Stream object (no locks, no
closing generators from another thread).
"""
import sys
import time
import types
import warnings
from array import array

try:                                   # fast C volume scaling (stdlib <=3.12, `audioop-lts` on 3.13+)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import audioop as _audioop
except ImportError:                    # pure-Python fallback below is always available
    _audioop = None

SR, CH, BPF = 44100, 2, 4          # sample-rate, channels, bytes per frame (S16 stereo)
_MAX_SEND = 8192                   # miniaudio's stream buffer is 16384 frames


def backend_names() -> tuple:
    """Real audio backends to try, per platform (never the silent NULL backend)."""
    if sys.platform == "win32":
        return ("WASAPI", "DSOUND", "WINMM")
    if sys.platform == "darwin":
        return ("COREAUDIO",)
    return ("PULSEAUDIO", "ALSA", "JACK", "SNDIO", "OSS", "AUDIO4")      # PipeWire is served via PulseAudio


def _import_miniaudio():
    """miniaudio.py imports urllib.request at module level (~10 MB of ssl/http/email) purely for its
    internet-radio client, which XMusic never uses.  Import it with that module stubbed out."""
    if "miniaudio" in sys.modules:
        return sys.modules["miniaudio"]
    stub = "urllib.request" not in sys.modules
    if stub:
        sys.modules["urllib.request"] = types.ModuleType("urllib.request")
    try:
        import miniaudio
    finally:
        if stub:
            sys.modules.pop("urllib.request", None)
    return miniaudio


class _Stream:
    __slots__ = ("src", "pending", "played", "base", "done", "finished")

    def __init__(self, src, base, first):
        self.src, self.base = src, base
        self.pending = bytearray(first)
        self.played = 0
        self.done = False          # decoder exhausted
        self.finished = False      # decoder exhausted AND all audio handed to device


class Engine:
    def __init__(self, null=False):
        self.null = null
        self.volume = 70
        self.muted = False
        self._gain = 256
        self.set_volume(70)
        self.paused = False
        self.error = None
        self.backend = ""
        self.device = None
        self._cur = None
        self._ma = None
        self._gen = None
        self._quiet = None

    # ---------------------------------------------------------------- device
    def open(self):
        ma = _import_miniaudio()
        self._ma = ma
        B = ma.Backend
        if self.null:
            backends = [B.NULL]
        else:
            backends = [getattr(B, n) for n in backend_names() if hasattr(B, n)]
        self.device = ma.PlaybackDevice(output_format=ma.SampleFormat.SIGNED16, nchannels=CH,
                                        sample_rate=SR, buffersize_msec=120, backends=backends)
        self.backend = self.device.backend
        # The device is started lazily by play(): _start_device() primes a fresh generator
        # (first send() must be None) and starts it; idle_check() releases it again when silent.

    def close(self):
        self._cur = None
        d, self.device = self.device, None
        if d is not None:
            try:
                d.stop()
            except Exception:
                pass
            try:
                d.close()
            except Exception:
                pass

    # -------------------------------------------------------------- callback
    def _pcm(self):
        frames = yield b""
        while True:
            data = None
            try:
                data = self._fill(frames)
            except Exception as e:           # recorded, never re-raised into C
                self.error = "audio: %s" % e
                self._cur = None
            frames = yield data if data is not None else bytes(frames * BPF)

    def _fill(self, n):
        need = n * BPF
        cur = self._cur
        if cur is None or self.paused:
            return bytes(need)
        pend = cur.pending
        while len(pend) < need and not cur.done:
            want = min(_MAX_SEND, (need - len(pend)) // BPF) or 1
            try:
                chunk = cur.src.send(want)
            except StopIteration:
                cur.done = True
                break
            except Exception as e:           # mid-file decode error -> end track
                self.error = "decode: %s" % e
                cur.done = True
                break
            if not chunk:
                cur.done = True
                break
            pend += self._scale(chunk)
        take = min(len(pend), need)
        out = bytes(pend[:take])
        del pend[:take]
        cur.played += take // BPF
        if take < need:
            out += bytes(need - take)
        if cur.done and not pend:
            cur.finished = True
        return out

    def _scale(self, chunk):
        """Apply volume to an array('h') chunk, returning bytes."""
        g = self._gain
        if g >= 256:
            return chunk.tobytes()
        if _audioop is not None:
            return _audioop.mul(chunk.tobytes(), 2, g / 256.0)
        return array("h", [(s * g) >> 8 for s in chunk]).tobytes()

    # -------------------------------------------------- device power management
    def _start_device(self):
        d = self.device
        if d is not None and not d.running:
            self._gen = self._pcm()
            next(self._gen)                   # prime
            d.start(self._gen)

    def _stop_device(self):
        d = self.device
        if d is not None and d.running:
            d.stop()                          # blocks until the audio thread is quiescent

    def idle_check(self):
        """Release the audio device after 2s of silence (stopped or paused). Called from the UI loop."""
        d = self.device
        if d is None or not d.running:
            return
        if self._cur is not None and not self.paused:
            self._quiet = None
            return
        now = time.monotonic()
        if self._quiet is None:
            self._quiet = now
        elif now - self._quiet > 2.0:
            self._stop_device()
            self._quiet = None

    @property
    def device_running(self):
        return self.device is not None and self.device.running

    # ----------------------------------------------------------- controls
    def play(self, path, start=0.0, paused=False):
        """Open path (validated here, on the caller's thread) and start playing it."""
        ma = self._ma
        if ma is None:
            raise RuntimeError("audio device unavailable")
        sf = max(0, int(start * SR))
        src = ma.stream_file(path, output_format=ma.SampleFormat.SIGNED16, nchannels=CH,
                             sample_rate=SR, frames_to_read=4096, seek_frame=sf)
        first = src.send(4096)
        if not len(first):
            raise ValueError("no audio data")
        self.error = None
        self._start_device()
        self.paused = paused
        self._cur = _Stream(src, sf / SR, self._scale(first))
        self._quiet = None

    def stop(self):
        self._cur = None
        self.paused = False

    def toggle_pause(self):
        if self._cur is not None and not self._cur.finished:
            if self.paused:
                self._quiet = None
                self._start_device()
            self.paused = not self.paused

    def set_volume(self, v):
        self.volume = max(0, min(100, int(v)))
        self._update_gain()

    def set_muted(self, m):
        self.muted = bool(m)
        self._update_gain()

    def _update_gain(self):
        self._gain = 0 if self.muted else int(((self.volume / 100.0) ** 2) * 256)

    # -------------------------------------------------------------- queries
    def position(self):
        c = self._cur
        return 0.0 if c is None else c.base + c.played / SR

    @property
    def active(self):          # a track is loaded (playing, paused or draining)
        return self._cur is not None

    @property
    def playing(self):
        c = self._cur
        return c is not None and not self.paused and not c.finished

    @property
    def finished(self):
        c = self._cur
        return c is not None and c.finished
