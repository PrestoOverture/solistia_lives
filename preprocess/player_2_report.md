# Scene Player Art, Step 2 — Stage Catalogs Report

Built `assets/player/stages/<place>.yaml` for all 13 places (61 spots total, 5 exact same-view day/night pairs). No images were edited or copied.

## Summary by Place

| Place | Default Spot | Spots | Gallery Images Used | Unused Images |
| --- | --- | ---: | ---: | ---: |
| `conning_creek` | `town_center` | 4 | 4 / 5 | 1 |
| `crackridge` | `windmill_plaza` | 5 | 6 / 8 | 2 |
| `cropdale` | `village_square` | 7 | 8 / 11 | 3 |
| `festival_grounds` | `festival_clearing` | 3 | 3 / 3 | 0 |
| `flamechurch` | `chapel_hill` | 5 | 6 / 7 | 1 |
| `merry_hills` | `market_street` | 6 | 6 / 11 | 5 |
| `merry_hills_shrine_entrance` | `shrine_courtyard` | 4 | 5 / 8 | 3 |
| `montwise` | `town_square` | 7 | 7 / 12 | 5 |
| `new_delsta` | `main_street` | 5 | 5 / 9 | 4 |
| `new_delsta_theater` | `auditorium_aisle` | 3 | 3 / 7 | 4 |
| `oresrush` | `main_street` | 7 | 7 / 43 | 36 (33 past timelines + 3 present-day) |
| `southern_oresrush_wilds` | `wilds_trail` | 2 | 3 / 6 | 3 |
| `western_crackridge_wilds` | `merchants_guild` | 3 | 3 / 4 | 1 |
| **Total** | | **61** | **66 / 134** | **68** |

---

## Per-Place Breakdown

### 1. `conning_creek` (default: `town_center`)
- **Spots:**
  - `town_center` (*Town Center*): `Conning_Creek_Overview.jpg` (`night: null`, 5 stand points) — Cobblestone plaza facing the tavern terrace and the stone staircase up to the Guard Outpost.
  - `marketplace` (*Seafood Marketplace*): `Conning_Creek_Ochette.jpg` (`night: null`, 5 stand points) — Open-air harbor market with canvas stalls selling fresh fish, fruit baskets, and a covered wagon.
  - `guard_outpost_entrance` (*Guard Outpost Entrance*): `Conning_Creek_Guardhouse.jpg` (`night: null`, 5 stand points) — Broad stone staircase and iron gates leading up to the northern Guard Outpost garrison.
  - `flowerbed_courtyard` (*Flowerbed Courtyard*): `Conning_Creek_Flowerbed.jpg` (`night: null`, 5 stand points) — Quiet residential cottage yard in the lower quarter with a fenced flowerbed and outdoor dining table.
- **Unused Images:**
  - `Conning_Creek_Night.jpg`: Nighttime view of the marketplace panned ~30% east relative to `Conning_Creek_Ochette.jpg` (not the same camera view, and redundant with `marketplace`).

### 2. `crackridge` (default: `windmill_plaza`)
- **Spots:**
  - `windmill_plaza` (*Windmill Plaza*): `Crackridge_Entrance.jpg` (`night: null`, 5 stand points) — Main entrance plateau with the timber wind pump, the dark tome pedestal, and stone steps to the upper tier.
  - `chasm_overlook` (*Chasm Overlook*): `Crackridge_Chasm.jpg` (`night: null`, 5 stand points) — Timber platform jutting out over the foggy ravine where the legendary beast Tera slumbers.
  - `chasm_scaffolding` (*Chasm Scaffolding*): `Crackridge_Scaffolding.jpg` (`night: null`, 5 stand points) — Lower cliffside scaffolding platform with supply crates, barrels, and a ladder descending into the chasm.
  - `ridge_lookout` (*Ridge Lookout*): `Crackridge_View.jpg` (`night: Crackridge_View_Night.jpg`, 5 stand points) — Narrow rocky ridge jutting out between canyon walls toward the distant Wildlands peaks.
  - `inn_terrace` (*Inn & Apothecary Terrace*): `Moonshade_Order_Townspeople.jpg` (`night: null`, 5 stand points) — Upper cliffside terrace outside the Crackridge Inn and Apothecary where townspeople gather by torchlight.
