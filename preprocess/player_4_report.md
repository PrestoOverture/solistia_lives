# Scene Player Art, Step 4 — Field Sprites Report

## Summary

- **Destination directory**: `assets/player/sprites/`
- **Existing artifacts**: All 9 original `.webp` files (`agnea.webp`, `castti.webp`, `hikari.webp`, `minor.webp`, `ochette.webp`, `osvald.webp`, `partitio.webp`, `temenos.webp`, `throne.webp`) were retained unmodified.
- **New PNG sprites created**: 24 files
  - **Travelers (Front)**: 8 files (`agnea.png`, `castti.png`, `hikari.png`, `ochette.png`, `osvald.png`, `partitio.png`, `temenos.png`, `throne.png`)
  - **Travelers (Side)**: 2 files (`agnea_side.png`, `hikari_side.png`)
  - **Townspeople (Men)**: 7 files (`minor_m1.png` through `minor_m7.png`)
  - **Townspeople (Women)**: 7 files (`minor_f1.png` through `minor_f7.png`)
- **Metadata catalog**: `assets/player/sprites/index.yaml` listing all 24 sprite files with `who`, `sex`, `view`, `faces`, and canonical `source` page URL.
- **Pixel integrity**: All sprites feature transparent RGBA backgrounds, complete uncropped figures including feet, and unscaled original pixel dimensions (no redrawing or editing of pixel art).

---

## 1. Travelers (8 Main Characters)

### Front-Facing Standing Frames (`<name>.png`)

All 8 *Octopath Traveler II* playable travelers were retrieved at full resolution directly from the Octopath Traveler Fandom Wiki repository:

