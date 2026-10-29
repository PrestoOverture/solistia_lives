# Scene Player Art, Step 3 — Clean Images Report

## Summary

- **Total unique stage catalog images across 13 places**: 66 (`assets/player/clean/<place>/<file>`)
- **Gemini whole-frame copies awaiting original-based replacement**: 0 images
- **Cleaned with built-in imagegen + masked Pillow composite**: 63 images (3 reviewed test images, 48 subsequent originals, and 12/12 Gemini replacements).
- **Already clean in original gallery (no playable travelers, companion beast, or UI elements)**: 3 images
  - `crackridge/Moonshade_Order_Townspeople.jpg`
  - `new_delsta/New_Delsta_Nightlife.jpg`
  - `new_delsta_theater/Dolcinaea_New_Delsta_Theater.jpg`
- **Still unedited copies pending cleanup**: 0 images
- **Originals & Catalogs**: `assets/player/gallery/` and `assets/player/stages/*.yaml` were not modified.

---

## Still Unedited Files (0 Total)



---

## Per-Place Breakdown (All 66 Stage Catalog Images)

### 1. `conning_creek` (4 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Conning_Creek_Overview.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed playable traveler Osvald V. Vanstein standing on the middle terrace steps; inpainted stone steps and dirt path; preserved all 8 townspeople and `1280×720` resolution. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Conning_Creek_Ochette.jpg` | Cleaned (built-in imagegen + masked composite) | Ochette and Akala; all townspeople retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Conning_Creek_Guardhouse.jpg` | Cleaned (built-in imagegen + masked composite) | Removed travelers and visible UI; original size retained. | Used three targeted imagegen crop edits for party/stairs, guard bubble and HUD after full-frame call remained pending; guard and architecture retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Conning_Creek_Flowerbed.jpg` | Cleaned (built-in imagegen + masked composite) | Party, two distant guard bubbles and minimap/compass HUD; fence and flowerbed reconstructed. | Second edit reconstructed the flowerbed and fence after first result left broken fence fragments; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 2. `crackridge` (6 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Crackridge_Entrance.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed 5-member party cluster on the central dirt terrace (Throné, Temenos, Osvald, Castti, Ochette + Mahina), bottom-right circular minimap HUD, and speech bubbles over the upper-stairwell NPCs; preserved all townspeople and `1280×720` resolution. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Crackridge_Chasm.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed 5-member party cluster on the wooden chasm deck, speech bubble over the doorway NPC, and bottom-right circular minimap HUD; preserved the doorway townsman and `1280×720` resolution. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Moonshade_Order_Townspeople.jpg` | Already clean (copied) | Nothing to remove — original gallery screenshot is a clean cutscene frame containing only 5 townspeople NPCs with no playable travelers, companion beast, or UI elements. | None. |
| `Crackridge_Scaffolding.jpg` | Cleaned (built-in imagegen + masked composite) | Ramp party, two NPC bubbles and entire minimap/compass HUD. | Second pass removed remaining crescent HUD beside lower-right NPC; both NPCs and ramp geometry retained. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Crackridge_View.jpg` | Cleaned (built-in imagegen + masked composite) | Cliff party and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Crackridge_View_Night.jpg` | Cleaned (built-in imagegen + masked composite) | Cliff party, minimap/compass HUD and Change Time prompt. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 3. `cropdale` (8 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Cropdale.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed playable party members on the central stone steps, bottom-right circular minimap HUD, and NPC speech bubbles; preserved all 5 townspeople and `1280×720` resolution. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Cropdale_Bridge_Day.jpg` | Cleaned (built-in imagegen + masked composite) | Removed 5 travelers, 6 speech bubbles, bottom-right minimap/compass HUD; preserved townspeople and 1280×720 size. | Outside masks exact before JPEG save; quality 100, 4:4:4. Oresrush required a bubble-removal follow-up. |
| `Cropdale_Bridge.jpg` | Cleaned (built-in imagegen + masked composite) | Bridge party, two NPC bubbles and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Cropdale_Agnea's_House.jpg` | Cleaned (built-in imagegen + masked composite) | Agnea, five NPC bubbles and minimap/compass HUD. | Used magnified crop edit for stubborn dark speech bubble; townspeople and flowers retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Cropdale_Agnea's_House_Interior.jpg` | Cleaned (built-in imagegen + masked composite) | Agnea at bedroom doorway; Pala and all furniture retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Cropdale_Garud's_Room.jpg` | Cleaned (built-in imagegen + masked composite) | Agnea, shoe remnants, Garud speech bubble and minimap/compass HUD; Garud retained. | Second pass removed shoe remnants; Garud, loom and furniture retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Cropdale_Tavern.jpg` | Cleaned (built-in imagegen + masked composite) | Agnea and musical-note UI; musicians and all patrons retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Cropdale_Swine.jpg` | Cleaned (built-in imagegen + masked composite) | Four travelers, two NPC bubbles and minimap/compass HUD; pigs and doorway NPC retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 4. `festival_grounds` (3 images — 100% cleaned)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Festival_Grounds_Crowd.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed vertical column of 5 playable party members (Throné, Temenos, Osvald, Castti, Ochette + Mahina) in center of clearing and bottom-right circular minimap HUD; preserved all musicians, dancers, and festival townspeople at `1280×720`. | Mask includes party cast shadows; all festival townspeople, garlands and props retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Festival_Grounds_Banners.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed line of 5 playable party members on the stepped dirt entrance path and bottom-right circular minimap HUD; preserved background festival NPCs and colorful banner garlands at `1280×720`. | Mask includes party cast shadows; all festival townspeople, garlands and props retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Festival_Grounds_Agnea.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed Agnea dancing at center stage; reconstructed illuminated wooden stage floor while keeping all 13 audience townspeople and torchlight intact at `1280×720`. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 5. `flamechurch` (6 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Flamechurch_Hill.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed 4 playable party members (Throné, Osvald, Castti, Ochette) from the cobblestone courtyard in front of the chapel, bottom-right circular minimap HUD, and NPC speech bubbles; preserved the 3 townspeople on the left and the cleric on the right at `1280×720`. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Flamechurch_Chapel.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed 4 playable party members from the red-patterned nave rug, bottom-right circular minimap HUD, and NPC speech bubbles; preserved all 8 churchgoers, nuns, and clerics at `1280×720`. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Flamechurch_Chapel_Night.jpg` | Cleaned (built-in imagegen + masked composite) | Party before altar, two NPC bubbles and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Flamechurch_Temenos_and_Throne.jpg` | Cleaned (built-in imagegen + masked composite) | Throne and Temenos between braziers; background NPCs retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Flamechurch_Town_Night.jpg` | Cleaned (built-in imagegen + masked composite) | Stairway party and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Flamechurch_Night.jpg` | Cleaned (built-in imagegen + masked composite) | Four travelers, five speech/action balloons and minimap/compass HUD. | Magnified crop edits removed two stubborn dark bubble outlines; all NPCs retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 6. `merry_hills` (6 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Merry_Hills.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed vertical column of 5 playable party members (Throné, Temenos, Osvald, Castti, Ochette + Mahina) on the central cobblestone avenue, bottom-right circular minimap HUD, and all NPC speech bubbles; preserved all market vendors, shoppers, and townspeople at `1280×720`. | Magnified crop removed the faint background speech bubble; market NPCs and props retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Tavern.jpg` | Cleaned (built-in imagegen + masked composite) | Tavern party, woman speech bubble, minimap/compass HUD and Change Time prompt. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Bridge.jpg` | Cleaned (built-in imagegen + masked composite) | Five travelers, their cast shadows and minimap/compass HUD. | Targeted second pass removed residual traveler shadows or distant speech bubble; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Stairs.jpg` | Cleaned (built-in imagegen + masked composite) | Stairway party, three NPC bubbles including top-edge bubble, and minimap/compass HUD. | Targeted second pass removed residual traveler shadows or distant speech bubble; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Entrance.jpg` | Cleaned (built-in imagegen + masked composite) | Party and shadows, NPC speech/action bubbles, save marker and minimap/compass HUD; actual save book retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Descent.jpg` | Cleaned (built-in imagegen + masked composite) | Path party and minimap/compass HUD; two bridge NPCs retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 7. `merry_hills_shrine_entrance` (5 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Merry_Hills_Shrine_Entrance.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed 5 playable party members from the center stone plaza, bottom-right circular minimap HUD, and NPC speech bubbles; preserved all 8 townspeople and guards at `1280×720`. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Shrine_Entrance_Night.jpg` | Cleaned (original-based imagegen + masked composite; replaces Gemini) | Removed playable party members from the center stone plaza, bottom-right circular minimap HUD, and NPC speech bubbles; preserved all 27 night-festival townspeople, jester, and guards at `1280×720`. | Visually checked; all townspeople and props retained; original composition unchanged. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Shrine_Entrance_Center.jpg` | Cleaned (built-in imagegen + masked composite) | Shrine stairway party, NPC bubble and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Shrine_Entrance_Banner.jpg` | Cleaned (built-in imagegen + masked composite) | Party below banner, upper-right and blurred left-edge bubbles, minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Merry_Hills_Shrine_Entrance_West.jpg` | Cleaned (built-in imagegen + masked composite) | Terrace party, two NPC bubbles and minimap/compass HUD; boy under map retained. | Magnified crop edit preserved and reconstructed boy under translucent minimap; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 8. `montwise` (7 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Montwise_Center.jpg` | Cleaned (built-in imagegen + masked composite) | Removed 5 travelers, all 10 visible speech bubbles, bottom-right minimap/compass HUD; preserved townspeople and 1280×720 size. | Outside masks exact before JPEG save; quality 100, 4:4:4. Oresrush required a bubble-removal follow-up. |
| `Montwise_Library_Exterior.jpg` | Cleaned (built-in imagegen + masked composite) | Library stairway party and shadows, two NPC bubbles and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Montwise.jpg` | Cleaned (built-in imagegen + masked composite) | Bridge party and shadows, three NPC bubbles and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Montwise_Arena_Entrance.jpg` | Cleaned (built-in imagegen + masked composite) | Arena party including partially occluded travelers and Partitio; minimap/compass HUD; pillar retained. | Follow-up removed remaining Partitio; masked occluded travelers without moving central pillar; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Montwise_Manse_Exterior.jpg` | Cleaned (built-in imagegen + masked composite) | Stairway party and shadows, maid speech bubble and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Montwise_Manse.jpg` | Cleaned (built-in imagegen + masked composite) | Parlor party, maid speech bubble, minimap/compass HUD and Change Time prompt. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Montwise_Well.jpg` | Cleaned (built-in imagegen + masked composite) | Party by well, three speech/action bubbles and minimap/compass HUD; actual save book retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 9. `new_delsta` (5 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `New_Delsta_Nightlife.jpg` | Already clean (copied) | Nothing to remove — original gallery screenshot is a clean night scene of New Delsta containing only townspeople and a cat on a bench, with no playable travelers, companion beast, or UI elements. | None. |
| `New_Delsta_Epilogue.jpg` | Cleaned (built-in imagegen + masked composite) | Hikari and Temenos in plaza and Osvald on upper landing; their shadows; flag/string and NPCs retained. | Magnified crop removed Osvald on upper landing while retaining crossing flag/string; Hikari/Temenos and their shadows removed; all NPCs retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `New_Delsta_West.jpg` | Cleaned (built-in imagegen + masked composite) | Partitio, Throne, Temenos and their shadows; three NPC bubbles and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `New_Delsta_Street.jpg` | Cleaned (built-in imagegen + masked composite) | Party column, three NPC bubbles and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `New_Delsta_City_Lights_at_Night.jpg` | Cleaned (built-in imagegen + masked composite) | Throne and her shadow; open manhole and props retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 10. `new_delsta_theater` (3 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Dolcinaea_New_Delsta_Theater.jpg` | Already clean (copied) | Nothing to remove — original gallery screenshot contains only NPC Dolcinaea Luciel on the grand theater stage with no playable travelers, companion beast, or UI elements. | None. |
| `New_Delsta_Theater_Pillars.jpg` | Cleaned (built-in imagegen + masked composite) | Temenos and minimap/compass HUD; carpet motif reconstructed. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `New_Delsta_Theater.jpg` | Cleaned (built-in imagegen + masked composite) | Agnea in lower aisle; all audience NPCs retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 11. `oresrush` (7 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Oresrush_Day.jpg` | Cleaned (built-in imagegen + masked composite) | Overlapping street party and four NPC bubbles; native 2560x1600 letterboxed framing retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Oresrush_Papp's_House.jpg` | Cleaned (built-in imagegen + masked composite) | Party, two NPC bubbles and minimap/compass HUD. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Oresrush_Center.jpg` | Cleaned (built-in imagegen + masked composite) | Removed 5 travelers and Akala, 4 speech bubbles, bottom-right minimap/compass HUD; preserved townspeople and 1280×720 size. | Outside masks exact before JPEG save; quality 100, 4:4:4. Oresrush required a bubble-removal follow-up. |
| `Oresrush_Stables.jpg` | Cleaned (built-in imagegen + masked composite) | Four travelers, Akala, four NPC bubbles and entire minimap/compass HUD; townspeople retained. | Magnified crop edits removed residual HUD symbols or balloon outlines; townspeople, porch rails and actual save book retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Oresrush_Tavern.jpg` | Cleaned (built-in imagegen + masked composite) | Four travelers, Akala, two speech/action balloons and minimap/compass HUD; actual save book retained. | Magnified crop edits removed residual HUD symbols or balloon outlines; townspeople, porch rails and actual save book retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Oresrush_Upper_Level.jpg` | Cleaned (built-in imagegen + masked composite) | Four balcony travelers, three NPC bubbles and minimap/compass HUD; all four NPCs retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Oresrush_Saddlery.jpg` | Cleaned (built-in imagegen + masked composite) | Throne and her shadow in front of counter; shopkeeper retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 12. `southern_oresrush_wilds` (3 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Southern_Oresrush_Wilds_Trees.jpg` | Cleaned (built-in imagegen + masked composite) | Four travelers, Akala, their shadows and minimap/compass HUD; both ledge NPCs retained. | Removed travelers, companion where present, their shadows and held-light footprint; both ledge NPCs and chest retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Southern_Oresrush_Wilds_Trees_Night.jpg` | Cleaned (built-in imagegen + masked composite) | Four travelers, Akala, shadows/held-light footprint and minimap/compass HUD; both ledge NPCs retained. | Removed travelers, companion where present, their shadows and held-light footprint; both ledge NPCs and chest retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Southern_Oresrush_Wilds_Chest.jpg` | Cleaned (built-in imagegen + masked composite) | Party beside chest and minimap/compass HUD; chest retained. | Removed travelers, companion where present, their shadows and held-light footprint; both ledge NPCs and chest retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

---

### 13. `western_crackridge_wilds` (3 images)

| File | Status | Removed | Problems / Notes |
| :--- | :--- | :--- | :--- |
| `Western_Crackridge_Wilds_Merchants'_Guild.jpg` | Cleaned (built-in imagegen + masked composite) | Stairway party, two speech/icon balloons and minimap/compass HUD; camp NPCs retained. | Magnified crop removed residual bubble outline; both camp NPCs, tents and props retained; visually checked. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Western_Crackridge_Wilds_Cliff.jpg` | Cleaned (built-in imagegen + masked composite) | Four travelers, shadows and minimap/compass HUD; both right-side NPCs retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |
| `Western_Crackridge_Wilds_Scaffolding.jpg` | Cleaned (built-in imagegen + masked composite) | Platform party and minimap/compass HUD; all three bridge NPCs retained. | Visually checked; townspeople retained; no visible composition shift. JPEG quality 95, subsampling 0; outside masks exact before encoding. |

## Three-image masked cleanup verification (2026-10-29)

Only the three requested clean files changed, verified against SHA-256 snapshots of gallery, stage catalogs and all clean assets. The 12 earlier cleaned images and all other copies remain unchanged. Townspeople, architecture and props outside removal masks retain original pixels before encoding. Generated edits were resized from 1672×941 to original 1280×720.

The user selected JPEG output after being informed that JPEG re-encoding cannot preserve decoded pixels exactly. Scratch lossless composites have zero changed pixels outside masks. Final JPEGs use quality 100 and no chroma subsampling. Encoding differences outside masks:

| Image | Changed pixels outside masks | Mean absolute channel difference (0–255) | Maximum channel difference |
| :--- | ---: | ---: | ---: |
| `montwise/Montwise_Center.jpg` | 137949 | 0.127856 | 4 |
| `oresrush/Oresrush_Center.jpg` | 122209 | 0.117429 | 4 |
| `cropdale/Cropdale_Bridge_Day.jpg` | 162005 | 0.144759 | 4 |

Script, explicit masks, mask previews, generated edits, lossless composites, prompt set and validation JSON: `kb_raw/player_clean_scratch/`. Run with `uv run --with pillow python kb_raw/player_clean_scratch/composite.py` followed by the Montwise, Oresrush and Cropdale generated edit paths, in that order. Source originals are read-only inputs. Masks have a few pixels of padding; boundary color matching and inward feathering reduce seams.

Validation: 968 unit tests passed; `uv run story-engine --help` passed. No live model tests were run. The initial test batch stopped after these three and passed user review. The remaining-48 pass below is now complete.

## Remaining 48 cleanup — completed

Pipeline: built-in imagegen → resize to original dimensions → explicit padded mask composite → JPEG quality 95, subsampling 0. Original pixels outside masks are exact before JPEG encoding; encoding differences are recorded in scratch validation data. The earlier 15 cleaned images remain protected by SHA-256 checks.

| File | Status | Outside-mask JPEG mean absolute channel difference | Maximum |
| :--- | :--- | ---: | ---: |
| `conning_creek/Conning_Creek_Ochette.jpg` | cleaned | 0.518670 | 14 |
| `conning_creek/Conning_Creek_Guardhouse.jpg` | cleaned | 0.567555 | 15 |
| `conning_creek/Conning_Creek_Flowerbed.jpg` | cleaned | 0.478236 | 15 |
| `crackridge/Crackridge_Scaffolding.jpg` | cleaned | 0.535486 | 10 |
| `crackridge/Crackridge_View.jpg` | cleaned | 0.172151 | 10 |
| `crackridge/Crackridge_View_Night.jpg` | cleaned | 0.210623 | 8 |
| `cropdale/Cropdale_Bridge.jpg` | cleaned | 0.567446 | 16 |
| `cropdale/Cropdale_Agnea's_House.jpg` | cleaned | 0.522968 | 16 |
| `cropdale/Cropdale_Agnea's_House_Interior.jpg` | cleaned | 0.428795 | 18 |
| `cropdale/Cropdale_Garud's_Room.jpg` | cleaned | 0.371658 | 12 |
| `cropdale/Cropdale_Tavern.jpg` | cleaned | 0.426731 | 18 |
| `cropdale/Cropdale_Swine.jpg` | cleaned | 0.551989 | 16 |
| `flamechurch/Flamechurch_Chapel_Night.jpg` | cleaned | 0.497096 | 17 |
| `flamechurch/Flamechurch_Temenos_and_Throne.jpg` | cleaned | 0.475809 | 16 |
| `flamechurch/Flamechurch_Town_Night.jpg` | cleaned | 0.445710 | 18 |
| `flamechurch/Flamechurch_Night.jpg` | cleaned | 0.535325 | 13 |
| `merry_hills/Merry_Hills_Tavern.jpg` | cleaned | 0.450522 | 13 |
| `merry_hills/Merry_Hills_Bridge.jpg` | cleaned | 0.305610 | 13 |
| `merry_hills/Merry_Hills_Stairs.jpg` | cleaned | 0.574906 | 13 |
| `merry_hills/Merry_Hills_Entrance.jpg` | cleaned | 0.521154 | 15 |
| `merry_hills/Merry_Hills_Descent.jpg` | cleaned | 0.502254 | 15 |
| `merry_hills_shrine_entrance/Merry_Hills_Shrine_Entrance_Center.jpg` | cleaned | 0.535883 | 13 |
| `merry_hills_shrine_entrance/Merry_Hills_Shrine_Entrance_Banner.jpg` | cleaned | 0.470635 | 13 |
| `merry_hills_shrine_entrance/Merry_Hills_Shrine_Entrance_West.jpg` | cleaned | 0.457780 | 11 |
| `montwise/Montwise_Library_Exterior.jpg` | cleaned | 0.469385 | 11 |
| `montwise/Montwise.jpg` | cleaned | 0.472691 | 14 |
| `montwise/Montwise_Arena_Entrance.jpg` | cleaned | 0.416980 | 11 |
| `montwise/Montwise_Manse_Exterior.jpg` | cleaned | 0.435191 | 11 |
| `montwise/Montwise_Manse.jpg` | cleaned | 0.480977 | 16 |
| `montwise/Montwise_Well.jpg` | cleaned | 0.427174 | 11 |
| `new_delsta/New_Delsta_Epilogue.jpg` | cleaned | 0.578452 | 17 |
| `new_delsta/New_Delsta_West.jpg` | cleaned | 0.548724 | 17 |
| `new_delsta/New_Delsta_Street.jpg` | cleaned | 0.546084 | 15 |
| `new_delsta/New_Delsta_City_Lights_at_Night.jpg` | cleaned | 0.507544 | 15 |
| `new_delsta_theater/New_Delsta_Theater_Pillars.jpg` | cleaned | 0.414584 | 14 |
| `new_delsta_theater/New_Delsta_Theater.jpg` | cleaned | 0.350480 | 14 |
| `oresrush/Oresrush_Day.jpg` | cleaned | 0.282015 | 10 |
| `oresrush/Oresrush_Papp's_House.jpg` | cleaned | 0.508316 | 11 |
| `oresrush/Oresrush_Stables.jpg` | cleaned | 0.491428 | 11 |
| `oresrush/Oresrush_Tavern.jpg` | cleaned | 0.403499 | 12 |
| `oresrush/Oresrush_Upper_Level.jpg` | cleaned | 0.478650 | 15 |
| `oresrush/Oresrush_Saddlery.jpg` | cleaned | 0.259497 | 10 |
| `southern_oresrush_wilds/Southern_Oresrush_Wilds_Trees.jpg` | cleaned | 0.575037 | 11 |
| `southern_oresrush_wilds/Southern_Oresrush_Wilds_Trees_Night.jpg` | cleaned | 0.504655 | 12 |
| `southern_oresrush_wilds/Southern_Oresrush_Wilds_Chest.jpg` | cleaned | 0.491672 | 11 |
| `western_crackridge_wilds/Western_Crackridge_Wilds_Merchants'_Guild.jpg` | cleaned | 0.464562 | 10 |
| `western_crackridge_wilds/Western_Crackridge_Wilds_Cliff.jpg` | cleaned | 0.475522 | 12 |
| `western_crackridge_wilds/Western_Crackridge_Wilds_Scaffolding.jpg` | cleaned | 0.474295 | 11 |

### Final verification

- All 48 requested files cleaned and visually reviewed, place by place. No no-target skips; no files left unedited because of visible damage or composition shift. Every original contained travelers or UI requiring removal.
- JPEG quality **95**, subsampling **0** verified from saved JPEG sampling and quantization tables for all 48. The three earlier reviewed test images retain their original quality-100 outputs.
- All native dimensions retained: 47 files at 1280×720 and `Oresrush_Day.jpg` at **2560×1600**, including its letterbox bars.
- Every lossless pre-save composite was checked channel by channel: **zero changed pixels outside the explicit padded removal masks**. JPEG re-encoding differences are shown in the per-file table above and recorded in scratch validation data.
- SHA-256 checks verified all **178 protected files** unchanged: all gallery originals, all stage catalogs, and all clean copies outside the 48-file scope, including the 15 previously cleaned images. No asset files were added or removed.
- `uv sync`, 968 unit tests and the CLI help smoke check passed. No live model tests, packaging, commits or pushes.
- Built-in imagegen was used throughout. Targeted magnified crop edits corrected persistent bubbles/HUD fragments and preserved the boy underneath a translucent minimap. Guardhouse used three crop edits after the full-frame call remained pending; that redundant call was terminated after the crop composites passed review.
- Scratch artifacts: `kb_raw/player_clean_scratch/composite.py`, `remaining48_specs.json`, `remaining48_progress.json`, `remaining48_prompt_set.json`, `remaining48_audit.json`, generated edits/patches, masks, mask previews and lossless composites.

## Original-based redo of 12 Gemini images

Every replacement starts from `assets/player/gallery/`, never the former Gemini clean copy. Explicit padded masks composite imagegen-edited pixels over the original; native dimensions and composition are retained. Output JPEG quality 95, subsampling 0. The other 54 clean files, all originals and all stage catalogs are protected by SHA-256 snapshots.

| File | Status | JPEG mean absolute channel difference outside masks | Maximum |
| :--- | :--- | ---: | ---: |
| `conning_creek/Conning_Creek_Overview.jpg` | cleaned | 0.552213 | 12 |
| `crackridge/Crackridge_Entrance.jpg` | cleaned | 0.557272 | 11 |
| `crackridge/Crackridge_Chasm.jpg` | cleaned | 0.305027 | 9 |
| `cropdale/Cropdale.jpg` | cleaned | 0.466843 | 14 |
| `festival_grounds/Festival_Grounds_Crowd.jpg` | cleaned | 0.509076 | 13 |
| `festival_grounds/Festival_Grounds_Banners.jpg` | cleaned | 0.557549 | 14 |
| `festival_grounds/Festival_Grounds_Agnea.jpg` | cleaned | 0.431189 | 12 |
| `flamechurch/Flamechurch_Hill.jpg` | cleaned | 0.589250 | 13 |
| `flamechurch/Flamechurch_Chapel.jpg` | cleaned | 0.476839 | 11 |
| `merry_hills/Merry_Hills.jpg` | cleaned | 0.441018 | 11 |
| `merry_hills_shrine_entrance/Merry_Hills_Shrine_Entrance.jpg` | cleaned | 0.419426 | 14 |
| `merry_hills_shrine_entrance/Merry_Hills_Shrine_Entrance_Night.jpg` | cleaned | 0.435574 | 12 |

### Final redo verification — 2026-10-30

- All 12 former Gemini copies were rebuilt from gallery originals and visually reviewed. All 12 remain 1280×720, saved as JPEG quality **95**, subsampling **0**.
- Every lossless pre-save composite has **zero changed pixels outside the padded removal masks**. Saved JPEG re-encoding differences are measured in the table above; these are not claimed to be pixel-identical after encoding.
- SHA-256 verification confirms all **54 other clean files** unchanged, together with every gallery original and stage catalog (**214 protected files** total). No asset files were added or removed.
- The faint remaining Merry Hills speech bubble was removed with a magnified imagegen crop patch, then composited through the same mask pipeline.
- `uv sync`, **968 unit tests**, and the CLI help smoke check passed. No live tests, packaging, commits or pushes.
- Reproducible scratch records: `kb_raw/player_clean_scratch/composite.py`, `redo12_specs.json`, `redo12_prompts.json`, `redo12_progress.json`, `redo12_baseline.json`, and `redo12_audit.json`, plus generated edits, masks and lossless composites.