- **Unused Images:**
  - `Crackridge.jpg`: Alternate night angle of the upper inn wooden deck, redundant with `inn_terrace`.
  - `Crackridge_Overview.jpg`: Overlapping daytime angle of the entrance plateau shifted slightly east toward the armory, redundant with `windmill_plaza`.

### 3. `cropdale` (default: `village_square`)
- **Spots:**
  - `village_square` (*Village Square*): `Cropdale.jpg` (`night: null`, 6 stand points) — Cropdale's sunlit center with stone steps descending past festival canopies toward the village tavern.
  - `watermill_bridge` (*Watermill Bridge*): `Cropdale_Bridge_Day.jpg` (`night: Cropdale_Bridge.jpg`, 6 stand points) — Arched stone bridge crossing the lily-covered village stream beside the waterwheel cottage.
  - `agnea_house_exterior` (*Agnea's House Exterior*): `Cropdale_Agnea's_House.jpg` (`night: null`, 5 stand points) — Thatched-roof Bristarni cottage with drying woven textiles, flower trellises, and garden steps.
  - `agnea_house_interior` (*Agnea's House Interior*): `Cropdale_Agnea's_House_Interior.jpg` (`night: null`, 5 stand points) — Warm interior of the Bristarni home with woven rugs, beds, dining table, and stone fireplace.
  - `garud_workshop` (*Garud's Room*): `Cropdale_Garud's_Room.jpg` (`night: null`, 5 stand points) — Garud's tailor and weaving room inside the Bristarni house, equipped with an upright loom and yarn spools.
  - `tavern` (*Cropdale Tavern*): `Cropdale_Tavern.jpg` (`night: null`, 5 stand points) — Lively village tavern interior with a raised wooden performance stage, bar counter, and patron tables.
  - `hog_farm` (*Hog Farm*): `Cropdale_Swine.jpg` (`night: null`, 5 stand points) — Thatched farmstead on Cropdale's northeastern edge where prized pigs graze in a fenced yard.
- **Unused Images:**
  - `Cropdale_Entrance.jpg`: Overlapping view of the watermill bridge and save point, redundant with `watermill_bridge`.
  - `Cropdale_Temenos.jpg`: Overlapping view of the watermill cottage garden and bridge, redundant with `watermill_bridge`.
  - `Cropdale_Intro.jpg`: Distant wide-angle nocturnal overview of the lower village rather than a close conversational spot.

### 4. `festival_grounds` (default: `festival_clearing`)
- **Spots:**
  - `festival_clearing` (*Festival Clearing*): `Festival_Grounds_Crowd.jpg` (`night: null`, 6 stand points) — Woodland clearing before the raised wooden stage, flanked by food stalls, pavilion tent, and stools.
  - `entrance_path` (*Entrance Path*): `Festival_Grounds_Banners.jpg` (`night: null`, 5 stand points) — Wooded trail lined with rustic log fences, wreath banners, and overhead bunting leading to the clearing.
  - `dance_stage` (*Dance Stage*): `Festival_Grounds_Agnea.jpg` (`night: null`, 5 stand points) — Raised wooden festival stage lit by torches and decorated with flower boxes and painted castle scenery.
- **Unused Images:** None (all 3 gallery images used).

### 5. `flamechurch` (default: `chapel_hill`)
- **Spots:**
  - `chapel_hill` (*Chapel Hill*): `Flamechurch_Hill.jpg` (`night: null`, 6 stand points) — Cobblestone plaza atop the hill directly before the town chapel and neighboring stone cottage.
  - `chapel` (*Town Chapel*): `Flamechurch_Chapel.jpg` (`night: Flamechurch_Chapel_Night.jpg`, 6 stand points) — Sanctuary interior with stained-glass windows, a pipe organ, wooden pews, and Pontiff Jörg's portrait.
  - `town_square` (*Town Square*): `Flamechurch_Temenos_and_Throne.jpg` (`night: null`, 6 stand points) — Central village terrace with twin Sacred Flame braziers, the roofed water well, and the inn.
  - `tavern_lane` (*Tavern Lane*): `Flamechurch_Town_Night.jpg` (`night: null`, 5 stand points) — Cobblestone lane outside the timber-framed Flamechurch tavern, lit by a brazier beside stacked crates.
  - `chapel_steps` (*Chapel Steps Terrace*): `Flamechurch_Night.jpg` (`night: null`, 5 stand points) — Stone terrace at the foot of the chapel staircase with a wooden bench, handcart, and market stalls.
- **Unused Images:**
  - `Flamechurch_Vista.jpg`: Distant scenic vista of Flamechurch Cathedral high on the mountains over blurred rooftops; no walkable ground.

### 6. `merry_hills` (default: `market_street`)
- **Spots:**
  - `market_street` (*Market Street*): `Merry_Hills.jpg` (`night: null`, 6 stand points) — Bustling cobblestone thoroughfare lined with festival awnings, merchant stalls, and street performers.
  - `tavern_yard` (*Tavern Yard*): `Merry_Hills_Tavern.jpg` (`night: null`, 5 stand points) — Stone terrace outside the rustic cliffside tavern where an elderly actor performs.
  - `great_bridge` (*Great Bridge*): `Merry_Hills_Bridge.jpg` (`night: null`, 5 stand points) — High stone bridge spanning the town gorge, hung with sun-and-moon tapestries.
  - `inn_terrace` (*Inn & Grocer Terrace*): `Merry_Hills_Stairs.jpg` (`night: null`, 5 stand points) — Hillside cobblestone terrace outside the Merry Hills inn and vegetable grocer.
  - `town_entrance` (*Town Entrance*): `Merry_Hills_Entrance.jpg` (`night: null`, 5 stand points) — Broad stone staircase climbing from the western mountain pass into the festival promenade.
  - `hillside_path` (*Hillside Path*): `Merry_Hills_Descent.jpg` (`night: null`, 5 stand points) — Terraced path winding below the great bridge arches past stone cottages and autumn trees.
- **Unused Images:**
  - `Merry_Hills_Agnea.jpg`: Identical camera view to `Merry_Hills.jpg` captured during Agnea's Chapter 5 cutscene.
  - `Merry_Hills_Center.jpg`: Overlapping view of the market thoroughfare a few steps north of `Merry_Hills.jpg`.
  - `Merry_Hills_Market.jpg`: Overlapping view of the upper market stalls redundant with `market_street`.
  - `Merry_Hills_Market_Evening.jpg`: Another overlapping angle along the upper market stalls (different camera position from `Merry_Hills_Market.jpg`, so not a same-view night pair).
  - `Merry_Hills_Pennant.jpg`: Overlapping transition view of the stair landing and notice board adjacent to `inn_terrace`.

### 7. `merry_hills_shrine_entrance` (default: `shrine_courtyard`)
- **Spots:**
  - `shrine_courtyard` (*Shrine Courtyard*): `Merry_Hills_Shrine_Entrance.jpg` (`night: Merry_Hills_Shrine_Entrance_Night.jpg`, 6 stand points) — Ceremonial stone avenue and amphitheater steps flanked by marble maiden statues and braziers.
  - `shrine_portal` (*Shrine Portal*): `Merry_Hills_Shrine_Entrance_Center.jpg` (`night: null`, 5 stand points) — Grand marble staircase flanked by cypress trees and braziers leading to the Shrine of Ul'sterra.
  - `east_terrace` (*East Banner Terrace*): `Merry_Hills_Shrine_Entrance_Banner.jpg` (`night: null`, 5 stand points) — Cliffside terrace featuring a stone column draped in a sun-and-moon banner and ringed by burning candles.
  - `west_overlook` (*West Overlook*): `Merry_Hills_Shrine_Entrance_West.jpg` (`night: null`, 5 stand points) — Stone parapet terrace overlooking the mountain canyon, guarded by a corner brazier.
- **Unused Images:**
  - `Merry_Hills_Shrine_Entrance_Agnea.jpg`: Cutscene duplicate of `shrine_courtyard` with a grand piano and overturned cart on the steps.
  - `Merry_Hills_Shrine_Entrance_East.jpg`: Redundant wider angle of `east_terrace`.
  - `Merry_Hills_Shrine_Entrance_Tree.jpg`: Redundant angle of the western banner column adjacent to `west_overlook`.

### 8. `montwise` (default: `town_square`)
- **Spots:**
  - `town_square` (*Town Square*): `Montwise_Center.jpg` (`night: null`, 5 stand points) — Central cobblestone plaza and old book market fronting the provisioner shop and outdoor tavern tables.
  - `library_exterior` (*Library Entrance*): `Montwise_Library_Exterior.jpg` (`night: null`, 5 stand points) — Stone courtyard terrace before the sculpted portico and double doors of the Montwise Grand Library.
  - `town_entrance` (*Town Entrance Bridge*): `Montwise.jpg` (`night: null`, 5 stand points) — High stone arch bridge spanning the mountain gorge at the entrance to Montwise, hung with red banners.
  - `arena_entrance` (*Underground Arena Entrance*): `Montwise_Arena_Entrance.jpg` (`night: null`, 5 stand points) — Subterranean stone arcade beneath the bridge where a banner-flanked archway descends to the arena.
  - `moneylenders_manse_exterior` (*Moneylender's Manse Exterior*): `Montwise_Manse_Exterior.jpg` (`night: null`, 5 stand points) — Hillside flagstone terrace flanked by cypress planters outside the moneylender's residence.
  - `moneylenders_manse_interior` (*Moneylender's Manse Interior*): `Montwise_Manse.jpg` (`night: null`, 5 stand points) — Lavish salon inside the moneylender's estate with crystal chandelier, wall safes, and roulette table.
  - `the_well` (*Cliffside Well*): `Montwise_Well.jpg` (`night: null`, 5 stand points) — Secluded lower cliff terrace with a timber-roofed stone well, torches, and steps up to the square.
- **Unused Images:**
  - `Montwise_Moon.jpg`: Rooftop panoramic vista of the Grand Library dome against the full moon with no walkable ground.
  - `Montwise_Moneylender's_Manse.jpg`: Cutscene duplicate of `Montwise_Manse.jpg` during Osvald and Partitio's Crossed Path.
  - `Montwise_Overview.jpg`: Pulled-back duplicate angle of `Montwise_Center.jpg`.
  - `Montwise_Wall_Chest.jpg`: Narrow western battlement walkway focused on a treasure chest.
  - `Montwise_Night.jpg`: Nighttime view of the southern rampart steps shifted southwest from `Montwise_Center.jpg` (camera framing does not align with `Montwise_Center.jpg`).

### 9. `new_delsta` (default: `main_street`)
- **Spots:**
  - `main_street` (*Main Boulevard*): `New_Delsta_Epilogue.jpg` (`night: null`, 6 stand points) — Bustling central avenue lined with brick storefronts, taverns, and the grand stone staircase.
  - `theater_plaza` (*Theater & Estate Plaza*): `New_Delsta_West.jpg` (`night: null`, 6 stand points) — Paved plaza before the wrought-iron gates of Diamante's Estate and the New Delsta Theater.
  - `upper_promenade` (*Upper Promenade*): `New_Delsta_Street.jpg` (`night: null`, 5 stand points) — Upper street with an outdoor sidewalk cafe, market stall, and steps toward the theater.
  - `central_staircase` (*Central Staircase*): `New_Delsta_Nightlife.jpg` (`night: null`, 5 stand points) — Wide stone staircase linking the lower boulevard and upper cafe terrace under glowing lampposts.
  - `back_alley` (*Back Alley*): `New_Delsta_City_Lights_at_Night.jpg` (`night: null`, 5 stand points) — Dim brick tenement courtyard with crates and an open manhole descending into the Underground Waterway.
- **Unused Images:**
  - `New_Delsta_Perch.jpg`: Characters standing on a narrow rooftop ledge with a treasure chest (prompt forbids standing on roofs).
  - `New_Delsta_City_Night.jpg`: Duplicate of `New_Delsta_Nightlife.jpg` with the minimap HUD visible.
  - `New_Delsta_Epilogue_Dance.jpg`: Cutscene duplicate of `New_Delsta_West.jpg` crowded with dancing spectators.
  - `New_Delsta_Night.jpg`: Overlapping nighttime street curve view redundant with `main_street` and `central_staircase`.

### 10. `new_delsta_theater` (default: `auditorium_aisle`)
- **Spots:**
  - `auditorium_aisle` (*Auditorium Aisle*): `New_Delsta_Theater_Pillars.jpg` (`night: null`, 5 stand points) — Red-carpeted central aisle between spiral gold columns, flanked by velvet auditorium seating.
  - `the_stage` (*The Grand Stage*): `Dolcinaea_New_Delsta_Theater.jpg` (`night: null`, 6 stand points) — Gilded theater stage framed by red velvet curtains and an opulent golden peacock backdrop.
  - `auditorium_mezzanine` (*Auditorium Mezzanine*): `New_Delsta_Theater.jpg` (`night: null`, 4 stand points) — Elevated balcony aisle overlooking the plush seating rows and the crimson-curtained stage.
- **Unused Images:**
  - `CotC_New_Delsta_Theater_Upper_Floor_Onstage_View.png`: Skipped per prompt rule (*Champions of the Continent* `CotC_` image).
  - `CotC_New_Delsta_Theater_Crossed_Paths.png`: Skipped per prompt rule (*Champions of the Continent* `CotC_` image).
  - `Agnea_New_Delsta_Theater.jpg`: Cutscene angle of the stage with blurred audience heads across the foreground, redundant with `the_stage`.
  - `Agnea's_Finale.jpg`: Cutscene reverse-shot from behind Agnea facing a packed auditorium with no open floor space.

### 11. `oresrush` (default: `main_street`)
- **Spots:**
  - `main_street` (*Main Street*): `Oresrush_Day.jpg` (`night: null`, 5 stand points) — Broad dirt road running beneath the wooden water tower past the saloon and boardwalk storefronts.
  - `papps_house` (*Papp's House*): `Oresrush_Papp's_House.jpg` (`night: null`, 5 stand points) — Two-story frontier timber house and yard on the rocky red bluff overlooking Oresrush.
  - `town_center` (*Town Center*): `Oresrush_Center.jpg` (`night: null`, 5 stand points) — Commercial heart of town with wooden boardwalk storefronts and the community bulletin board.
  - `stables` (*The Stables*): `Oresrush_Stables.jpg` (`night: null`, 5 stand points) — Wooden horse barn and fenced dirt paddock below the eastern windmill.
  - `tavern` (*Tavern Porch*): `Oresrush_Tavern.jpg` (`night: null`, 5 stand points) — Lantern-lit wooden boardwalk porch outside the Oresrush tavern and neighboring armory.
  - `inn_balcony` (*Inn Upper Balcony*): `Oresrush_Upper_Level.jpg` (`night: null`, 5 stand points) — Second-story wooden terrace of the inn overlooking the town entrance road.
  - `saddlery` (*The Saddlery*): `Oresrush_Saddlery.jpg` (`night: null`, 5 stand points) — Leatherworking shop interior with a wagon-wheel chandelier and curved counter.
- **Unused Images:**
  - **33 past-timeline images skipped per prompt rule** (*"For `oresrush`, use only present-day images, not Partitio's past timelines"*):
    - *16 years ago (5):* `Oresrush_Origin_Dreams.jpg`, `Oresrush_Origin_Father_and_Son.jpg`, `Oresrush_Origin_Mini_Partitio.jpg`, `Oresrush_Origin_Outlook.jpg`, `Oresrush_Origin.jpg`.
    - *Construction timelapse (5):* `Oresrush_Timelapse_Beginning.jpg`, `Oresrush_Timelapse_Foundation.jpg`, `Oresrush_Timelapse_Scaffolding.jpg`, `Oresrush_Timelapse_Construction.jpg`, `Oresrush_Timelapse_Complete.jpg`.
    - *8 years ago, period of prosperity (15):* `Oresrush_Prosperity_Construction.jpg`, `Oresrush_Prosperity.jpg`, `Oresrush_Prosperity_Auction.jpg`, `Oresrush_Prosperity_Papp's_House.jpg`, `Oresrush_Prosperity_House_Night.jpg`, `Oresrush_Prosperity_Side_Room.jpg`, `Oresrush_Prosperity_House_Interior.jpg`, `Oresrush_Prosperity_Upstairs.jpg`, `Oresrush_Prosperity_Father_and_Son.jpg`, `Oresrush_Prosperity_Night.jpg`, `Oresrush_Prosperity_Foundry.jpg`, `Oresrush_Prosperity_Yard.jpg`, `Oresrush_Prosperity_Roque.jpg`, `Oresrush_Prosperity_Roque's_Offer.jpg`, `Oresrush_Prosperity_Autumn_House.jpg`.
    - *Period of poverty (8):* `Oresrush_Poverty.jpg`, `Oresrush_Poverty_Upstairs.jpg`, `Oresrush_Poverty_Papp's_House.jpg`, `Oresrush_Poverty_Side_Room.jpg`, `Oresrush_Poverty_House_Interior.jpg`, `Oresrush_Poverty_Partitio.jpg`, `Oresrush_Poverty_Giff.jpg`, `Oresrush_Poverty_Tavern.jpg`.
  - **3 present-day images not used:**
    - `Oresrush_Vulture.jpg`: Cutscene shot focused on a vulture perched on a broken wagon carcass blocking the center road, redundant with `main_street` and `town_center`.
    - `Oresrush_Night_Road.jpg`: Nighttime view of the town road shifted east relative to `Oresrush_Center.jpg` (camera framing does not match `Oresrush_Center.jpg` or `Oresrush_Day.jpg`).
    - `Oresrush_Partitio.jpg`: Cutscene angle near Papp's house with the foreground water tower barrel obstructing the standing area, redundant with `papps_house`.

### 12. `southern_oresrush_wilds` (default: `wilds_trail`)
- **Spots:**
  - `wilds_trail` (*Wilds Trail*): `Southern_Oresrush_Wilds_Trees.jpg` (`night: Southern_Oresrush_Wilds_Trees_Night.jpg`, 6 stand points) — Rocky sandstone terrace overlooking the crossroads trail where a covered wagon is parked.
  - `canyon_cache` (*Canyon Cache*): `Southern_Oresrush_Wilds_Chest.jpg` (`night: null`, 5 stand points) — Secluded sandstone ledge below a natural rock arch with an iron chest against the cliff.
- **Unused Images:**
  - `Southern_Oresrush_Wilds_Distance.jpg`: Distant landscape vista with heavy foreground tilt-shift blur and tiny background figures.
  - `Southern_Oresrush_Wilds_Arch.jpg`: Narrow vertical stone stairway between rock walls where a group cannot spread out to talk.
  - `Southern_Oresrush_Wilds_Night.jpg`: Unpaired night view by the windmill and save point with no matching daytime view, redundant with `wilds_trail`.

### 13. `western_crackridge_wilds` (default: `merchants_guild`)
- **Spots:**
  - `merchants_guild` (*Merchants' Guild Encampment*): `Western_Crackridge_Wilds_Merchants'_Guild.jpg` (`night: null`, 5 stand points) — Cliffside headquarters of the Merchants' Guild with merchant tents, wares, and a campfire.
  - `cliff_terrace` (*Cliffside Terrace*): `Western_Crackridge_Wilds_Cliff.jpg` (`night: null`, 6 stand points) — Sunlit sandstone ledge perched above the canyon abyss with a ladder and oil lantern.
  - `mine_scaffolding` (*Mine Scaffolding*): `Western_Crackridge_Wilds_Scaffolding.jpg` (`night: null`, 6 stand points) — Heavy wooden trestle platform and timber bridge spanning a deep canyon gorge.
- **Unused Images:**
  - `Western_Crackridge_Wilds_Vulture.jpg`: Narrow ridge vista focused on a vulture perched on a dead pine over sheer canyon drop-offs.
