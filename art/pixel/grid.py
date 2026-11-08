"""Zoomed view with a coordinate grid, and pixel edits by coordinate.

  python grid.py show in.png out.png [--k 20] [--crop x0,y0,x1,y1]
  python grid.py edit in.png out.png edits.txt

edits.txt, one per line ('#' comments):
  x,y #rrggbb        set a pixel
  x,y clear          make it transparent
  x,y x2,y2 copy     copy pixel (x2,y2) to (x,y)
  x,y dark 0.8       scale brightness of a pixel
"""
import colorsys
import sys

from PIL import Image, ImageDraw


def show(src, dst, k=20, crop=None):
    im = Image.open(src).convert('RGBA')
    if crop:
        im = im.crop(crop)
    ox, oy = crop[:2] if crop else (0, 0)
    w, h = im.size
    pad = 28
    out = Image.new('RGBA', (w * k + pad, h * k + pad), (95, 125, 85, 255))
    out.alpha_composite(im.resize((w * k, h * k), Image.NEAREST), (pad, pad))
    d = ImageDraw.Draw(out)
    for x in range(w + 1):
        d.line([(pad + x * k, pad), (pad + x * k, pad + h * k)], fill=(0, 0, 0, 70 if (x + ox) % 5 else 160))
        if x < w:
            d.text((pad + x * k + 3, 6), str(x + ox), fill=(255, 255, 255, 255))
    for y in range(h + 1):
        d.line([(pad, pad + y * k), (pad + w * k, pad + y * k)], fill=(0, 0, 0, 70 if (y + oy) % 5 else 160))
        if y < h:
            d.text((2, pad + y * k + 4), str(y + oy), fill=(255, 255, 255, 255))
    out.save(dst)


def edit(src, dst, edits):
    im = Image.open(src).convert('RGBA')
    px = im.load()
    for line in open(edits):
        parts = line.split()
        if not parts or parts[0].startswith('#'):
            continue
        x, y = map(int, parts[0].split(','))
        if parts[1] == 'clear':
            px[x, y] = (0, 0, 0, 0)
        elif len(parts) == 3 and parts[2] == 'copy':
            sx, sy = map(int, parts[1].split(','))
            px[x, y] = px[sx, sy]
        elif parts[1] == 'dark':
            r, g, b, a = px[x, y]
            hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            r, g, b = colorsys.hsv_to_rgb(hh, s, min(1, v * float(parts[2])))
            px[x, y] = (int(r * 255), int(g * 255), int(b * 255), a)
        else:
            c = parts[1].lstrip('#')
            px[x, y] = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    im.save(dst)


if __name__ == '__main__':
    cmd, src, dst = sys.argv[1:4]
    if cmd == 'show':
        args = sys.argv[4:]
        k = int(args[args.index('--k') + 1]) if '--k' in args else 20
        crop = tuple(map(int, args[args.index('--crop') + 1].split(','))) if '--crop' in args else None
        show(src, dst, k, crop)
    else:
        edit(src, dst, sys.argv[4])
