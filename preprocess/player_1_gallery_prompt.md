# Scene Player Art, Step 1 — Pull Location Galleries

**One job:** download every image in the **Gallery** section of each place's page on the Octopath Traveler Fandom wiki, with its caption. Don't edit, crop, rename, or choose between images; later steps do that.

**Source:** `https://octopathtraveler.fandom.com/api.php`. Find the Gallery's files with `action=parse&prop=text` (or `prop=images`, keeping only the Gallery's files), and get each file's full-resolution URL with `action=query&prop=imageinfo&iiprop=url`.

**Places** (folder name → wiki page title):

conning_creek → Conning Creek · crackridge → Crackridge · cropdale → Cropdale · festival_grounds → Festival Grounds · flamechurch → Flamechurch · merry_hills → Merry Hills · merry_hills_shrine_entrance → Merry Hills: Shrine Entrance · montwise → Montwise · new_delsta → New Delsta · new_delsta_theater → New Delsta: Theater · oresrush → Oresrush · southern_oresrush_wilds → Southern Oresrush Wilds · western_crackridge_wilds → Western Crackridge Wilds

**Output:** `assets/player/gallery/<folder>/`, each image under its wiki file name, plus `index.yaml` listing, in Gallery order, each image's `file`, `wiki_url` (its File: page), and `caption` (empty if none). A page with no Gallery gets `images: []` and a `note`.

Write nothing outside `assets/player/gallery/` except a short report, `preprocess/player_1_report.md`: per place, the image count and any problem.
