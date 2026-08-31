# -*- coding: utf-8 -*-
"""Generate cover.png (1200x630) and cover_wechat.png (900x383) for the
architecture book. Same visual system as the main book cover (dark blue
gradient + gold accents), text adapted. Uses Source Han Sans OTF fonts
located in the build/ directory."""

import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..'))

GOLD = (201, 164, 92)
LIGHT = (232, 237, 248)
MUTED = (150, 165, 195)
TOP = (18, 34, 74)
BOTTOM = (8, 22, 48)

F_BOLD = os.path.join(HERE, 'SourceHanSansSC-Bold.otf')
F_MED = os.path.join(HERE, 'SourceHanSansSC-Medium.otf')
F_REG = os.path.join(HERE, 'SourceHanSansSC-Regular.otf')


def gradient(draw, w, h):
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)


def center(draw, text, font, y, fill, w, spacing=0):
    if spacing:
        text = (' ' * spacing).join(list(text))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) / 2 - bbox[0], y), text, font=font, fill=fill)


def make_cover(w, h, out):
    img = Image.new('RGB', (w, h), TOP)
    d = ImageDraw.Draw(img)
    gradient(d, w, h)
    s = w / 1200.0  # scale factor relative to 1200x630 design

    def sc(px):
        return int(px * s)

    # top rule + series mark
    d.line([(sc(336), sc(88)), (sc(864), sc(88))], fill=GOLD, width=max(1, sc(2)))
    center(d, 'COGITO · SCRIBO', ImageFont.truetype(F_MED, sc(34)), sc(100), GOLD, w, spacing=2)
    # main title
    center(d, '架构解析', ImageFont.truetype(F_BOLD, sc(110)), sc(190), GOLD, w, spacing=2)
    # mid rule
    d.line([(sc(444), sc(365)), (sc(756), sc(365))], fill=GOLD, width=max(1, sc(3)))
    # subtitles
    center(d, '我思故我写 · 姊妹卷', ImageFont.truetype(F_MED, sc(32)), sc(385), LIGHT, w, spacing=1)
    center(d, '七套核心系统的工程实现', ImageFont.truetype(F_REG, sc(28)), sc(448), LIGHT, w)
    # footer
    center(d, 'wUwproject · CC BY-SA 4.0 · 免费公开', ImageFont.truetype(F_REG, sc(20)), sc(548), MUTED, w)

    img.save(out)
    print(f'OK {out} ({w}x{h})')


if __name__ == '__main__':
    make_cover(1200, 630, os.path.join(OUT, 'cover.png'))
    make_cover(900, 383, os.path.join(OUT, 'cover_wechat.png'))
