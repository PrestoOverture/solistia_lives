"""Cut a generated turnaround sheet (front, left, right, back on a flat background) into
transparent sprites for the player: sprites/<who>_<view>.png, all views at one scale.

Usage: python cutout.py sheet.png who out_dir [--scale 0.5] [--views front,left,right,back]
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def key_mask(a, tolerance=48, pocket=1500, strict=24):
    """Figure pixels. Background is background-coloured area connected to the border, plus enclosed
    background-coloured pockets bigger than `pocket` px (gaps between arm and body); smaller
    pockets are costume (grey-blue cuffs) and stay."""
    bg = np.median(np.concatenate([a[:6, :6], a[:6, -6:], a[-6:, :6], a[-6:, -6:]]).reshape(-1, 3), 0)
    like = Image.fromarray((np.abs(a - bg).sum(-1) <= tolerance).astype(np.uint8) * 255)
    from PIL import ImageDraw
    w, h = like.size
    px = like.load()
    for x, y in [(x, 0) for x in range(0, w, 7)] + [(x, h - 1) for x in range(0, w, 7)] \
            + [(0, y) for y in range(0, h, 7)] + [(w - 1, y) for y in range(0, h, 7)]:
        if px[x, y] == 255:
            ImageDraw.floodfill(like, (x, y), 100)
    arr = np.array(like)
    background = arr == 100
    for y, x in zip(*np.where(arr == 255)):
        if like.getpixel((int(x), int(y))) != 255:
            continue
        ImageDraw.floodfill(like, (int(x), int(y)), 50)
        region = np.array(like) == 50
        if region.sum() > pocket:
            background |= region
        like.paste(1, mask=Image.fromarray(region.astype(np.uint8) * 255))
    # pockets that are the flat background colour itself (green specks inside hair) go regardless of size
    background |= np.abs(a - bg).sum(-1) <= strict
    mask = Image.fromarray((~background).astype(np.uint8) * 255)
    # drop the 1px fringe that still carries background tint
    mask = mask.filter(ImageFilter.MinFilter(3))
    return np.array(mask) > 127


def figures(mask, min_width=20):
    """Column spans holding a figure, split at empty columns."""
    cols = mask.any(0)
    spans, x = [], 0
    while x < len(cols):
        if cols[x]:
            start = x
            while x < len(cols) and cols[x]:
                x += 1
            if x - start >= min_width:
                spans.append((start, x))
        x += 1
    return spans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sheet')
    ap.add_argument('who')
    ap.add_argument('out_dir')
    ap.add_argument('--scale', type=float, default=0.5)
    ap.add_argument('--views', default='front,left,right,back')
    a = ap.parse_args()
    rgb = np.array(Image.open(a.sheet).convert('RGB')).astype(int)
    mask = key_mask(rgb)
    spans = figures(mask)
    views = a.views.split(',')
    if len(spans) != len(views):
        raise SystemExit(f'{a.sheet}: found {len(spans)} figures, expected {len(views)}')
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for view, (x0, x1) in zip(views, spans):
        rows = np.where(mask[:, x0:x1].any(1))[0]
        y0, y1 = rows[0], rows[-1] + 1
        rgba = np.dstack([rgb[y0:y1, x0:x1], mask[y0:y1, x0:x1] * 255]).astype(np.uint8)
        im = Image.fromarray(rgba)
        im = im.resize((max(1, round(im.width * a.scale)), max(1, round(im.height * a.scale))), Image.LANCZOS)
        alpha = im.getchannel('A').point(lambda v: 255 if v > 128 else 0)
        im.putalpha(alpha)
        im.save(out / f'{a.who}_{view}.png')
        print(out / f'{a.who}_{view}.png', im.size)


if __name__ == '__main__':
    main()
