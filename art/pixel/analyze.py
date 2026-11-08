"""Measure pixel-sprite style: size, palette, outline, shading, noise.

Usage: python analyze.py sprite.png [...]
"""
import colorsys
import sys

from PIL import Image


def stats(path):
    im = Image.open(path).convert('RGBA')
    im = im.crop(im.getbbox())
    w, h = im.size
    px = im.load()
    solid = lambda x, y: 0 <= x < w and 0 <= y < h and px[x, y][3] > 127
    cells = [(x, y) for y in range(h) for x in range(w) if solid(x, y)]
    colors = {px[x, y][:3] for x, y in cells}
    edge = [(x, y) for x, y in cells if not all(solid(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    hsv = lambda c: colorsys.rgb_to_hsv(*(v / 255 for v in c))
    edge_v = sorted(hsv(px[x, y][:3])[2] for x, y in edge)
    body_v = sorted(hsv(px[x, y][:3])[2] for x, y in cells)
    sat = sorted(hsv(px[x, y][:3])[1] for x, y in cells)
    black = sum(1 for x, y in edge if max(px[x, y][:3]) < 40) / len(edge)
    # noise: share of pixels whose 4 neighbours all differ in colour
    lonely = sum(1 for x, y in cells if all(not solid(x + dx, y + dy) or px[x + dx, y + dy][:3] != px[x, y][:3]
                                             for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))) / len(cells)
    mid = lambda v: v[len(v) // 2]
    return dict(size=f'{w}x{h}', fill=round(len(cells) / (w * h), 2), colors=len(colors),
                edge_v=round(mid(edge_v), 2), edge_black=round(black, 2), body_v=round(mid(body_v), 2),
                sat=round(mid(sat), 2), lonely=round(lonely, 2))


if __name__ == '__main__':
    for path in sys.argv[1:]:
        print(path.rsplit('/', 1)[-1].ljust(34), stats(path))
