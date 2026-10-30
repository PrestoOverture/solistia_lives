# Scene Player Art, Step 4 — Side-Facing and Townspeople Sprites

**One job:** download Octopath Traveler II field sprites (the small pixel figures that walk around towns), as standing frames, to `assets/player/sprites/`. Don't redraw or edit pixels, except to crop a single frame from a sheet and keep its transparent background.

**Why:** the current sprites in that folder all face the camera, so a character can't turn toward the person they talk to; and every minor character uses the same girl.

**Sources:** The Spriters Resource (Octopath Traveler II field sprite sheets), the Octopath Traveler Fandom wiki, or other sites with the game's own sprites. Only the game's own art, from OT II if possible, OT I's townspeople if OT II has too few.

**What to get:**
1. **Travelers** (agnea, castti, hikari, ochette, osvald, partitio, temenos, throne): one standing frame facing the camera (`<name>.png`) and one standing frame seen from the side (`<name>_side.png`). Note whether the side frame faces left or right.
2. **Townspeople:** at least 6 different men and 6 different women (mixed ages and clothes: villagers, merchants, guards, elders, children are fine), each with a front frame and, if the sheet has one, a side frame: `minor_m1.png`, `minor_m1_side.png`, …, `minor_f1.png`, ….

Every frame is a whole figure, one person, uncropped feet, transparent background, at the game's pixel size (don't scale).

**Output:** the files above plus `assets/player/sprites/index.yaml` listing each file with `who` (traveler name, or `townsperson`), `sex` (`m`/`f`, townspeople only), `view` (`front` or `side`), `faces` (`left`/`right`, side frames only), and `source` (the page URL). Keep the existing `.webp` files.

When done, write `preprocess/player_4_report.md`: what you found per item, and anything missing and why.
