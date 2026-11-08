"""Clean a set of frames of one character so they read as one hand-made sprite sheet:
a shared palette across all frames, specks removed, and a dark coloured outline
(each edge pixel takes a darkened tint of the colour inside it, like OT's sprites).

Usage: python clean.py out_dir frame.png [...] [--colors 48] [--keep 0.04] [--darken 0.4]
"""
import argparse
import colorsys
from pathlib import Path

import numpy as np
from PIL import Image

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N8 = N4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def oklab(rgb):
    c = np.asarray(rgb, float) / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    lms = c @ np.array([[0.4122, 0.2119, 0.0883], [0.5363, 0.6807, 0.2817], [0.0514, 0.1074, 0.6300]])
    return np.cbrt(lms) @ np.array([[0.2105, 1.9780, 0.0259], [0.7936, -2.4286, 0.7828], [-0.0041, 0.4506, -0.8087]])


def shared_palette(frames, n, keep=0.06):
    """K-means in OKLab over the distinct opaque colours of every frame, so small features
    (eyes, sleeves) weigh as much as big areas and hues don't collapse into grey."""
    cols = np.unique(np.concatenate([f[f[..., 3] > 127][:, :3] for f in frames]), axis=0).astype(float)
    lab = oklab(cols)
    centers = lab[np.linspace(0, len(lab) - 1, n).astype(int)]
    for _ in range(20):
        labels = ((lab[:, None] - centers[None]) ** 2).sum(-1).argmin(1)
        centers = np.array([lab[labels == i].mean(0) if (labels == i).any() else centers[i] for i in range(n)])
    # each palette entry is a real source colour (the one nearest its cluster centre)
    pal = cols[((lab[:, None] - centers[None]) ** 2).sum(-1).argmin(0)]
    for c, l in zip(cols, lab):
        if ((oklab(pal) - l) ** 2).sum(1).min() > keep ** 2:
            pal = np.vstack([pal, c])
    return np.unique(pal, axis=0).astype(int)


def remap(a, pal):
    out = a.copy()
    solid = a[..., 3] > 127
    lab = oklab(a[solid][:, :3])
    out[solid, :3] = pal[((lab[:, None] - oklab(pal)[None]) ** 2).sum(-1).argmin(1)]
    out[..., 3] = np.where(solid, 255, 0)
    out[~solid] = 0
    return out


def despeck(a):
    h, w = a.shape[:2]
    out = a.copy()
    inside = lambda x, y: 0 <= x < w and 0 <= y < h
    for y in range(h):
        for x in range(w):
            nb = [a[y + dy, x + dx] for dx, dy in N4 if inside(x + dx, y + dy)]
            solid_nb = [n for n in nb if n[3]]
            if a[y, x, 3] and not solid_nb:
                out[y, x] = 0  # lone opaque pixel
            elif not a[y, x, 3] and len(solid_nb) == 4:
                out[y, x] = solid_nb[0]  # pinhole
            elif a[y, x, 3]:
                ring = [tuple(a[y + dy, x + dx]) for dx, dy in N8 if inside(x + dx, y + dy)]
                if len(ring) == 8 and len(set(ring)) == 1 and ring[0] != tuple(a[y, x]) and ring[0][3]:
                    out[y, x] = ring[0]  # one-pixel colour speck
    return out


def tint(rgb, darken):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    r, g, b = colorsys.hsv_to_rgb(h, min(1, s * 1.15), v * darken)
    return int(r * 255), int(g * 255), int(b * 255)


def outline(a, darken):
    """Edge pixels become a dark tint of the nearest interior colour, so the line follows each material."""
    h, w = a.shape[:2]
    out = a.copy()
    solid = lambda x, y: 0 <= x < w and 0 <= y < h and a[y, x, 3]
    for y in range(h):
        for x in range(w):
            if not solid(x, y) or all(solid(x + dx, y + dy) for dx, dy in N4):
                continue
            inner = [a[y + dy, x + dx, :3] for dx, dy in N8 if solid(x + dx, y + dy)
                     and all(solid(x + dx + ex, y + dy + ey) for ex, ey in N4)]
            # skip near-black interiors (shoes, bodice): their line stays as it is
            inner = [c for c in inner if max(c) > 60]
            if inner:
                base = max(inner, key=lambda c: int(c.sum()))
                out[y, x, :3] = tint(base, darken)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('frames', nargs='+')
    ap.add_argument('--colors', type=int, default=48)
    ap.add_argument('--keep', type=float, default=0.04)
    ap.add_argument('--darken', type=float, default=0.4)
    a = ap.parse_args()
    frames = [np.array(Image.open(f).convert('RGBA')) for f in a.frames]
    pal = shared_palette(frames, a.colors, a.keep)
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    for path, f in zip(a.frames, frames):
        f = outline(despeck(remap(f, pal)), a.darken)
        Image.fromarray(f).save(Path(a.out_dir) / Path(path).name)


if __name__ == '__main__':
    main()
