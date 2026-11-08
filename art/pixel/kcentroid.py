"""Pixel-art-aware downscale: each output pixel takes the dominant colour cluster of its block
instead of the block average, so edges and features stay crisp.

Usage: python kcentroid.py in.png out.png height [k]
"""
import sys

import numpy as np
from PIL import Image


def dominant(block, k):
    solid = block[block[:, 3] > 127]
    if len(solid) * 2 < len(block):
        return (0, 0, 0, 0)
    colors = solid[:, :3].astype(float)
    centers = colors[np.linspace(0, len(colors) - 1, min(k, len(colors))).astype(int)]
    for _ in range(6):
        labels = ((colors[:, None] - centers[None]) ** 2).sum(-1).argmin(1)
        centers = np.array([colors[labels == i].mean(0) if (labels == i).any() else centers[i] for i in range(len(centers))])
    best = np.bincount(labels, minlength=len(centers)).argmax()
    return (*centers[best].round().astype(int), 255)


def main():
    src, dst, height = sys.argv[1], sys.argv[2], int(sys.argv[3])
    k = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    im = Image.open(src).convert('RGBA')
    im = im.crop(im.getbbox())
    a = np.array(im)
    h, w = a.shape[:2]
    width = max(1, round(w * height / h))
    out = np.zeros((height, width, 4), np.uint8)
    for y in range(height):
        for x in range(width):
            block = a[y * h // height:(y + 1) * h // height, x * w // width:(x + 1) * w // width].reshape(-1, 4)
            out[y, x] = dominant(block, k)
    Image.fromarray(out).save(dst)


if __name__ == '__main__':
    main()
