"""Turn a detailed sprite into an OT-style field sprite: area-downsample to ~37 px tall,
keep the painterly colours, harden alpha, add a dark coloured outline, show at 2x.

Usage: python ot_downsample.py in.png out.png [--height 37] [--head 1.0]
--head scales the top part (head) relative to the body before downsampling (chibi push).
"""
import argparse
import colorsys

from PIL import Image, ImageEnhance


def chibi(im, head_frac, scale):
    """Enlarge the top head_frac of the figure by scale, keeping the feet in place."""
    if scale == 1.0:
        return im
    w, h = im.size
    cut = int(h * head_frac)
    head, body = im.crop((0, 0, w, cut)), im.crop((0, cut, w, h))
    head = head.resize((int(w * scale), int(cut * scale)), Image.LANCZOS)
    out = Image.new('RGBA', (max(w, head.width), head.height + body.height), (0, 0, 0, 0))
    out.alpha_composite(body, ((out.width - w) // 2, head.height))
    out.alpha_composite(head, ((out.width - head.width) // 2, 0))
    return out


def outline(im, darken=0.35):
    px = im.load()
    w, h = im.size
    solid = lambda x, y: 0 <= x < w and 0 <= y < h and px[x, y][3] > 0
    out = im.copy()
    po = out.load()
    for y in range(h):
        for x in range(w):
            if not solid(x, y):
                continue
            if all(solid(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            r, g, b, _ = px[x, y]
            hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            r, g, b = colorsys.hsv_to_rgb(hh, min(1, s * 1.1), v * darken)
            po[x, y] = (int(r * 255), int(g * 255), int(b * 255), 255)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--height', type=int, default=37)
    ap.add_argument('--head', type=float, default=1.0)
    ap.add_argument('--head-frac', type=float, default=0.3)
    ap.add_argument('--sat', type=float, default=0.85)
    ap.add_argument('--contrast', type=float, default=1.1)
    a = ap.parse_args()
    im = Image.open(a.src).convert('RGBA')
    im = im.crop(im.getbbox())
    im = chibi(im, a.head_frac, a.head)
    # premultiply so transparent pixels don't bleed dark fringes into the average
    w = max(1, round(im.width * a.height / im.height))
    rgb = Image.new('RGBA', im.size, (0, 0, 0, 0))
    rgb.alpha_composite(im)
    small = rgb.resize((w, a.height), Image.BOX, reducing_gap=None)
    r, g, b, al = small.split()
    al = al.point(lambda v: 255 if v > 100 else 0)
    color = Image.merge('RGB', (r, g, b))
    color = ImageEnhance.Color(color).enhance(a.sat)
    color = ImageEnhance.Contrast(color).enhance(a.contrast)
    small = Image.merge('RGBA', (*color.split(), al))
    small = outline(small)
    small.save(a.dst)


if __name__ == '__main__':
    main()
