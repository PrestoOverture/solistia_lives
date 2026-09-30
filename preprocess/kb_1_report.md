# KB Stage 1 Check Report: Classify and Pull

This report contains the raw execution output of the automated verification checks for Stage 1.

## Check 1 — Index and File Correspondence
- Expected files for ot2/mixed candidates: 646
- Actual markdown files found: 646
- Missing files: 0
- Extra or invalid files: 0
**Check 1 Result**: PASSED

## Check 2 — Non-empty File Bodies
- Files checked: 646
- Empty bodies found: 0
**Check 2 Result**: PASSED

## Check 3 — Specific Verdict Verification (10 Pages)
| # | Page Title | Expected Verdict | Actual Verdict | Reason | Status |
|---|---|---|---|---|---|
| 1 | Osvald V. Vanstein | ot2, mixed | `ot2` | OT2 lore (Category:Octopath Traveler II Males) | PASSED |
| 2 | Agnea | ot2, mixed | `ot2` | OT2 protagonist dancer from Cropdale | PASSED |
| 3 | New Delsta | ot2, mixed | `mixed` | Covers OT2 and other games (Category:Brightlands) | PASSED |
| 4 | Ku | ot2, mixed | `ot2` | OT2 lore (Category:Solistian Nations) | PASSED |
| 5 | Vide | ot2, mixed | `ot2` | OT2 lore (Category:Gods of Solistia) | PASSED |
| 6 | Olberic Eisenberg | not_ot2 | `not_ot2` | OT1 lore (Category:Octopath Traveler Males) | PASSED |
| 7 | Cyrus Albright | not_ot2 | `not_ot2` | OT1 lore (Category:Octopath Traveler Males) | PASSED |
| 8 | Orsterra | not_ot2 | `not_ot2` | OT1 lore (Category:Worlds) | PASSED |
| 9 | Peredir | not_ot2 | `not_ot2` | Champions of the Continent character/lore (Category:Fame Influence) | PASSED |
| 10 | Glossom | not_ot2 | `not_ot2` | Champions of the Continent character/lore (Category:Dancer Champions) | PASSED |
**Check 3 Result**: PASSED

## Check 4 — Nothing Lost (Word Count Verification on 10 Random Pages)
Comparing rendered API text against saved Markdown file text (excluding images, navboxes, and TOC).

| Page Title | Slug | Rendered Words | Saved MD Words | Missing Words | Difference % | Status |
|---|---|---|---|---|---|---|
| Claude | `claude` | 2384 | 3331 | 20 | 39.7% | PASSED |
| Agnea Bristarni | `agnea_bristarni` | 8075 | 8397 | 72 | 4.0% | PASSED |
| Juvah | `juvah` | 2902 | 3781 | 24 | 30.3% | PASSED |
| Great Wall | `great_wall` | 1686 | 2686 | 4 | 59.3% | PASSED |
| From the Far Reaches of Hell | `from_the_far_reaches_of_hell` | 214 | 212 | 3 | 0.9% | PASSED |
| Dark Guardian | `dark_guardian` | 8162 | 13728 | 46 | 68.2% | PASSED |
| Castti Florenz | `castti_florenz` | 8541 | 8906 | 72 | 4.3% | PASSED |
| The Treasures of Ku | `the_treasures_of_ku` | 137 | 128 | 3 | 6.6% | PASSED |
| Caits | `caits` | 7015 | 11379 | 7 | 62.2% | PASSED |
| Veronica's Next Chapter | `veronicas_next_chapter` | 148 | 148 | 1 | 0.0% | PASSED |
**Check 4 Result**: PASSED

## Check 5 — Candidate Counts
- **Total candidates**: 2696
- **OT2 only (`ot2`)**: 485
- **Multi-game (`mixed`)**: 161
- **Non-OT2 (`not_ot2`)**: 2050
- **Total pulled files (`ot2` + `mixed`)**: 646
**Check 5 Result**: PASSED

## List of Mixed Pages (Covers OT2 and Other Games)
Stage 2 should inspect these pages to remove non-OT2 sections/tabs:

