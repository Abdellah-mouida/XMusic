"""Filesystem scan, lazy ID3 metadata, folder tree."""
import os


class Track:
    __slots__ = ("path", "title", "artist", "album", "duration", "loaded", "bad", "_low")

    def __init__(self, path):
        self.path = path
        self.title = os.path.splitext(os.path.basename(path))[0]
        self.artist = ""
        self.album = ""
        self.duration = 0.0
        self.loaded = False
        self.bad = False
        self._low = None

    def haystack(self):
        if self._low is None:
            self._low = "\n".join((self.title, self.artist, self.album, os.path.basename(self.path))).lower()
        return self._low

    def load_meta(self):
        """Read ID3 + duration with mutagen. Never raises."""
        self.loaded = True
        self._low = None
        try:
            from mutagen.easyid3 import EasyID3
            from mutagen.mp3 import MP3
            try:
                m = MP3(self.path, ID3=EasyID3)
            except Exception:
                m = MP3(self.path)
            self.duration = float(m.info.length or 0)
            tags = m.tags
            if tags:
                def g(k):
                    try:
                        v = tags.get(k)
                        return str(v[0]).strip() if v else ""
                    except Exception:
                        return ""
                self.title = g("title") or self.title
                self.artist = g("artist")
                self.album = g("album")
        except Exception:
            pass          # malformed/missing metadata: keep filename title


def scan(root, errors=None):
    """Iteratively collect *.mp3 under root (no recursion limits, tolerant of errors)."""
    out, stack = [], [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.name.startswith("."):
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.name.lower().endswith(".mp3") and e.is_file():
                            out.append(Track(e.path))
                    except OSError:
                        continue
        except OSError as ex:
            if errors is not None:
                errors.append(str(ex))
    out.sort(key=lambda t: t.path.lower())
    return out


def build_tree(tracks, root):
    """dir -> (sorted subdir names, [tracks directly inside])."""
    tree = {}
    for t in tracks:
        d = os.path.dirname(t.path)
        tree.setdefault(d, [set(), []])[1].append(t)
        while d != root and len(d) > len(root):
            parent = os.path.dirname(d)
            tree.setdefault(parent, [set(), []])[0].add(os.path.basename(d))
            d = parent
    return {k: (sorted(v[0], key=str.lower), v[1]) for k, v in tree.items()}
