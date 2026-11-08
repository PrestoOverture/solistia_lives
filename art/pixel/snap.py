"""Recover true pixel art from an upscaled "pixel-art style" image (e.g. GPT image output).
The grid is not perfectly uniform there, so cell boundaries are found from colour edges per axis
instead of cutting at a fixed pitch; each cell takes the dominant colour of its centre.
The flat background (sampled from the corner) becomes transparent; figures are split into files.

Usage: python snap.py in.png out_prefix [--pitch 16]   (pitch: rough art-pixel size; guessed if omitted)
"""
import argparse

import numpy as np
from PIL import Image

from kcentroid import dominant


def edge_profile(a, axis):
    d = np.abs(np.diff(a, axis=axis)).sum(-1) > 30
    return d.sum(axis=1 - axis).astype(float)


def guess_pitch(a):
    d = np.abs(np.diff(a, axis=1)).sum(-1) > 30
    runs = np.concatenate([np.diff(np.where(row)[0]) for row in d[::5] if row.sum() > 2])
    runs = runs[runs > 4]
    return float(np.median(runs))


def boundaries(profile, pitch):
    """Edge positions: local maxima of the edge profile, spaced at least 0.6 pitch, gaps filled evenly."""
    n = len(profile) + 1
    order = np.argsort(-profile)
    taken = []
    for i in order:
        if profile[i] <= 0:
            break
        if all(abs(i - t) >= 0.6 * pitch for t in taken):
            taken.append(i)
    cuts = sorted([0] + [t + 1 for t in taken] + [n])
    out = [cuts[0]]
    for c in cuts[1:]:
        gap = c - out[-1]
        k = max(1, round(gap / pitch))
        out += [round(out[-1] + gap * j / k) for j in range(1, k + 1)]
    return sorted(set(out))


def snap(a, pitch):
    bx, by = boundaries(edge_profile(a, 1), pitch), boundaries(edge_profile(a, 0), pitch)
    bg = np.median(a[:8, :8].reshape(-1, 3), 0)
    rgba = np.dstack([a, np.where(np.abs(a - bg).sum(-1) > 60, 255, 0)]).astype(np.uint8)
    out = np.zeros((len(by) - 1, len(bx) - 1, 4), np.uint8)
    for j, (y0, y1) in enumerate(zip(by, by[1:])):
        for i, (x0, x1) in enumerate(zip(bx, bx[1:])):
            my, mx = (y1 - y0) // 4, (x1 - x0) // 4  # centre half of the cell, away from blended edges
            out[j, i] = dominant(rgba[y0 + my:y1 - my or y1, x0 + mx:x1 - mx or x1].reshape(-1, 4), 3)
    return out


def split(sprite):
    """Split a sheet into figures at fully transparent columns."""
    cols = sprite[..., 3].any(0)
    figs, x = [], 0
    while x < len(cols):
        if cols[x]:
            s = x
            while x < len(cols) and cols[x]:
                x += 1
            fig = sprite[:, s:x]
            rows = np.where(fig[..., 3].any(1))[0]
            figs.append(fig[rows[0]:rows[-1] + 1])
        x += 1
    return figs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out_prefix')
    ap.add_argument('--pitch', type=float)
    a = ap.parse_args()
    img = np.array(Image.open(a.src).convert('RGB')).astype(int)
    pitch = a.pitch or guess_pitch(img)
    for i, fig in enumerate(split(snap(img, pitch))):
        Image.fromarray(fig).save(f'{a.out_prefix}_{i}.png')
        print(f'{a.out_prefix}_{i}.png', fig.shape[1], 'x', fig.shape[0], 'pitch', round(pitch, 1))


if __name__ == '__main__':
    main()