| File | Character | Dimensions | Source Page URL | Status |
| :--- | :--- | :--- | :--- | :--- |
| `agnea.png` | Agnea Bristni | 72 × 148 | [Agnea Sprite](https://octopathtraveler.fandom.com/wiki/File:Agnea_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |
| `castti.png` | Castti Florenz | 72 × 160 | [Castti Sprite](https://octopathtraveler.fandom.com/wiki/File:Castti_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |
| `hikari.png` | Hikari Ku | 88 × 156 | [Hikari Sprite](https://octopathtraveler.fandom.com/wiki/File:Hikari_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |
| `ochette.png` | Ochette | 88 × 152 | [Ochette Sprite](https://octopathtraveler.fandom.com/wiki/File:Ochette_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |
| `osvald.png` | Osvald V. Vanstein | 84 × 160 | [Osvald Sprite](https://octopathtraveler.fandom.com/wiki/File:Osvald_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |
| `partitio.png` | Partitio Yellowil | 80 × 160 | [Partitio Sprite](https://octopathtraveler.fandom.com/wiki/File:Partitio_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |
| `temenos.png` | Temenos Mistral | 72 × 152 | [Temenos Sprite](https://octopathtraveler.fandom.com/wiki/File:Temenos_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |
| `throne.png` | Throné Anguis | 72 × 148 | [Throné Sprite](https://octopathtraveler.fandom.com/wiki/File:Thron%C3%A9_Sprite.png) | Downloaded & verified; transparent RGBA, full body with feet |

### Side-Facing Standing Frames (`<name>_side.png`)

| File | Character | Direction (`faces`) | Dimensions | Source Sheet URL | Status / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `agnea_side.png` | Agnea Bristni | `left` | 32 × 72 | [Beta Agnea Walk](https://octopathtraveler.fandom.com/wiki/File:Beta_Agnea_Walk.png) | Cropped from neutral standing frame of overworld walk cycle (Row 1, cols 48–80, rows 176–256). Transparent RGBA, unscaled. |
| `hikari_side.png` | Hikari Ku | `left` | 38 × 76 | [Beta Hikari Sprites](https://octopathtraveler.fandom.com/wiki/File:Beta_Hikari_Sprites.png) | Cropped from neutral standing frame of overworld sprite sheet (Row 1, cols 42–80, rows 176–256). Transparent RGBA, unscaled. |
| `castti_side.png` | Castti Florenz | — | — | — | **Missing**: Not present on Fandom Wiki repository; alternative source (The Spriters Resource) blocked by Cloudflare bot mitigation (`HTTP 403 Forbidden`). |
| `ochette_side.png` | Ochette | — | — | — | **Missing**: Not present on Fandom Wiki repository; alternative source (The Spriters Resource) blocked by Cloudflare bot mitigation (`HTTP 403 Forbidden`). |
| `osvald_side.png` | Osvald V. Vanstein | — | — | — | **Missing**: Not present on Fandom Wiki repository; alternative source (The Spriters Resource) blocked by Cloudflare bot mitigation (`HTTP 403 Forbidden`). |
| `partitio_side.png` | Partitio Yellowil | — | — | — | **Missing**: Not present on Fandom Wiki repository; alternative source (The Spriters Resource) blocked by Cloudflare bot mitigation (`HTTP 403 Forbidden`). |
| `temenos_side.png` | Temenos Mistral | — | — | — | **Missing**: Not present on Fandom Wiki repository; alternative source (The Spriters Resource) blocked by Cloudflare bot mitigation (`HTTP 403 Forbidden`). |
| `throne_side.png` | Throné Anguis | — | — | — | **Missing**: Not present on Fandom Wiki repository; alternative source (The Spriters Resource) blocked by Cloudflare bot mitigation (`HTTP 403 Forbidden`). |

---

## 2. Townspeople (14 Diverse Archetypes)

A balanced set of 7 men and 7 women covering diverse social roles, clothing styles, and ages (guards, merchants, villagers, aristocrats, elders, and children) was downloaded at original resolution with transparent backgrounds.

### Men (`minor_m*.png`)

| File | Role / Archetype | View | Dimensions | Source Page URL | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `minor_m1.png` | Town Guard (Armored) | `front` | 76 × 144 | [Sunlands Guard Armored](https://octopathtraveler.fandom.com/wiki/File:Sunlands_Guard_Armored_Sprite.png) | Full armor, helmet, spear/halberd |
| `minor_m2.png` | Traveling Merchant | `front` | 76 × 132 | [Sunlands Merchant](https://octopathtraveler.fandom.com/wiki/File:Sunlands_Merchant_Sprite.png) | Turban, pack, trading attire |
| `minor_m3.png` | Commoner / Villager | `front` | 72 × 132 | [Cliftlands Man](https://octopathtraveler.fandom.com/wiki/File:Cliftlands_Man_Sprite.png) | Standard working man tunic and trousers |
| `minor_m4.png` | Aristocrat / Noble | `front` | 72 × 132 | [Aristocrat Man](https://octopathtraveler.fandom.com/wiki/File:Aristocrat_Man_Sprite.png) | Tailored gentleman's suit, cravat, coat |
| `minor_m5.png` | Town Elder | `front` | 72 × 132 | [Aristocrat Elderly Man](https://octopathtraveler.fandom.com/wiki/File:Aristocrat_Elderly_Man_Sprite.png) | Senior citizen with white hair and beard |
| `minor_m6.png` | Village Boy (Child) | `front` | 56 × 108 | [Cliftlands Child Boy](https://octopathtraveler.fandom.com/wiki/File:Cliftlands_Child_Boy_Sprite.png) | Young child figure |
| `minor_m7.png` | Town Barker / Crier | `front` | 72 × 132 | [Barker Sprite](https://octopathtraveler.fandom.com/wiki/File:Barker_Sprite.png) | Shouting townsman with megaphone / roll |

### Women (`minor_f*.png`)

| File | Role / Archetype | View | Dimensions | Source Page URL | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `minor_f1.png` | Commoner / Villager | `front` | 72 × 132 | [Cliftlands Woman](https://octopathtraveler.fandom.com/wiki/File:Cliftlands_Woman_Sprite.png) | Standard working woman dress and apron |
| `minor_f2.png` | Village Girl (Cropdale) | `front` | 84 × 152 | [Pala Sprite](https://octopathtraveler.fandom.com/wiki/File:Pala_Sprite.png) | Young village woman (matches existing `minor.webp`) |
| `minor_f3.png` | Aristocrat / Noble | `front` | 76 × 128 | [Aristocrat Woman](https://octopathtraveler.fandom.com/wiki/File:Aristocrat_Woman_Sprite.png) | Noble lady in formal ballgown |
| `minor_f4.png` | Young Lady | `front` | 72 × 132 | [Aristocrat Young Woman](https://octopathtraveler.fandom.com/wiki/File:Aristocrat_Young_Woman_Sprite.png) | Young woman in elegant dress |
| `minor_f5.png` | Town Elder | `front` | 72 × 132 | [Aristocrat Elderly Woman](https://octopathtraveler.fandom.com/wiki/File:Aristocrat_Elderly_Woman_Sprite.png) | Senior grandmother in shawl |
| `minor_f6.png` | Village Girl (Child) | `front` | 60 × 108 | [Cliftlands Child Girl](https://octopathtraveler.fandom.com/wiki/File:Cliftlands_Child_Girl_Sprite.png) | Young child figure |
| `minor_f7.png` | Reporter / Specialist | `front` | 72 × 148 | [Ori Sprite](https://octopathtraveler.fandom.com/wiki/File:Ori_Sprite.png) | OT2 New Delsta reporter in flat cap and vest |

### Townspeople Side Frames

- **Status**: No side frames were present on the wiki for generic townspeople. The community uploaded individual standalone standing front sprites rather than complete walk sheets. As per prompt guidelines (*"if the sheet has one, a side frame"*), only the available front frames are included.

---

## 3. Index Catalog Verification (`index.yaml`)

`assets/player/sprites/index.yaml` was generated with 24 structured entries complying strictly with the required fields:
- `who`: traveler name (`agnea`, `castti`, etc.) or `townsperson`
- `sex`: `m` or `f` (for townspeople entries)
- `view`: `front` or `side`
- `faces`: `left` or `right` (for side view frames)
- `source`: direct wiki canonical page URL
