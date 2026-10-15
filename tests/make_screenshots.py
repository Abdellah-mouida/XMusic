"""Regenerate docs/screenshots/*.png from the real app (needs: pip install pyte pillow; a test library in /tmp/Music2)."""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ptyrun import Session, ROOT
from shot import shot
from PIL import Image
OUT = os.path.join(ROOT, "docs", "screenshots"); os.makedirs(OUT, exist_ok=True)
BG = {"blue": "#080B12", "girly": "#1A1220", "yaru": "#1A1A1A", "amoled-blue": "#000000", "amoled-pink": "#000000", "violet": "#120B24"}
def sess(cols, rows, theme="blue", keys=""):
    shutil.rmtree("/tmp/xm_home", ignore_errors=True)
    s = Session(cols, rows, ["--music-dir", "/tmp/Music2", "--null-audio", "--theme", theme]); s.pump(1.6); s.send(keys, 1.4); return s
s = sess(80, 30, "blue", "/01 alpha\r\r"); shot(s, OUT + "/main.png", BG["blue"]); s.send("q"); s.wait_exit()
s = sess(80, 26, "violet", "e\x1b[Be\x1b[Be\x1b[BE\r3\x1b[B"); shot(s, OUT + "/queue.png", BG["violet"]); s.send("q"); s.wait_exit()
s = sess(80, 26, "blue", "/01 alpha\r\r"); s.send("t", 0.5); s.send("\x1b[B\x1b[B\x1b[B\x1b[B", 0.6); shot(s, OUT + "/theme-picker.png", BG["amoled-blue"]); s.send("q"); s.wait_exit()
s = sess(60, 16, "girly", "/01 alpha\r\r"); shot(s, OUT + "/compact.png", BG["girly"]); s.send("q"); s.wait_exit()
imgs = []
for t in BG:
    s = sess(80, 30, t, "/01 alpha\r\r"); shot(s, "/tmp/_t.png", BG[t]); imgs.append(Image.open("/tmp/_t.png").copy()); s.send("q"); s.wait_exit()
w, h = imgs[0].size; k = 0.55; tw, th = int(w * k), int(h * k)
m = Image.new("RGB", (tw * 2, th * 3))
for i, im in enumerate(imgs): m.paste(im.resize((tw, th), Image.LANCZOS), ((i % 2) * tw, (i // 2) * th))
m.save(OUT + "/themes.png"); print("wrote", sorted(os.listdir(OUT)))
