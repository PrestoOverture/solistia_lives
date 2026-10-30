# Scene Player Art, Step 5 — Re-pick Stand Points

**One job:** fix the `stand` points in `assets/player/stages/<place>.yaml` so that no traveler drawn on a point overlaps a townsperson who is still in the picture. Change only `stand` lists; don't edit images, spots, or anything else.

**Why:** the player draws a traveler as a sprite of height `h` (about 0.5 h wide) with its feet at (`x`, `y`). When that box overlaps a townsperson baked into the image, the traveler is painted over them, even if the townsperson stands in front.

**For each spot:** look at its clean images, `assets/player/clean/<place>/<day file>` and, if set, `<night file>`. Keep every point whose box (from x − 0.25 h to x + 0.25 h across, y − h to y down) is clear of townspeople in both images. Replace or drop the others: a new point must be on open walkable ground, keep the same `h` scale as the people near it, and the spot should keep 3–6 points spread so a group can talk. If a spot can't keep 3 clear points, keep the clearest ones and say so in the report.

When done, write `preprocess/player_5_report.md`: per spot, how many points you kept, moved, and dropped.
