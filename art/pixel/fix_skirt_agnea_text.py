"""Redraw the broken lower skirt of a_text.png: A-line to the ankles, curved hem, two shoes."""
import sys
from PIL import Image
src, dst = sys.argv[1:3]
im = Image.open(src).convert('RGBA'); px = im.load()
hx = lambda h: (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 255)
OR, MID, DK, SH, SHL = hx('#ba4e1b'), hx('#7b2e10'), hx('#3c1706'), hx('#0b0909'), hx('#363533')
for y in range(59, 80):
    for x in range(48):
        px[x, y] = (0, 0, 0, 0)
top, bot = 59, 67
L = lambda y: round(11 - 1.5 * (y - top) / (bot - top))
R = lambda y: round(33 + 4 * (y - top) / (bot - top))
for x in range(L(bot), R(bot) + 1):
    # hem curves: corners lift one row
    edge = min(x - L(bot), R(bot) - x)
    hem = bot - (1 if edge < 2 else 0)
    for y in range(top, hem + 1):
        if not L(y) <= x <= R(y):
            continue
        if x in (L(y), R(y)) or y == hem: c = DK
        elif y == hem - 1: c = MID
        elif x <= L(y) + 1 or x >= R(y) - 2: c = MID
        elif x in (19, 20) and y < hem - 2 or x == 27 and top + 1 < y < hem - 2: c = MID
        else: c = OR
        px[x, y] = c
for x0 in (16, 24):
    for x in range(x0, x0 + 6):
        px[x, 68] = SHL if 0 < x - x0 < 5 else SH
        px[x, 69] = SH
    for x in range(x0 + 1, x0 + 5):
        px[x, 70] = SH
im.save(dst)
