# Scene Player Art, Step 2 — Stage Catalogs

**One job:** for each place in `assets/player/gallery/<place>/`, write a stage catalog, `assets/player/stages/<place>.yaml`, that says which spots a scene can happen at, which gallery image shows each spot, and where people can stand in that image. Don't edit or copy any image.

**Spots:** look at every image in the place's gallery (its `index.yaml` caption and file name help) and at the place's KB page (`kb/locations/**/<place>.md`). A spot is one view someone could have a conversation in: a square, the tavern, the tavern's upper floor, the library entrance, the well. Skip world-map views and *Champions of the Continent* images (`CotC_` files). For `oresrush`, use only present-day images, not Partitio's past timelines.

Per spot:
- `id` (snake_case), `name`, and `about`: one line saying what is there, from the image and the KB.
- `day`: the image file; `night`: an image of the **same view** at night, or `null`.
- `stand`: 3-6 points where a person could stand in the `day` image, on open ground, not on roofs, walls, or water, and spread so a group can talk. Each point is `x`, `y` (where the feet touch the ground) and `h` (a person's height at that spot, judged from the people already in the image), all as fractions of the image's width or height. If `night` is set, the points must also fit it.

Per place: `default`, the spot id for a scene with no spot: the place's main public view.

When done, write `preprocess/player_2_report.md`: per place, its spots and any image you couldn't use and why.
