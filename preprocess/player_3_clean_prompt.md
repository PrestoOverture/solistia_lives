# Scene Player Art, Step 3 — Clean Images

**One job:** for every image named as `day` or `night` in `assets/player/stages/*.yaml`, make a cleaned copy with Gemini image editing at `assets/player/clean/<place>/<same file name>`. Don't change or move the originals in `assets/player/gallery/`, and don't edit the stage catalogs.

**Remove:**
- The game's travelers: the 8 playable characters (Agnea, Throné, Hikari, Ochette, Castti, Osvald, Temenos, Partitio), and Ochette's companion beast. They usually stand together as the party in the middle of the view.
- Game UI: the round minimap or compass in a corner, "Change Time" or other button prompts, and speech or "..." bubbles over anyone's head.

Fill what was removed with the ground, wall, or floor around it, so it looks like no one stood there.

**Keep:** townspeople, animals other than Ochette's companion, buildings, props, lighting, depth-of-field blur, and the image's size (1280×720) and pixel-art style. Change nothing else.

If an image can't be cleaned without visible damage, keep the copy you have and say so in the report.

When done, write `preprocess/player_3_report.md`: per place, each cleaned file, what was removed, and any problem.
