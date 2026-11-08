# Original art (public build)

Everything here is original artwork made for this project. No game assets are included. The public site serves only these files.

- `sprites/`: field sprites of every person in the two showcase worlds. Each one has four views (front, left, right, back) in one house style. They were made with GPT image generation through the Codex CLI. The style references were earlier generated sheets, and the in-game sprites served only as design references for the travelers. `art/pixel/cutout.py` cut them out. A top margin sets each person's relative height. Where a generated "left" view faced the wrong way (Fennec, Hikari, Kieran), the left view is the mirrored right view.
- `clean/<place>/`: stage backdrops, also generated through the Codex CLI. Each night version is an edit of the day image with the same layout.
- `stages/*.yaml`: stage catalogs for these backdrops (spots and stand points). They have the same format as `assets/player/stages/`.

The art for the travelers depicts characters from *Octopath Traveler II* (© Square Enix) as fan art. This is an unofficial fan project, not affiliated with or endorsed by Square Enix.
