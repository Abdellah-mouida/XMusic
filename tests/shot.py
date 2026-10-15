"""Render the emulated terminal screen to a PNG (needs Pillow; used for README screenshots)."""
from PIL import Image, ImageDraw, ImageFont
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
CW, CH = 11, 22
def shot(s, path, bg="#080B12"):
    sc = s.screen; img = Image.new("RGB", (sc.columns * CW, sc.lines * CH), bg); d = ImageDraw.Draw(img)
    col = lambda c, dflt: ("#" + c) if c != "default" and len(c) == 6 else dflt
    for y in range(sc.lines):
        for x in range(sc.columns):
            ch = sc.buffer[y][x]; b = col(ch.bg, bg); f = col(ch.fg, "#E5EAF3")
            if b != bg: d.rectangle([x * CW, y * CH, (x + 1) * CW, (y + 1) * CH], fill=b)
            if ch.data != " ": d.text((x * CW, y * CH), ch.data, font=F, fill=f)
    img.save(path)