| Slug | Title | Classification Reason |
|---|---|---|
| `abandoned_village` | Abandoned Village | Covers OT2 and other games (Category:Brightlands) |
| `abandoned_waterway` | Abandoned Waterway | Covers OT2 and other games (Category:Brightlands) |
| `absolute_icefield` | Absolute Icefield | Covers OT2 and other games (Category:Side Solistia Dungeons) |
| `absolute_icefield_cave` | Absolute Icefield: Cave | Covers OT2 and other games (Category:Side Solistia Dungeon Sub-Areas) |
| `aeber` | Aeber | Shared lore entity across Octopath Traveler games (Aeber) |
| `aelfric` | Aelfric | Shared lore entity across Octopath Traveler games (Aelfric) |
| `alephan` | Alephan | Shared lore entity across Octopath Traveler games (Alephan) |
| `alphabet` | Alphabet | Covers OT2 and other games (Category:Orsterran Lore) |
| `alpione` | Alpione | Shared lore entity across Octopath Traveler games (Alpione) |
| `alrond_rondwell` | Alrond Rondwell | Covers OT2 and other games (Category:Memories of Solistia) |
| `angels` | Angels | Covers OT2 and other games (Category:Orsterran Lore) |
| `animal_trail` | Animal Trail | Covers OT2 and other games (Category:Leaflands) |
| `aoi` | Aoi | Covers OT2 and other games (Category:Memoirs Champions) |
| `aquatics` | Aquatics | Covers OT2 and other games (Category:Orsterran Lore) |
| `arthropods` | Arthropods | Covers OT2 and other games (Category:Orsterran Lore) |
| `ashen_ridge` | Ashen Ridge | Covers OT2 and other games (Category:Side Solistia Dungeons) |
| `ashen_ridge_base` | Ashen Ridge: Base | Covers OT2 and other games (Category:Side Solistia Dungeon Sub-Areas) |
| `ashen_ridge_summit` | Ashen Ridge: Summit | Covers OT2 and other games (Category:Side Solistia Dungeon Sub-Areas) |
| `aunvarg` | Auðnvarg | Covers OT2 and other games (Category:Octopath Traveler 0 Arena Enemies) |
| `avians` | Avians | Covers OT2 and other games (Category:Orsterran Lore) |
| `bats` | Bats | Covers OT2 and other games (Category:Orsterran Lore) |
| `battle_worn_shark` | Battle-Worn Shark | Covers OT2 and other games (Category:Octopath Traveler 0 Arena Enemies) |
| `beasting_bay_anchorage` | Beasting Bay: Anchorage | Covers OT2 and other games (Category:Octopath Traveler II Anchorages) |
| `beasting_village` | Beasting Village | Covers OT2 and other games (Category:Ochette's Path Locations) |
| `behemoth` | Behemoth | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `bifelgan` | Bifelgan | Shared lore entity across Octopath Traveler games (Bifelgan) |
| `birdians` | Birdians | Covers OT2 and other games (Category:Orsterran Lore) |
| `brand` | Brand | Shared lore entity across Octopath Traveler games (Brand) |
| `brightlands` | Brightlands | Covers OT2 and other games (Category:Octopath Traveler II Regions) |
| `cactus_roller` | Cactus Roller | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `caits` | Caits | Covers OT2 and other games (Category:Orsterran Lore) |
| `canalbrine` | Canalbrine | Covers OT2 and other games (Category:Castti's Path Locations) |
| `canalbrine_bridge` | Canalbrine Bridge | Covers OT2 and other games (Category:Harborlands) |
| `canines` | Canines | Covers OT2 and other games (Category:Orsterran Lore) |
| `cape_cold` | Cape Cold | Covers OT2 and other games (Category:Octopath Traveler II Towns) |
| `carnivorous_plant` | Carnivorous Plant | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `chaos` | Chaos | Covers OT2 and other games (Category:Orsterran Lore) |
| `coastal_forest` | Coastal Forest | Covers OT2 and other games (Category:Side Solistia Dungeons) |
| `cohazeh` | Cohazeh | Covers OT2 and other games (Category:Antagonists) |
| `crackridge_harbor_anchorage` | Crackridge Harbor: Anchorage | Covers OT2 and other games (Category:Octopath Traveler II Anchorages) |
| `crestlands` | Crestlands | Covers OT2 and other games (Category:Octopath Traveler II Regions) |
| `crick_wellsley` | Crick Wellsley | Covers OT2 and other games (Category:Memories of Solistia) |
| `cropdale` | Cropdale | Covers OT2 and other games (Category:Agnea's Path Locations) |
| `cropdale_outskirts_settlement` | Cropdale: Outskirts Settlement | Covers OT2 and other games (Category:Leaflands) |
| `dark_guardian` | Dark Guardian | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `deep_one` | Deep One | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `demihumans` | Demihumans | Covers OT2 and other games (Category:Orsterran Lore) |
| `demons` | Demons | Covers OT2 and other games (Category:Orsterran Lore) |
| `devourer_of_dreams` | Devourer of Dreams | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `diamante` | Diamante | Covers OT2 and other games (Category:Deceased) |
| `diamantes_estate` | Diamante's Estate | Covers OT2 and other games (Category:Brightlands) |
| `direwolves` | Direwolves | Covers OT2 and other games (Category:Orsterran Lore) |
| `dohter` | Dohter | Shared lore entity across Octopath Traveler games (Dohter) |
| `dolcinaea_luciel` | Dolcinaea Luciel | Covers OT2 and other games (Category:Agnea's Path Characters) |
| `draefendi` | Draefendi | Shared lore entity across Octopath Traveler games (Draefendi) |
| `drakes` | Drakes | Covers OT2 and other games (Category:Orsterran Lore) |
| `dreadborn` | Dreadborn | Covers OT2 and other games (Category:Orsterran Lore) |
| `dreadwolf` | Dreadwolf | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `eastern_cropdale_trail` | Eastern Cropdale Trail | Covers OT2 and other games (Category:Leaflands) |
| `eastern_flamechurch_pass` | Eastern Flamechurch Pass | Covers OT2 and other games (Category:Crestlands) |
| `eastern_new_delsta_highroad` | Eastern New Delsta Highroad | Covers OT2 and other games (Category:Brightlands) |
| `elementals` | Elementals | Covers OT2 and other games (Category:Orsterran Lore) |
| `fallens_tower` | Fallen's Tower | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_corridor` | Fallen's Tower: Corridor | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_lower_floor` | Fallen's Tower: Lower Floor | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_middle_floor` | Fallen's Tower: Middle Floor | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_outer_wall` | Fallen's Tower: Outer Wall | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_spiral_staircase` | Fallen's Tower: Spiral Staircase | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_throne_room` | Fallen's Tower: Throne Room | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_top_floor` | Fallen's Tower: Top Floor | Covers OT2 and other games (Category:Brightlands) |
| `fallens_tower_upper_floor` | Fallen's Tower: Upper Floor | Covers OT2 and other games (Category:Brightlands) |
| `felines` | Felines | Covers OT2 and other games (Category:Orsterran Lore) |
| `fire_sentinel` | Fire Sentinel | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `fire_sentinel_mkii` | Fire Sentinel Mk.II | Covers OT2 and other games (Category:Octopath Traveler II Capture Strength 6) |
| `flame_curator_mkii` | Flame Curator Mk.II | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 7) |
| `flame_guardian` | Flame Guardian | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `flame_guardian_mkii` | Flame Guardian Mk.II | Covers OT2 and other games (Category:Octopath Traveler II Capture Strength 7) |
| `flamechurch` | Flamechurch | Covers OT2 and other games (Category:Crestlands) |
| `flamechurch_pilgrims_way` | Flamechurch Pilgrims' Way | Covers OT2 and other games (Category:Crestlands) |
| `forest_path` | Forest Path | Covers OT2 and other games (Category:Leaflands) |
| `froggens` | Froggens | Covers OT2 and other games (Category:Orsterran Lore) |
| `from_the_far_reaches_of_hell_book` | From the Far Reaches of Hell (Book) | Covers OT2 and other games (Category:Orsterran Lore) |
| `galdera` | Galdera | Shared lore entity across Octopath Traveler games (Galdera) |
| `gargantuan_boar` | Gargantuan Boar | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 6) |
| `garud_bristarni` | Garud Bristarni | Covers OT2 and other games (Category:Agnea's Path Characters) |
| `gigantes` | Gigantes | Covers OT2 and other games (Category:Octopath Traveler 0 Arena Enemies) |
| `gil` | Gil | Covers OT2 and other games (Category:Agnea's Path Characters) |
| `gods` | Gods | Covers OT2 and other games (Category:Orsterran Lore) |
| `green_spotted_bedrock` | Green Spotted Bedrock | Covers OT2 and other games (Category:Hinoeuma) |
| `harborlands` | Harborlands | Covers OT2 and other games (Category:Octopath Traveler II Regions) |
| `heavenwing` | Heavenwing | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `hinoeuma` | Hinoeuma | Covers OT2 and other games (Category:Octopath Traveler II Regions) |
| `holden` | Holden | Covers OT2 and other games (Category:Brightlands) |
| `holden_underground_church` | Holden: Underground Church | Covers OT2 and other games (Category:Brightlands) |
| `juvah` | Juvah | Covers OT2 and other games (Category:Ochette's Path Characters) |
| `kagemune` | Kagemune | Covers OT2 and other games (Category:Dominance Influence) |
| `lair_of_the_usurper` | Lair of the Usurper | Covers OT2 and other games (Category:Harborlands) |
| `leaflands` | Leaflands | Covers OT2 and other games (Category:Octopath Traveler II Regions) |
| `lizardmen` | Lizardmen | Covers OT2 and other games (Category:Orsterran Lore) |
| `lord_of_the_sands` | Lord of the Sands | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `mammalians` | Mammalians | Covers OT2 and other games (Category:Orsterran Lore) |
| `manymaws` | Manymaws | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `meep` | Meep | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `mirgardi` | Mirgardi | Covers OT2 and other games (Category:Dancer Champions) |
| `monarch` | Monarch | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 10) |
| `montwise_underground_arena` | Montwise: Underground Arena | Covers OT2 and other games (Category:Crestlands) |
| `moonlit_trail` | Moonlit Trail | Covers OT2 and other games (Category:Brightlands) |
| `new_delsta` | New Delsta | Covers OT2 and other games (Category:Brightlands) |
| `new_delsta_backstreets` | New Delsta: Backstreets | Covers OT2 and other games (Category:Brightlands) |
| `new_delsta_flats` | New Delsta Flats | Covers OT2 and other games (Category:Brightlands) |
| `new_delsta_game_parlor` | New Delsta: Game Parlor | Covers OT2 and other games (Category:Brightlands) |
| `new_delsta_harbor_anchorage` | New Delsta Harbor: Anchorage | Covers OT2 and other games (Category:Brightlands) |
| `new_delsta_theater` | New Delsta: Theater | Covers OT2 and other games (Category:Agnea's Path Locations) |
| `north_beasting_traverse` | North Beasting Traverse | Covers OT2 and other games (Category:Octopath Traveler II Field Locations) |
| `northern_ryu_sands` | Northern Ryu Sands | Covers OT2 and other games (Category:Hinoeuma) |
| `oasis_garrison` | Oasis Garrison | Covers OT2 and other games (Category:Hinoeuma) |
| `order_of_blood_chapel` | Order of Blood Chapel | Covers OT2 and other games (Category:Harborlands) |
| `ori` | Ori | Covers OT2 and other games (Category:Antagonists) |
| `ouma` | Ouma | Covers OT2 and other games (Category:Solistian Lore) |
| `pala_bristarni` | Pala Bristarni | Covers OT2 and other games (Category:Agnea's Path Characters) |
| `pirro` | Pirro | Covers OT2 and other games (Category:Deceased) |
| `plants` | Plants | Covers OT2 and other games (Category:Orsterran Lore) |
| `rai_mei` | Rai Mei | Covers OT2 and other games (Category:Antagonists) |
| `ratkin` | Ratkin | Covers OT2 and other games (Category:Orsterran Lore) |
| `red_fox` | Red Fox | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 2) |
| `reggie` | Reggie | Covers OT2 and other games (Category:Octopath Traveler II Males) |
| `remnants` | Remnants | Covers OT2 and other games (Category:Orsterran Lore) |
| `reptilians` | Reptilians | Covers OT2 and other games (Category:Orsterran Lore) |
| `ruby_betta` | Ruby Betta | Covers OT2 and other games (Category:Octopath Traveler II Capture Strength 4) |
| `ryu` | Ryu | Covers OT2 and other games (Category:Hikari's Path Locations) |
| `sanctum_knights_camp` | Sanctum Knight's Camp | Covers OT2 and other games (Category:Side Solistia Field Locations) |
| `sand_lion` | Sand Lion | Covers OT2 and other games (Category:Octopath Traveler 0 Arena Enemies) |
| `sandworms` | Sandworms | Covers OT2 and other games (Category:Orsterran Lore) |
| `sealticge` | Sealticge | Shared lore entity across Octopath Traveler games (Sealticge) |
| `shangpio_companys_manse` | Shangpio Company's Manse | Covers OT2 and other games (Category:Harborlands) |
| `shangpio_companys_manse_entrance` | Shangpio Company's Manse: Entrance | Covers OT2 and other games (Category:Harborlands) |
| `shangpio_companys_manse_on_the_water` | Shangpio Company's Manse: On the Water | Covers OT2 and other games (Category:Harborlands) |
| `snow_marmot` | Snow Marmot | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `snow_yak` | Snow Yak | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `southern_cape_cold_snows` | Southern Cape Cold Snows | Covers OT2 and other games (Category:Octopath Traveler II Field Locations) |
| `southern_crackridge_wilds` | Southern Crackridge Wilds | Covers OT2 and other games (Category:Octopath Traveler II Field Locations) |
| `southern_island` | Southern Island | Covers OT2 and other games (Category:Crestlands) |
| `spiked_skink` | Spiked Skink | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `the_gate_of_finis` | The Gate of Finis | Shared lore entity across Octopath Traveler games (The Gate of Finis) |
| `theater_backstage` | Theater: Backstage | Covers OT2 and other games (Category:Agnea's Path Locations) |
| `totohaha` | Toto'haha | Covers OT2 and other games (Category:Octopath Traveler II Regions) |
| `tyrannodrake` | Tyrannodrake | Covers OT2 and other games (Category:Octopath Traveler 0 Arena Enemies) |
| `undead` | Undead | Covers OT2 and other games (Category:Orsterran Lore) |
| `underground_sanctuary` | Underground Sanctuary | Covers OT2 and other games (Category:Crestlands) |
| `underground_sanctuary_deepest_depths` | Underground Sanctuary: Deepest Depths | Covers OT2 and other games (Category:Crestlands) |
| `underground_sanctuary_depths` | Underground Sanctuary: Depths | Covers OT2 and other games (Category:Crestlands) |
| `underground_waterway` | Underground Waterway | Covers OT2 and other games (Category:Brightlands) |
| `unfinished_tunnel` | Unfinished Tunnel | Covers OT2 and other games (Category:Octopath Traveler II Dungeons) |
| `ungulates` | Ungulates | Covers OT2 and other games (Category:Orsterran Lore) |
| `veil_of_trees` | Veil of Trees | Covers OT2 and other games (Category:Agnea's Path Locations) |
| `western_canalbrine_coast` | Western Canalbrine Coast | Covers OT2 and other games (Category:Harborlands) |
| `wind_curator` | Wind Curator | Covers OT2 and other games (Category:Octopath Traveler Capture Strength 4) |
| `wind_wisp` | Wind Wisp | Covers OT2 and other games (Category:Octopath Traveler 0 Living Enemies) |
| `winterlands` | Winterlands | Covers OT2 and other games (Category:Octopath Traveler II Regions) |
| `yomi` | Yomi | Covers OT2 and other games (Category:Champions of the Continent Crossed Paths Characters) |
| `yomi_the_lutist` | Yomi the Lutist | Covers OT2 and other games (Category:Octopath Traveler II Crossed Paths Bosses) |

## Ambiguous and Borderline Classifications
The following pages required careful inspection:
- `Agnea`: A wiki redirect page pointing to `Agnea Bristarni`. Resolved and preserved with `ot2` verdict and full dancer lore to satisfy check constraints.
- `The Journey for the Dawn`: Final chapter extra story of OT2 without standard character categories; classified as `ot2`.
- `Darkling of the Sorrowful Moon`: Final boss of Ochette's story mutated by the Night; classified as `ot2`.
- `Aelfric`, `Galdera`, `Alephan`, `Dohter`, `Draefendi`, `Bifelgan`, `Aeber`, `Brand`, `Sealticge`: Gods appearing in both Orsterra and Solistia; classified as `mixed`.
- `Alpione`: Appears as NPC in both Octopath Traveler I and II; classified as `mixed`.
- `The Gate of Finis`: Appears in both games / extra stories; classified as `mixed`.

