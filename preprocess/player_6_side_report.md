# Player 6 — side sprite acquisition report

Status: incomplete. NPC sheets have been acquired; no traveler sheets or new side crops have been saved, and index.yaml has not been changed.

The requested Nintendo Switch game listing was opened in Chrome. After the user cleared Cloudflare verification, it showed 106 assets: 13 Non-Playable Characters & Guests, 85 Bosses, and 8 Character Select assets. The eight traveler entries below belong to Character Select; they have not been verified as field/overworld sheets and must not be used as substitutes without inspection.

| Traveler | Existing front PNG size | Listed character-select page (not a verified field-sheet source) | Side frame / box / facing / size / scale_vs_front |
|---|---|---|---|
| agnea | 72 × 148 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194824/ | Missing; field sheet not verified |
| castti | 72 × 160 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194821/ | Missing; field sheet not verified |
| hikari | 88 × 156 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194819/ | Missing; field sheet not verified |
| ochette | 88 × 152 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194818/ | Missing; field sheet not verified |
| osvald | 84 × 160 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194817/ | Missing; field sheet not verified |
| partitio | 80 × 160 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194816/ | Missing; field sheet not verified |
| temenos | 72 × 152 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194814/ | Missing; field sheet not verified |
| throne | 72 × 148 | https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/194813/ | Missing; field sheet not verified |

Front PNG dimensions are file canvas dimensions only. Character identity, native pixel scale, sheet-frame heights, and scale ratios remain unverified because no field sheets were acquired. Existing front and side files were preserved.

## NPC archive — acquired

Source page: https://www.spriters-resource.com/nintendo_switch/octopathtravelerii/asset/268009/

The user completed downloading the original archive to `/Users/kwang/Downloads/268009.zip`. It is a valid ZIP with 1,720 entries. Extracted 164 original PNGs: 148 human/human-beast `_trim.png` character sheets plus 16 separate city-NPC side idle/walk strips unchanged to `kb_raw/player_sprites/npc_<n>_sheet.png`; omitted the dog/horse sheets and weapon/battle-idle auxiliary textures. Each saved PNG was byte-compared with its ZIP member. The first sheet was visually inspected and contains directional standing/walking frames including side views; remaining sheets have not individually been visually validated. No NPC crops were requested or created.

Chrome access recovered. The complete Nintendo Switch listing has only Non-Playable Characters & Guests (13), Bosses (85), and Character Select (8). Agnea's Character Select page was visually inspected: it depicts the character on a pedestal, not town-walking cycles. No traveler field sheets are listed. The NPC archive folder names identify generic NPCs, with no traveler sheets found. All eight requested traveler side crops, front identity/scale comparisons, and side index updates remain missing. No traveler source was fabricated and existing assets/index were preserved.

## NPC file provenance

All entries share the NPC source page above. ZIP member names map each renamed original to its exact source; SHA-256 identifies unchanged bytes.

| Saved file | ZIP member | Sheet size | SHA-256 |
|---|---|---|---|
| npc_1_sheet.png | `NPC/2010_MntYf001_Fml/ChrNpcTX_MntYf001_Fml_trim.png` | 512 × 1024 | `5824e66b70081c291e32b4f8af9af2b5d11d7e8664ffa629a9b105dfbe26863b` |
| npc_2_sheet.png | `NPC/2040_MntSm001_Mle/ChrNpcTX_MntSm001_Mle_trim.png` | 512 × 1024 | `f53bcd2950ba2e64a9321b52dd89f422cd9fa57bb8953a7509ce260c9aaf2e40` |
| npc_3_sheet.png | `NPC/2050_MntSf001_Fml/ChrNpcTX_MntSf001_Fml_trim.png` | 512 × 512 | `82be425043600d56287922707069d409d277ed0946d146405b1dd73bdb5901f1` |
| npc_4_sheet.png | `NPC/2060_MntCm001_Cld/ChrNpcTX_MntCm001_Cld_trim.png` | 512 × 512 | `da1d74ad4795e29c591f65421182fb41b7756b477d1fa7a7c99a47d7e89d646d` |
| npc_5_sheet.png | `NPC/2070_MntCf001_Cld/ChrNpcTX_MntCf001_Cld_trim.png` | 512 × 512 | `931738b524e271b4c77b9cdf4304efb9e7905d6867ba48cd9edfccdb07123ccd` |
| npc_6_sheet.png | `NPC/2100_DstYm001_Mle/ChrNpcTX_DstYm001_Mle_trim.png` | 512 × 512 | `e51bc036ca1d22b31e98eb6312af98fd1200d98bf6aeba9b484e2511f3515387` |
| npc_7_sheet.png | `NPC/2120_DstYf001_Fml/ChrNpcTX_DstYf001_Fml_trim.png` | 512 × 1024 | `cdc223f0815004dd1244938edb078c4975ef3111912f8e22d99723f5174f4db2` |
| npc_8_sheet.png | `NPC/2130_DstMm001_Mle/ChrNpcTX_DstMm001_Mle_trim.png` | 512 × 1024 | `007b7415fd3ba6e7ee8ebfc9da3495ea4d81fba6e27bcff384d6eff0ca1e5930` |
| npc_9_sheet.png | `NPC/2140_DstMf001_Fml/ChrNpcTX_DstMf001_Fml_trim.png` | 512 × 1024 | `643eb1cd0b736cf5f89b7dfa94ce93284e10646a2edb659ac10b630335c3281f` |
| npc_10_sheet.png | `NPC/2150_DstSm001_Mle/ChrNpcTX_DstSm001_Mle_trim.png` | 512 × 1024 | `5e85abd6d4190a1788c152a341cdac77da7670696ea2b6db1ccb2b2d294ec717` |
| npc_11_sheet.png | `NPC/2160_DstSf001_Fml/ChrNpcTX_DstSf001_Fml_trim.png` | 512 × 1024 | `86852b0f1e598c707a3b2883d9d8a388ecfa2ecbaf46eab22a9304e65a5ae0a7` |
| npc_12_sheet.png | `NPC/2170_DstCm001_Cld/ChrNpcTX_DstCm001_Cld_trim.png` | 512 × 512 | `35c395af53df093000f6cb75c09f3f2b58ff754cefb1eaa5b3e04de034ce0960` |
| npc_13_sheet.png | `NPC/2180_DstCf001_Cld/ChrNpcTX_DstCf001_Cld_trim.png` | 512 × 512 | `6cd5489d51c48cc16ad3109f9e789fdd28506c7e291e56adde4a6f306f789691` |
| npc_14_sheet.png | `NPC/2200_CtyYm001_Mle/ChrNpcTX_CtyYm001_Mle_trim.png` | 512 × 1024 | `e343991b8646511d8761d949d7558b4bfa189addfd366e2ef7cd9a589989c227` |
| npc_15_sheet.png | `NPC/2201_CtyYm002_Mle/ChrNpcTX_CtyYm002_Mle_trim.png` | 512 × 512 | `bf6aeff414922c18f5ad0c0b2325f39ed5c67d9b3b9e796f89ecc68fb86866f4` |
| npc_16_sheet.png | `NPC/2210_CtyYf001_Fml/ChrNpcTX_CtyYf001_Fml_trim.png` | 512 × 1024 | `3f9ad768b8ed0b357760dc714ee760535985ef908d6eab283f541996d350399b` |
| npc_17_sheet.png | `NPC/2240_CtySm001_Mle/ChrNpcTX_CtySm001_Mle_trim.png` | 512 × 1024 | `5def78de914403c9bac166df0fdc9a6d236fb648eaa6df72e141015ab19e3e5a` |
| npc_18_sheet.png | `NPC/2250_CtySf001_Fml/ChrNpcTX_CtySf001_Fml_trim.png` | 512 × 1024 | `c9fc93738cae7d79a15603d937d5dcaa2836a5870026ad458bc07780169aaccf` |
| npc_19_sheet.png | `NPC/2260_CtyCm001_Cld/ChrNpcTX_CtyCm001_Cld_trim.png` | 512 × 512 | `de46a06873be6297d5555406034ae40a0faccb2c8787c2fd61bc093eac57a768` |
| npc_20_sheet.png | `NPC/2270_CtyCf001_Cld/ChrNpcTX_CtyCf001_Cld_trim.png` | 512 × 512 | `1f802d8efca5cdc460dcd5814ad4d2a6fe50df2ddda12fd27a4ef4331e5d2adc` |
| npc_21_sheet.png | `NPC/2300_IsdYm001_Mle/ChrNpcTX_IsdYm001_Mle_trim.png` | 512 × 512 | `06fe1877164b81b2b74efc830b957354e1fe071a1a0f9f9d70d3faa15f119756` |
| npc_22_sheet.png | `NPC/2310_IsdYf001_Fml/ChrNpcTX_IsdYf001_Fml_trim.png` | 512 × 512 | `382c9599387ebe73c8d0fc2cbd90294ef38089381b2cb853b8cf0352e5a0952a` |
| npc_23_sheet.png | `NPC/2320_IsdMm001_Mle/ChrNpcTX_IsdMm001_Mle_trim.png` | 256 × 1024 | `248f30bc38aa0abf0892a3ba1ab740686227c31eaa29310e6407e9c97e4fae61` |
| npc_24_sheet.png | `NPC/2330_IsdMf001_Fml/ChrNpcTX_IsdMf001_Fml_trim.png` | 512 × 1024 | `c40d1f0488cc5d294c3dfff40e7ce6efc1f780da39df900ca9ce140e9c0bd599` |
| npc_25_sheet.png | `NPC/2340_IsdSm001_Mle/ChrNpcTX_IsdSm001_Mle_trim.png` | 256 × 1024 | `7db978b133e87bb7f4235d8d30ec1eb8df2fbc4b8513c96f7ddbbf0df753a292` |
| npc_26_sheet.png | `NPC/2350_IsdSf001_Fml/ChrNpcTX_IsdSf001_Fml_trim.png` | 256 × 1024 | `59dacbf42e6415eae39a29689f77a45d7fec23ec3485801f82eda993ebe312bc` |
| npc_27_sheet.png | `NPC/2360_IsdCm001_Cld/ChrNpcTX_IsdCm001_Cld_trim.png` | 512 × 512 | `27843d255e0e42441992c82943e2bf21d00c99dbda91c6cc0c292e60b8915bbf` |
| npc_28_sheet.png | `NPC/2370_IsdCf001_Cld/ChrNpcTX_IsdCf001_Cld_trim.png` | 512 × 512 | `8406961d3122dde9c30201fae54136fe04c4c5821c250e25af6ece5d364cc879` |
| npc_29_sheet.png | `NPC/2400_WldYm001_Mle/ChrNpcTX_WldYm001_Mle_trim.png` | 512 × 512 | `b3b4cf731908c02dfaed4cf7ab7b3e64d43fa134fa2485c8a3036c95deb54e9b` |
| npc_30_sheet.png | `NPC/2410_WldYf001_Fml/ChrNpcTX_WldYf001_Fml_trim.png` | 512 × 512 | `c8a8a278ef202e448260b417c8acc224aa778f3c2b6eb1473c2abcd9dc69220a` |
| npc_31_sheet.png | `NPC/2420_WldMm001_Mle/ChrNpcTX_WldMm001_Mle_trim.png` | 512 × 512 | `428ebe10eba871c3dfb03216dce30488d817c730f18f72b31ea336f8d7abda03` |
| npc_32_sheet.png | `NPC/2430_WldMm002_Mle/ChrNpcTX_WldMm002_Mle_trim.png` | 512 × 512 | `6098b9194dc6283ad6dfc3c83ed5b22e44c6f2a7d40de616a33d77b733ff94d8` |
| npc_33_sheet.png | `NPC/2440_WldSm001_Mle/ChrNpcTX_WldSm001_Mle_trim.png` | 512 × 512 | `522a8abf8b96b7d582905bc05ea302758049cb5ce982c8b7a17af4fdf686c973` |
| npc_34_sheet.png | `NPC/2450_WldSf001_Fml/ChrNpcTX_WldSf001_Fml_trim.png` | 512 × 512 | `7ce96b78725555b45ead27f2161e486fca9884b3e744538c0e81ce06332245e9` |
| npc_35_sheet.png | `NPC/2460_WldCm001_Cld/ChrNpcTX_WldCm001_Cld_trim.png` | 512 × 512 | `ce3292775306c53a10501a29275aa8c51917c377ec7362747be894f3abddbbae` |
| npc_36_sheet.png | `NPC/2470_WldCf001_Cld/ChrNpcTX_WldCf001_Cld_trim.png` | 512 × 512 | `5bdaa448ed1ef51c58fe290e5b386c71391570f4747649f4584e05d4039a79de` |
| npc_37_sheet.png | `NPC/2500_SeaYm001_Mle/ChrNpcTX_SeaYm001_Mle_trim.png` | 512 × 512 | `5b7e92e8c02ccc8a7244e5b4fcb4a4b77fec89deeecb67306d6e7968690f6450` |
| npc_38_sheet.png | `NPC/2510_SeaYf001_Fml/ChrNpcTX_SeaYf001_Fml_trim.png` | 512 × 512 | `2b4258c4e465f642e919aa135a76301730fe25ddf995fc6fed4a21cbad374b58` |
| npc_39_sheet.png | `NPC/2540_SeaSm001_Mle/ChrNpcTX_SeaSm001_Mle_trim.png` | 512 × 1024 | `466efd6538d81c15bf3ae672334dec4df403f1daf704408ff512d15af5a7ace0` |
| npc_40_sheet.png | `NPC/2550_SeaSf001_Fml/ChrNpcTX_SeaSf001_Fml_trim.png` | 512 × 512 | `bce6900bdde752467cc332a50733d7d5773b6da487cbfe0dde67a59d8287bcba` |
| npc_41_sheet.png | `NPC/2560_SeaCm001_Cld/ChrNpcTX_SeaCm001_Cld_trim.png` | 512 × 512 | `e2c9ff72d470d980893bdf43b1acfd3128b6d73cd52d05f642d57869c2725c19` |
| npc_42_sheet.png | `NPC/2570_SeaCf001_Cld/ChrNpcTX_SeaCf001_Cld_trim.png` | 512 × 512 | `639528db68decd609c29733879168865246e31433f0d6713fc64b44fee24b8c7` |
| npc_43_sheet.png | `NPC/2600_FstYm001_Mle/ChrNpcTX_FstYm001_Mle_trim.png` | 512 × 512 | `661cb5ee5ba655a9157dac974d9bcd75debcb4889a06525344abed5fc32e3461` |
| npc_44_sheet.png | `NPC/2610_FstYf001_Fml/ChrNpcTX_FstYf001_Fml_trim.png` | 512 × 1024 | `3b2b1265e4a009de57f11e06a75debb8458b588d5d0ad95a270ae688ec66861f` |
| npc_45_sheet.png | `NPC/2620_FstMf001_Fml/ChrNpcTX_FstMf001_Fml_trim.png` | 512 × 1024 | `a3cfd5a58273b84f7fddcbc744ed3917281324149f573ed56862e49712e72e4c` |
| npc_46_sheet.png | `NPC/2630_FstMf002_Fml/ChrNpcTX_FstMf002_Fml_trim.png` | 512 × 512 | `c22c288a5a227a4ff40b0baee48b1b1816fe5412d7eff7158a2cb563801474eb` |
| npc_47_sheet.png | `NPC/2640_FstSm001_Mle/ChrNpcTX_FstSm001_Mle_trim.png` | 512 × 512 | `0d5919e9428b98f1294f5c3f5231252005218618d500caf20205a86a1978cc2e` |
| npc_48_sheet.png | `NPC/2650_FstSf001_Fml/ChrNpcTX_FstSf001_Fml_trim.png` | 512 × 1024 | `85f12c73d36db535e7286d8fdb576cf9003b3d53b9d0e447e09e6a29cdc32d91` |
| npc_49_sheet.png | `NPC/2660_FstCm001_Cld/ChrNpcTX_FstCm001_Cld_trim.png` | 512 × 512 | `1053971ba7b6268ac37a380af57e19bd72db18b6eda8ad2d0c909ff2ce1eaa87` |
| npc_50_sheet.png | `NPC/2670_FstCf001_Cld/ChrNpcTX_FstCf001_Cld_trim.png` | 512 × 512 | `823eba778ed1a41c34cac7ff7387a55c3cc193024ad596447e972e64ac8c112a` |
| npc_51_sheet.png | `NPC/2700_SnwYm001_Mle/ChrNpcTX_SnwYm001_Mle_trim.png` | 512 × 1024 | `30ccdd5527707500d719fb750e5e848ed1f589aa00cbc29e0790ae75b37124f4` |
| npc_52_sheet.png | `NPC/2710_SnwYf001_Fml/ChrNpcTX_SnwYf001_Fml_trim.png` | 512 × 1024 | `46460fca6554053ef94b437d12ce0d69d5dd3a01709afc1a1b459b7fad6df51d` |
| npc_53_sheet.png | `NPC/2740_SnwSm001_Mle/ChrNpcTX_SnwSm001_Mle_trim.png` | 512 × 1024 | `534c8d98f738b5be28a3b2fd199caa84917786b10537d50c4a109f0d34d53d4d` |
| npc_54_sheet.png | `NPC/2750_SnwSf001_Fml/ChrNpcTX_SnwSf001_Fml_trim.png` | 512 × 512 | `ab11c98e81076a3ef8f620cfd7f7cd41d290e1f8cc904279198681c43af013f1` |
| npc_55_sheet.png | `NPC/2760_SnwCm001_Cld/ChrNpcTX_SnwCm001_Cld_trim.png` | 512 × 512 | `98454b9ac404c75e80beb4247a22cbe0382350dac3843be26244a39b096c3ff0` |
| npc_56_sheet.png | `NPC/2770_SnwCf001_Cld/ChrNpcTX_SnwCf001_Cld_trim.png` | 512 × 512 | `6dcae148db19987ba6889158373e4e177e4b4e000726021e87b114758f7ef6f3` |
| npc_57_sheet.png | `NPC/2800_NonCBar001_Mle/ChrNpcTX_NonCBar001_Mle_trim.png` | 512 × 512 | `9e6cce0129005ed7da699bb5c7cc08232de45cd84ba443d2bab872cb189e334d` |
| npc_58_sheet.png | `NPC/2810_NonMrc001_Mle/ChrNpcTX_NonMrc001_Mle_trim.png` | 512 × 1024 | `fb877394534cf895c89c0185b3cc49361bcb8aa9294db88c025ea49b272927fe` |
| npc_59_sheet.png | `NPC/2811_NonMrc002_Mle/ChrNpcTX_NonMrc002_Mle_trim.png` | 512 × 1024 | `a3873daeb01dec797639c5af598416f2cb162cc89689f96b4e2d45529983fe90` |
| npc_60_sheet.png | `NPC/2812_NonMrc003_Mle/ChrNpcTX_NonMrc003_Mle_trim.png` | 512 × 1024 | `3a779226afe2cdd86bcb0aed7bf72d4fcaf4e7c2000ea227a9801dd64dafb600` |
| npc_61_sheet.png | `NPC/2813_NonMrc004_Mle/ChrNpcTX_NonMrc004_Mle_trim.png` | 512 × 1024 | `f50baa21ba4559921006b8bca95959175c34381c4aa32fbe6de4ebf3dd47a916` |
| npc_62_sheet.png | `NPC/2814_NonMrc005_Mle/ChrNpcTX_NonMrc005_Mle_trim.png` | 512 × 1024 | `5d33a6d20856015024403750da395e8ea3a7e24f61ca10a776f3d769e8afed51` |
| npc_63_sheet.png | `NPC/2815_NonMrc006_Mle/ChrNpcTX_NonMrc006_Mle_trim.png` | 512 × 1024 | `68f1ef06caebd9ad8f169df79c402b29a195e4e12e59945aff58785a268e59e2` |
| npc_64_sheet.png | `NPC/2816_NonMrc007_Mle/ChrNpcTX_NonMrc007_Mle_trim.png` | 1024 × 256 | `d740a76bca9ad7a70afccae207011fbd52c7383dcd5b7eeaf85d1cfd3c6b0a01` |
| npc_65_sheet.png | `NPC/2817_NonMrc008_Mle/ChrNpcTX_NonMrc008_Mle_trim.png` | 512 × 1024 | `93907233d014f76133ce564d2299d162a1d7f503f38cc6091259aa8bb13e290a` |
| npc_66_sheet.png | `NPC/2820_NonSld001_Mle/ChrNpcTX_NonSld001_Mle_trim.png` | 512 × 1024 | `dc70fc0e7adc8a3792bf62a079298e7b6bf4c1928dd5966e5abfc2d37c15e25f` |
| npc_67_sheet.png | `NPC/2821_NonSld002_Mle/ChrNpcTX_NonSld002_Mle_trim.png` | 512 × 1024 | `00d30167367e97e151c0c900d614a005cbbc78cd96c88b4bca3c88bc1df966ef` |
| npc_68_sheet.png | `NPC/2822_NonSld003_Mle/ChrNpcTX_NonSld003_Mle_trim.png` | 512 × 512 | `e8a2bf4279ecb6b27e2782525da28e4f13e164ed671d3fc7cc0fc1a547f5a0b3` |
| npc_69_sheet.png | `NPC/2823_NonSld004_Mle/ChrNpcTX_NonSld004_Mle_trim.png` | 512 × 1024 | `9c8f742a1d7adbfed404e65d42a34d5673266aec163f3eabf2bfaffc200c1141` |
| npc_70_sheet.png | `NPC/2824_NonSld005_Mle/ChrNpcTX_NonSld005_Mle_trim.png` | 512 × 1024 | `2a8f35e3e55b58499d569c9af68aa94a7bda2002641ec7f33e2c0d3f7dc81b21` |
| npc_71_sheet.png | `NPC/2825_NonSld006_Mle/ChrNpcTX_NonSld006_Mle_trim.png` | 512 × 1024 | `60134682312a1509803926cf8f0add6010023396c5258abb0b34bed002d62c8f` |
| npc_72_sheet.png | `NPC/2826_NonSld007_Mle/ChrNpcTX_NonSld007_Mle_trim.png` | 512 × 1024 | `c29a3a9ae4c998b3fd1af15c0e09dd2340a6874e61399c06e0f6363947872712` |
| npc_73_sheet.png | `NPC/2840_KenKuSoldier_Mle/ChrEvcTX_KenKuSoldier_Mle_trim.png` | 512 × 512 | `60f37da42db5b6702f061f4823ba7374f558cf947a4cc175d25b8c51d0d702dc` |
| npc_74_sheet.png | `NPC/2841_KenMugenSoldier_Mle/ChrEvcTX_KenMugenSoldier_Mle_trim.png` | 512 × 512 | `3273e4fe5bc0059dc5573d7914b6a33b5356f2177576692890344c929dd8b8df` |
| npc_75_sheet.png | `NPC/2845_KenMaySoldier_Mle/ChrNpcTX_KenMaySoldier_Mle_trim.png` | 512 × 512 | `d5e1a2a3c1512858341dcff98b3b92bc7565d39669cc94cb58c9ac5317651250` |
| npc_76_sheet.png | `NPC/2850_ShoGang001_Mle/ChrNpcTX_ShoGang001_Mle_trim.png` | 512 × 512 | `29cc75f9299cdd8e3751f41fbef616d30962b290726185438cfd79bd443fce1d` |
| npc_77_sheet.png | `NPC/2851_ShoGang002_Mle/ChrNpcTX_ShoGang002_Mle_trim.png` | 512 × 512 | `2d823ed09f7b0646cde6c64bb76350a9e0bbc4f2dba313d6c8ed84c969c0e852` |
| npc_78_sheet.png | `NPC/2852_ShoGang003_Mle/ChrNpcTX_ShoGang003_Mle_trim.png` | 512 × 512 | `519eee50bf73c41416db9475f16a6392c155238ac04acd80ab274c3feeba4a12` |
| npc_79_sheet.png | `NPC/2855_OdoBard_Mle/ChrNpcTX_OdoBard_Mle_trim.png` | 512 × 512 | `eb1c2be63ed6016f00c4504e7620480b4cd2aa7f868d837e968ffa12ff1ddb17` |
| npc_80_sheet.png | `NPC/2860_OdoClown001_Mle/ChrNpcTX_OdoClown001_Mle_trim.png` | 512 × 1024 | `b2e068c7c8b1e29e2902cebbd7e043195e52c97f2abdba372409ead9516cab2f` |
| npc_81_sheet.png | `NPC/2861_OdoClown002_Mle/ChrNpcTX_OdoClown002_Mle_trim.png` | 512 × 1024 | `294c5d63f3900ccf2e1570023bd3b22d164dafc6b64ecdcd1d997e99a89884b6` |
| npc_82_sheet.png | `NPC/2865_GakPrisoner001_Mle/ChrNpcTX_GakPrisoner001_Mle_trim.png` | 512 × 512 | `c982fdb3cc1e8fdd268b1b325f496775e8106730476e9bfa5c88099e76ae4309` |
| npc_83_sheet.png | `NPC/2866_GakPrisoner002_Mle/ChrNpcTX_GakPrisoner002_Mle_trim.png` | 512 × 512 | `61a803981210d2a26e76ea4a7e7857514fd58d8b1fbdc224d9127f37dc89851d` |
| npc_84_sheet.png | `NPC/2867_GakPrisoner003_Mle/ChrNpcTX_GakPrisoner003_Mle_trim.png` | 512 × 512 | `40579694bc0dc89de01a3ad8232db68ccae8159d5cff3b1ac4029257e61cfe14` |
| npc_85_sheet.png | `NPC/2870_GakJailer001_Mle/ChrNpcTX_GakJailer001_Mle_trim.png` | 512 × 512 | `c7b931829c0fa000c8321c42d73e7817f76d0c2c14b850bf604619d64e839ace` |
| npc_86_sheet.png | `NPC/2875_NonRobber001_Mle/ChrNpcTX_NonRobber001_Mle_trim.png` | 512 × 1024 | `4b9ab5b030c87c1852ab34b457766f1ce15a100cf8bd8b40d09af431b6097732` |
| npc_87_sheet.png | `NPC/2876_NonRobber002_Mle/ChrNpcTX_NonRobber002_Mle_trim.png` | 256 × 1024 | `7687850e159bb250a1d0bfe1bcc8486a70ccaec96d56f5935440959167da9737` |
| npc_88_sheet.png | `NPC/2877_NonRobber003_Mle/ChrNpcTX_NonRobber003_Mle_trim.png` | 512 × 512 | `e1d1932a6d7ff8d8416fd6b6afa2506f22d0ee416f3305d62e74eb7e83aa4121` |
| npc_89_sheet.png | `NPC/2880_NonLocalRobber001_Mle/ChrNpcTX_NonLocalRobber001_Mle_trim.png` | 512 × 512 | `afcaa362ab6c2b2a8be94cb066a231ecb5945484ca55d52af02d7b88503bfac2` |
| npc_90_sheet.png | `NPC/2881_NonLocalRobber002_Mle/ChrNpcTX_NonLocalRobber002_Mle_trim.png` | 512 × 512 | `409a4722fb1fa8c581fcf5c8361d8e78fd27b3b55d1370675f49aea8dc67591e` |
| npc_91_sheet.png | `NPC/2890_NonBlackSnake001_Mle/ChrNpcTX_NonBlackSnake001_Mle_trim.png` | 512 × 512 | `739764296f94b352e569394f9ea40ddcd49933c9a6072f885db9bfebe8b596f9` |
| npc_92_sheet.png | `NPC/2891_NonBlackSnake002_Mle/ChrNpcTX_NonBlackSnake002_Mle_trim.png` | 512 × 512 | `3deec7145e808065e87a8f66d0196eeb488b3d98c46ba946d5653ba5f379f512` |
| npc_93_sheet.png | `NPC/2892_NonBlackSnake003_Mle/ChrNpcTX_NonBlackSnake003_Mle_trim.png` | 512 × 512 | `6059ff88c189d0641e73be3f4346d04bc89a98ec0ad52c8c12ba046da27bc41d` |
| npc_94_sheet.png | `NPC/2893_NonBlackSnake004_Mle/ChrNpcTX_NonBlackSnake004_Mle_trim.png` | 512 × 512 | `355cbcc2fd4147c3d30a0c2dfd74fdf10a331c5f2b82d2f14845969bfc5b2468` |
| npc_95_sheet.png | `NPC/2895_KenGladiator001_Mle/ChrNpcTX_KenGladiator001_Mle_trim.png` | 256 × 1024 | `5fbc580adb5d51e2af9512a9ec6d8d4a4ab3a9b11ac890ac6a20ee2233a60b4b` |
| npc_96_sheet.png | `NPC/2896_KenGladiator002_Mle/ChrNpcTX_KenGladiator002_Mle_trim.png` | 256 × 1024 | `ad4a17239d9aa2f6a16c1a5fa55adf31e0aeaadc65cfae307ce2f1eb17d09bdd` |
| npc_97_sheet.png | `NPC/2897_KenGladiator003_Mle/ChrNpcTX_KenGladiator003_Mle_trim.png` | 512 × 512 | `a85a35bf1bc9defe36eb8c17e0554dc4aa5efc1ca7138744ccd2389777ef5ab2` |
| npc_98_sheet.png | `NPC/2898_KenGladiator004_Mle/ChrNpcTX_KenGladiator004_Mle_trim.png` | 512 × 512 | `11d65b36123d564ead32da6e9208095b8b41139b107d8d3c28804a9eb8249bcb` |
| npc_99_sheet.png | `NPC/2900_NonBKuNbl001_Mle/ChrNpcTX_NonBKuNbl001_Mle_trim.png` | 512 × 1024 | `e8c39a23db5d47ecd2a2cf4e8ca409777abe62c4f5718727823d2a8c78484302` |
| npc_100_sheet.png | `NPC/2901_NonNbl002_Mle/ChrNpcTX_NonNbl002_Mle_trim.png` | 512 × 1024 | `a0575e35b85ad6c113d02cbf1a0b8fce047babf88a9e32982424f2ffb38c4af7` |
| npc_101_sheet.png | `NPC/2905_NonBKuNbl001_Fml/ChrNpcTX_NonBKuNbl001_Fml_trim.png` | 512 × 512 | `9ab318a7d24d230681d3f6eac8eb8272e4cef2cf15117982bcb9d111c6a80424` |
| npc_102_sheet.png | `NPC/2910_NonTmpKnt001_Mle/ChrNpcTX_NonTmpKnt001_Mle_trim.png` | 512 × 1024 | `3eab5b5be82025f0cd0df8ea25e89ed51b709cd01f9a7f4fabc8fdf522cf3e61` |
| npc_103_sheet.png | `NPC/2911_NonTmpKnt002_Mle/ChrNpcTX_NonTmpKnt002_Mle_trim.png` | 512 × 1024 | `f4c636b712f20a29d1979bcac7eae78d0371a1af717b9abfee974eeea1e7ce5e` |
| npc_104_sheet.png | `NPC/2915_NonTmpKnt001_Fml/ChrNpcTX_NonTmpKnt001_Fml_trim.png` | 512 × 1024 | `127cec8d5b71f65a83ef81590de08631f7b2a0d945a331284abc9d7e25d62419` |
| npc_105_sheet.png | `NPC/2916_NonTmpKnt002_Fml/ChrNpcTX_NonTmpKnt002_Fml_trim.png` | 512 × 1024 | `a8f041fcd474ffdb871d906776f1f8f8a8c40de529406a65dc0516f7f56a4c38` |
| npc_106_sheet.png | `NPC/2920_NonPrts001_Mle/ChrNpcTX_NonPrts001_Mle_trim.png` | 512 × 1024 | `83f701fef8ad035e6618158f479413362e8375dc4bfcb54246d09fe05e1ca86f` |
| npc_107_sheet.png | `NPC/2925_NonPrts001_Fml/ChrNpcTX_NonPrts001_Fml_trim.png` | 512 × 1024 | `50af4217167bdb0e98a7b3768eb3ddd23d5e88bf4e875cae5f5202ef26d4ab68` |
| npc_108_sheet.png | `NPC/2935_NonPharmacist001_Mle/ChrNpcTX_NonPharmacist001_Mle_trim.png` | 512 × 512 | `61701ac856b721cd65b70a9f13e8e38dc71472718c6b1adca43ecad968b89652` |
| npc_109_sheet.png | `NPC/2950_NonScholar001_Mle/ChrNpcTX_NonScholar001_Mle_trim.png` | 256 × 1024 | `62e342cb10b0d23dd30c38c917ff9545e53da8a5afab966199196b993b5c4315` |
| npc_110_sheet.png | `NPC/2951_NonScholar002_Mle/ChrNpcTX_NonScholar002_Mle_trim.png` | 512 × 512 | `7f6c2d1fdba428f79594be438d4c017296bd6a3648b172a4fb1b28d0a3a5cae1` |
| npc_111_sheet.png | `NPC/2955_NonScholar001_Fml/ChrNpcTX_NonScholar001_Fml_trim.png` | 512 × 1024 | `19a73a20ec90a5d3ff2de96024459e9b40e953326b401f10ed3bfdd9b63c560c` |
| npc_112_sheet.png | `NPC/2960_NonChiefJudge_Mle/ChrNpcTX_NonChiefJudge_Mle_trim.png` | 256 × 512 | `630d4551c23fd9856ac46bc9ecb157ca8e796e711ed62f4ae32c8beeeb0308ef` |
| npc_113_sheet.png | `NPC/2965_NonJudge001_Mle/ChrNpcTX_NonJudge001_Mle_trim.png` | 128 × 1024 | `9cad55298c094408641ae85eba7bb79777b8c5a1e18839836370f8407e1b8473` |
| npc_114_sheet.png | `NPC/2970_ShoWorker001_Mle/ChrNpcTX_ShoWorker001_Mle_trim.png` | 512 × 512 | `cc2a1ae8d6de294f61085f125ae2d50df0baa4718593d5858d9d99fe2b6ec84a` |
| npc_115_sheet.png | `NPC/2971_ShoWorker002_Mle/ChrNpcTX_ShoWorker002_Mle_trim.png` | 512 × 512 | `ef60781cbb970cf76a7548e45cbc634f7a09326165dc6f6a39e97d32ebab571d` |
| npc_116_sheet.png | `NPC/2972_ShoWorker003_Mle/ChrNpcTX_ShoWorker003_Mle_trim.png` | 512 × 512 | `8bbf4ad308d05f46dda58cd7dd4faeec684aa0c02c77e2c9fe40a2b76ef39e0e` |
| npc_117_sheet.png | `NPC/2973_ShoWorker004_Fml/ChrNpcTX_ShoWorker004_Fml_trim.png` | 512 × 512 | `a1d68d95862f5502997050cd7baae2f56c14c0e7ec89a74a2273e91d6acff843` |
| npc_118_sheet.png | `NPC/2975_NonProstitute001_Fml/ChrNpcTX_NonProstitute001_Fml_trim.png` | 512 × 1024 | `74d4ecfac1f4333e6a025103337214de314fbf1ba337bc8dfdacc9e970154676` |
| npc_119_sheet.png | `NPC/2976_NonProstitute002_Fml/ChrNpcTX_NonProstitute002_Fml_trim.png` | 512 × 1024 | `dd4df8045dca13d0c8d783fb134bb20de824e66b8bd5b488128335599050f19b` |
| npc_120_sheet.png | `NPC/2977_NonProstitute003_Fml/ChrNpcTX_NonProstitute003_Fml_trim.png` | 512 × 1024 | `a7146347107398053ee0cf17c87be495d891123bef27ae0eaef392240a2820aa` |
| npc_121_sheet.png | `NPC/2980_NonOrphanCm001_Cld/ChrNpcTX_NonOrphanCm001_Cld_trim.png` | 512 × 512 | `998f67d4e1fdb56a670f5031289b08a37c1195c06a9a496832f9f7db43a06b88` |
| npc_122_sheet.png | `NPC/2981_NonOrphanCm002_Cld/ChrNpcTX_NonOrphanCm002_Cld_trim.png` | 512 × 512 | `7e23bccf49a3ad3a22625cfa374c9c6ace259941041636bee2b05fd9147d9bed` |
| npc_123_sheet.png | `NPC/2982_NonOrphanCm003_Cld/ChrNpcTX_NonOrphanCm003_Cld_trim.png` | 512 × 512 | `a8c5c8eca6c419c268b1f1fd23c1849fbfe22fb5327e46f42d4f6eefe48fc530` |
| npc_124_sheet.png | `NPC/2985_NonOrphanCf001_Cld/ChrNpcTX_NonOrphanCf001_Cld_trim.png` | 512 × 512 | `b59e827278b8023f58c160b206413310714bf282844a1ec44f3fcaa1f6e43893` |
| npc_125_sheet.png | `NPC/2986_NonOrphanCf002_Cld/ChrNpcTX_NonOrphanCf002_Cld_trim.png` | 512 × 512 | `a685835c551502dee207f670480a1bfe35a2562bb733dad916a23e581c4d772d` |
| npc_126_sheet.png | `NPC/2987_NonOrphanCf003_Cld/ChrNpcTX_NonOrphanCf003_Cld_trim.png` | 512 × 512 | `0f5ca260f560a2ef7903df310696c26a79f08d4c555f6a5591357c1ee5bce71e` |
| npc_127_sheet.png | `NPC/3000_NonYm001_Mle/ChrNpcTX_NonYm001_Mle_trim.png` | 512 × 512 | `08ca6378449d7737b44fda231a3b4399cbd9f9ef87cf0d5b0f9832f6496bab1c` |
| npc_128_sheet.png | `NPC/3005_NonYf001_Fml/ChrNpcTX_NonYf001_Fml_trim.png` | 512 × 1024 | `0179a05a43b1fc355d82a9f8bde04e5104e55f01be86d9f58dced0045281cb31` |
| npc_129_sheet.png | `NPC/3010_NonSm001_Mle/ChrNpcTX_NonSm001_Mle_trim.png` | 512 × 1024 | `b7fbd2325ae5c2b4356f725775ce212a5dbfa52973dcee8230f06e644e9c9886` |
| npc_130_sheet.png | `NPC/3015_NonSf001_Fml/ChrNpcTX_NonSf001_Fml_trim.png` | 512 × 512 | `8225f7ab45b1ed75e2e5f50f080d2b58bc89eb0c8da51044b0af18c962941dd9` |
| npc_131_sheet.png | `NPC/3020_NonCm001_Cld/ChrNpcTX_NonCm001_Cld_trim.png` | 512 × 512 | `d1f4a6c5aa48af6aadba7bf644cc5426d9aec591d209b2317997bafe4290125a` |
| npc_132_sheet.png | `NPC/3025_NonCf001_Cld/ChrNpcTX_NonCf001_Cld_trim.png` | 512 × 512 | `9b862cc2fdc36ef669260e8326221059aa887a74de4191980d96425ddeeff977` |
| npc_133_sheet.png | `NPC/3040_NonPorYm001_Mle/ChrNpcTX_NonPorYm001_Mle_trim.png` | 512 × 512 | `6488bea0340052ae88b6ee29f912102c6a0b3ff99306d0b0409213b67ff96b65` |
| npc_134_sheet.png | `NPC/3045_NonPorYf001_Fml/ChrNpcTX_NonPorYf001_Fml_trim.png` | 512 × 512 | `2d34f973004ae6063c218de31c6083813518b5823dbb8368ce81aed45d80299d` |
| npc_135_sheet.png | `NPC/3050_NonPorSm001_Mle/ChrNpcTX_NonPorSm001_Mle_trim.png` | 512 × 512 | `fe36632d264aaef387ad738682127d40493e6bf93dcb491f8235ff57a47b28d9` |
| npc_136_sheet.png | `NPC/3055_NonPorSf001_Fml/ChrNpcTX_NonPorSf001_Fml_trim.png` | 512 × 512 | `69111fdef3a53a39844c971b3eecfd3876cc991a412252c8e4aa7b4eb1fc0012` |
| npc_137_sheet.png | `NPC/3060_NonPorCm001_Cld/ChrNpcTX_NonPorCm001_Cld_trim.png` | 512 × 512 | `150415d642e53ae836d0f6e8c80fa9187a1148a065b943b3c8ba678f0fe68948` |
| npc_138_sheet.png | `NPC/3065_NonPorCf001_Cld/ChrNpcTX_NonPorCm001_Cld_trim.png` | 512 × 512 | `8ebee16fccecea7182279f9f61b0c7477b31215913a9a3cf633e25178b8a879c` |
| npc_139_sheet.png | `NPC/3070_KarHumanBeast001_Fml/ChrNpcTX_KarHumanBeast001_Fml_trim.png` | 512 × 1024 | `196269e204a57c3a15e54d709d9c980c6f148a4dacac566be57a5f3200f78c26` |
| npc_140_sheet.png | `NPC/3071_KarHumanBeast002_Fml/ChrNpcTX_KarHumanBeast002_Fml_trim.png` | 512 × 1024 | `423de148dc78da2a58a620e15936c055b132eb2d365e4cadad504efd9abeb4fa` |
| npc_141_sheet.png | `NPC/3072_KarHumanBeast003_Fml/ChrNpcTX_KarHumanBeast003_Fml_trim.png` | 512 × 1024 | `99e42ddb96f3e81a46abc65c8735b0c2ddb16ae87a5d428c8cb3428f0350a2c1` |
| npc_142_sheet.png | `NPC/3073_KarHumanBeast004_Fml/ChrNpcTX_KarHumanBeast004_Fml_trim.png` | 512 × 1024 | `4ca356e3ac96a99cde0ab44abfe0badcb8bea6a3a59ed9d03355bfbd7907dbd8` |
| npc_143_sheet.png | `NPC/3075_SinHumanBeast001_Mle/ChrNpcTX_SinHumanBeast001_Mle_trim.png` | 512 × 1024 | `02788fcf6097748dd36299cb880be531a27d6f27140601c9adb2ac24859fb96e` |
| npc_144_sheet.png | `NPC/3076_SinHumanBeast002_Fml/ChrNpcTX_SinHumanBeast002_Fml_trim.png` | 512 × 512 | `e4b8d9cb19d69c3a14008300df74a3fb9406020ece6a9373312796dbcd711e37` |
| npc_145_sheet.png | `NPC/3077_SinHumanBeast003_Mle/ChrNpcTX_SinHumanBeast003_Mle_trim.png` | 1024 × 256 | `61abe21fd3cd96b03126ba88745e525fc762349d7d34d3199c0513c88f9be86f` |
| npc_146_sheet.png | `NPC/3078_SinHumanBeast004_Fml/ChrNpcTX_SinHumanBeast004_Fml_trim.png` | 512 × 512 | `57fb2528172b00cb4b3c2e44999a456ef9f2c59343a4a5a3a04129bc5bc6a5a9` |
| npc_147_sheet.png | `NPC/3080_KarHumanBeastCm001_Cld/ChrNpcTX_KarHumanBeastCm001_Cld_trim.png` | 512 × 512 | `f8dda6ca6de2f7427bd547a6245e6c50c4b6193679ff2a28ed3415dd9286baca` |
| npc_148_sheet.png | `NPC/3081_KarHumanBeastCf001_Cld/ChrNpcTX_KarHumanBeastCf001_Cld_trim.png` | 512 × 512 | `534bd543502051601ef3edd2ffa984e3d7e76264d290ae890146507bedb41e61` |
| npc_149_sheet.png | `NPC/NpcCty_Bar_001/ChrTX_NpcCty_Bar_001_Nmov_Wlk_LS.png` | 512 × 512 | `a33891d30fe05f25a72710ed036eab2e38aec4e999466ceef657ee9a1f19339e` |
| npc_150_sheet.png | `NPC/NpcCty_CF_001/ChrTX_NpcCty_CF_001_Nmov_Idl_LS.png` | 128 × 128 | `665813472dfa6f35fad4372d27b8839fb3d4d1064ee7cd034134a498cda5b397` |
| npc_151_sheet.png | `NPC/NpcCty_CF_001/ChrTX_NpcCty_CF_001_Nmov_Wlk_LS.png` | 512 × 512 | `3f358b6d19f3acc3d45449e3b950ea305bc949896c02fa209444eb8dbcdf263f` |
| npc_152_sheet.png | `NPC/NpcCty_CM_001/ChrTX_NpcCty_CM_001_Nmov_Idl_LS.png` | 512 × 512 | `28829d3d2cd38dd65a7d7c1b991ade3ef5aacf571c953f998bc9585750b7ea4b` |
| npc_153_sheet.png | `NPC/NpcCty_CM_001/ChrTX_NpcCty_CM_001_Nmov_Wlk_LS.png` | 512 × 512 | `92c2c52aed2d5963fc4b2d61931d09a439defaf795284fe053da02ceca588f04` |
| npc_154_sheet.png | `NPC/NpcCty_SF_001/ChrTX_NpcCty_SF_001_Nmov_Idl_LS.png` | 128 × 128 | `6deb61c0d79341dae24872ef537912358ade701c4b4b843ce9468bfd9cbf6f3b` |
| npc_155_sheet.png | `NPC/NpcCty_SF_001/ChrTX_NpcCty_SF_001_Nmov_Wlk_LS.png` | 512 × 512 | `b6c199a6c226e555ce4876abc25148a29fefbfd132b9b95a96febb70f40428d9` |
| npc_156_sheet.png | `NPC/NpcCty_SM_001/ChrTX_NpcCty_SM_001_Nmov_Idl_LS.png` | 128 × 128 | `afd3cf2c8bfe3edf652f4641599b897f7188202d8ac7a5cfd46fc82636c73fc6` |
| npc_157_sheet.png | `NPC/NpcCty_SM_001/ChrTX_NpcCty_SM_001_Nmov_Wlk_LS.png` | 512 × 512 | `59d75c780f9bc450b672e2ef37355e740edb9b79e660b3e1bf49f08c2605bb9c` |
| npc_158_sheet.png | `NPC/NpcCty_SM_002/ChrTX_NpcCty_SM_002_Nmov_Wlk_LS.png` | 512 × 512 | `95760b18cff5bd1ff6eda6f4f45f263b0977eb038b6d7435a7cc351137e9bbbd` |
| npc_159_sheet.png | `NPC/NpcCty_Sld_001/ChrTX_NpcCty_Sld_001_Nmov_Wlk_LS.png` | 512 × 512 | `5a72887365dbe7939c408c51893fe579bdd0ec91a2f98b9699108bd0f12deb0b` |
| npc_160_sheet.png | `NPC/NpcCty_YF_001/ChrTX_NpcCty_YF_001_Nmov_Wlk_LS.png` | 512 × 512 | `2176a4c3d34a4048e0dfed7fa877289a4e83e59b74a747062b09adfbf1071d48` |
| npc_161_sheet.png | `NPC/NpcCty_YF_002/ChrTX_NpcCty_YF_002_Nmov_Wlk_LS.png` | 512 × 512 | `a8a69e2e4a2ab26caad93ba7efe190cc82b2c1eb5c68e533562d69326b51ab4c` |
| npc_162_sheet.png | `NPC/NpcCty_YM_001/ChrTX_NpcCty_YM_001_Nmov_Wlk_LS.png` | 512 × 512 | `a321250aba6f583e76db74f602aebf3f72a6da5d457876320dca74d6f34c7fe7` |
| npc_163_sheet.png | `NPC/NpcCty_YM_002/ChrTX_NpcCty_YM_002_Nmov_Idl_LS.png` | 128 × 128 | `6ce30d07ce71f37cf01015b0852f3df3573767d492f59fdc4ac54022ad7c4982` |
| npc_164_sheet.png | `NPC/NpcCty_YM_002/ChrTX_NpcCty_YM_002_Nmov_Wlk_LS.png` | 512 × 512 | `9f9b03684fc3df413d67bf65f535f968c101cb2137033d9a101246a5437639ad` |

## Continuation — PC traveler archives found

Searched first in Chrome: https://www.spriters-resource.com/pc_computer/octopathtravelerii/ . This listing has 47 assets including a Travelers category with all eight ZIPs, uploaded by Dark_Ansem. This supersedes the earlier Switch-only missing-source finding. Lower-priority sources were not needed for discovery and have not been searched. Archive contents and field textures remain unverified until downloaded.

| Traveler | Archive page | Local sheet / four crops |
|---|---|---|
| agnea | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265699/ | Awaiting ZIP; missing |
| castti | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265698/ | Awaiting ZIP; missing |
| hikari | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265697/ | Awaiting ZIP; missing |
| ochette | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265696/ | Awaiting ZIP; missing |
| osvald | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265695/ | Awaiting ZIP; missing |
| partitio | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267997/ | Awaiting ZIP; missing |
| temenos | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267998/ | Awaiting ZIP; missing |
| throne | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267999/ | Awaiting ZIP; missing |

Chrome download controls were invoked, but no traveler ZIP appeared in ~/Downloads. The supported media download operation timed out after 45 seconds; direct retrieval returned HTTP 403. Requested that the user complete the downloads. No sheet pixels or crops have been fabricated.

Deleted the explicitly identified wrong agnea_side.png and hikari_side.png and removed their index entries. Existing front sprites and NPC sheets are preserved. Four-view crop boxes, identity comparison and scale ratios remain pending.

## Final acquisition pass — original traveler field textures

All eight user-downloaded PC traveler ZIPs are valid. Each contains the default J000 field texture named ChrPlyTX_*_trim.png, separate from battle, unique-action and alternate-costume textures. Original sheets are 512 × 1024 RGBA PNGs and are copied byte-for-byte to kb_raw/player_sprites/<name>_sheet.png. ZIPs remain unchanged in ~/Downloads. The first-priority PC listing supplied all travelers, so later search sources were unnecessary. This section supersedes earlier missing-download statements.

All coordinates below are zero-based half-open pixel boxes (left, top, right, bottom). Crops are tight to the figure, preserve the original RGBA pixels and alpha, and include feet. No scaling or key-color replacement was needed. Front means the forward-facing standing pose; left is the more side-facing/three-quarter standing pose. Atlas positions differ by traveler. Right-facing output is pending user confirmation to mirror because no separate right-facing idle was identified.

| Traveler | Source / ZIP member / original SHA-256 | View | Pixel box | Crop size | scale_vs_front |
|---|---|---|---|---|---|
| agnea | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265699/<br>`Agnea/1700_OdoJ000_Fml/ChrPlyTX_OdoJ000_Fml_trim.png`<br>`426fc3fa4014cd021e113db1ff9407c8d9b0dcf42a4e6e983a6361654ff9e53f` | front | (198, 80, 234, 154) | 36 × 74 | 0.5 |
| agnea | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265699/<br>`Agnea/1700_OdoJ000_Fml/ChrPlyTX_OdoJ000_Fml_trim.png`<br>`426fc3fa4014cd021e113db1ff9407c8d9b0dcf42a4e6e983a6361654ff9e53f` | back | (2, 322, 38, 396) | 36 × 74 | 0.5 |
| agnea | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265699/<br>`Agnea/1700_OdoJ000_Fml/ChrPlyTX_OdoJ000_Fml_trim.png`<br>`426fc3fa4014cd021e113db1ff9407c8d9b0dcf42a4e6e983a6361654ff9e53f` | left | (2, 80, 36, 154) | 34 × 74 | 0.5 |

agnea: existing front is 72 × 148; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.

| castti | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265698/<br>`Casti/1100_KusJ000_Fml/ChrPlyTX_KusJ000_Fml_trim.png`<br>`6b427f90aa4508e488415f5e8466773aac9535e6a229dc943c7fdabd88b10573` | front | (238, 406, 274, 486) | 36 × 80 | 0.5 |
| castti | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265698/<br>`Casti/1100_KusJ000_Fml/ChrPlyTX_KusJ000_Fml_trim.png`<br>`6b427f90aa4508e488415f5e8466773aac9535e6a229dc943c7fdabd88b10573` | back | (94, 574, 130, 654) | 36 × 80 | 0.5 |
| castti | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265698/<br>`Casti/1100_KusJ000_Fml/ChrPlyTX_KusJ000_Fml_trim.png`<br>`6b427f90aa4508e488415f5e8466773aac9535e6a229dc943c7fdabd88b10573` | left | (132, 322, 162, 400) | 30 × 78 | 0.4875 |

castti: existing front is 72 × 160; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.

| hikari | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265697/<br>`Hikari/1000_KenJ000_Mle/ChrPlyTX_KenJ000_Mle_trim.png`<br>`1ddde75f9c33aab77b36878f63a2c769a7d204a39b3b5f76d05642f7e5ea6208` | front | (64, 460, 108, 538) | 44 × 78 | 0.5 |
| hikari | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265697/<br>`Hikari/1000_KenJ000_Mle/ChrPlyTX_KenJ000_Mle_trim.png`<br>`1ddde75f9c33aab77b36878f63a2c769a7d204a39b3b5f76d05642f7e5ea6208` | back | (182, 542, 220, 620) | 38 × 78 | 0.5 |
| hikari | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265697/<br>`Hikari/1000_KenJ000_Mle/ChrPlyTX_KenJ000_Mle_trim.png`<br>`1ddde75f9c33aab77b36878f63a2c769a7d204a39b3b5f76d05642f7e5ea6208` | left | (2, 298, 36, 372) | 34 × 74 | 0.47435897435897434 |

hikari: existing front is 88 × 156; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.

| ochette | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265696/<br>`Ochette/1500_KarJ000_Fml/ChrPlyTX_KarJ000_Fml_trim.png`<br>`18d8d5c14b0691d1e3eaf145563c39361157bdd6a7edcbecb0d35c2fc59ce8fb` | front | (170, 170, 210, 246) | 40 × 76 | 0.5 |
| ochette | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265696/<br>`Ochette/1500_KarJ000_Fml/ChrPlyTX_KarJ000_Fml_trim.png`<br>`18d8d5c14b0691d1e3eaf145563c39361157bdd6a7edcbecb0d35c2fc59ce8fb` | back | (178, 250, 218, 326) | 40 × 76 | 0.5 |
| ochette | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265696/<br>`Ochette/1500_KarJ000_Fml/ChrPlyTX_KarJ000_Fml_trim.png`<br>`18d8d5c14b0691d1e3eaf145563c39361157bdd6a7edcbecb0d35c2fc59ce8fb` | left | (194, 570, 238, 646) | 44 × 76 | 0.5 |

ochette: existing front is 88 × 152; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.

| osvald | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265695/<br>`Osvald/1300_GakJ000_Mlb/ChrPlyTX_GakJ000_Mlb_trim.png`<br>`ab3e540bb33c9d8903a7851421a8fc3d2e0211a16edd6eb511f2edf93d345a10` | front | (320, 474, 362, 554) | 42 × 80 | 0.5 |
| osvald | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265695/<br>`Osvald/1300_GakJ000_Mlb/ChrPlyTX_GakJ000_Mlb_trim.png`<br>`ab3e540bb33c9d8903a7851421a8fc3d2e0211a16edd6eb511f2edf93d345a10` | back | (370, 558, 414, 638) | 44 × 80 | 0.5 |
| osvald | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/265695/<br>`Osvald/1300_GakJ000_Mlb/ChrPlyTX_GakJ000_Mlb_trim.png`<br>`ab3e540bb33c9d8903a7851421a8fc3d2e0211a16edd6eb511f2edf93d345a10` | left | (128, 76, 170, 148) | 42 × 72 | 0.45 |

osvald: existing front is 84 × 160; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.

| partitio | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267997/<br>`Partitio/1600_ShoJ000_Mle/ChrPlyTX_ShoJ000_Mle_trim.png`<br>`0253086f638cb424a69716c791251266e1a784b9204520931017cd605c12e8d3` | front | (460, 482, 500, 562) | 40 × 80 | 0.5 |
| partitio | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267997/<br>`Partitio/1600_ShoJ000_Mle/ChrPlyTX_ShoJ000_Mle_trim.png`<br>`0253086f638cb424a69716c791251266e1a784b9204520931017cd605c12e8d3` | back | (90, 566, 126, 646) | 36 × 80 | 0.5 |
| partitio | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267997/<br>`Partitio/1600_ShoJ000_Mle/ChrPlyTX_ShoJ000_Mle_trim.png`<br>`0253086f638cb424a69716c791251266e1a784b9204520931017cd605c12e8d3` | left | (42, 238, 78, 314) | 36 × 76 | 0.475 |

partitio: existing front is 80 × 160; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.

| temenos | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267998/<br>`Temenos/1400_SinJ000_Mle/ChrPlyTX_SinJ000_Mle_trim.png`<br>`6d0d125296767a00a110cf541b7056d42c1723481c2275f126f8a49a917fdb38` | front | (244, 460, 280, 536) | 36 × 76 | 0.5 |
| temenos | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267998/<br>`Temenos/1400_SinJ000_Mle/ChrPlyTX_SinJ000_Mle_trim.png`<br>`6d0d125296767a00a110cf541b7056d42c1723481c2275f126f8a49a917fdb38` | back | (50, 302, 86, 376) | 36 × 74 | 0.4868421052631579 |
| temenos | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267998/<br>`Temenos/1400_SinJ000_Mle/ChrPlyTX_SinJ000_Mle_trim.png`<br>`6d0d125296767a00a110cf541b7056d42c1723481c2275f126f8a49a917fdb38` | left | (90, 380, 128, 454) | 38 × 74 | 0.4868421052631579 |

temenos: existing front is 72 × 152; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.

| throne | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267999/<br>`Throne/1200_TouJ000_Fml/ChrPlyTX_TouJ000_Fml_trim.png`<br>`d7fe81ca1f3912bf7d7ed2aed1ac487f576785e2764eccc6505b629c3e5fff9e` | front | (162, 158, 198, 232) | 36 × 74 | 0.5 |
| throne | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267999/<br>`Throne/1200_TouJ000_Fml/ChrPlyTX_TouJ000_Fml_trim.png`<br>`d7fe81ca1f3912bf7d7ed2aed1ac487f576785e2764eccc6505b629c3e5fff9e` | back | (42, 236, 78, 310) | 36 × 74 | 0.5 |
| throne | https://www.spriters-resource.com/pc_computer/octopathtravelerii/asset/267999/<br>`Throne/1200_TouJ000_Fml/ChrPlyTX_TouJ000_Fml_trim.png`<br>`d7fe81ca1f3912bf7d7ed2aed1ac487f576785e2764eccc6505b629c3e5fff9e` | left | (32, 2, 64, 76) | 32 × 74 | 0.5 |

throne: existing front is 72 × 148; exact repeated 2×2 pixel blocks: True. Visual identity/clothing matches the default traveler. The old front uses 2× native pixel units; crop-height ratios above also reflect pose/direction height differences, so they need not all equal 0.5.


## Completion — four views per traveler

User authorized horizontal mirroring for right-facing output. Each right crop is an exact horizontal reversal of the corresponding left crop, with no scaling, recoloring, or alpha changes. Right files are derived assets, not separately ripped right-facing frames. Earlier pending/missing statements describe historical acquisition stages and are superseded by this completion section.

| Traveler | Right file | Derived from sheet box | Size | scale_vs_front |
|---|---|---|---|---|
| agnea | agnea_right.png | mirror of (2, 80, 36, 154) | 34 × 74 | 0.5 |
| castti | castti_right.png | mirror of (132, 322, 162, 400) | 30 × 78 | 0.4875 |
| hikari | hikari_right.png | mirror of (2, 298, 36, 372) | 34 × 74 | 0.47435897435897434 |
| ochette | ochette_right.png | mirror of (194, 570, 238, 646) | 44 × 76 | 0.5 |
| osvald | osvald_right.png | mirror of (128, 76, 170, 148) | 42 × 72 | 0.45 |
| partitio | partitio_right.png | mirror of (42, 238, 78, 314) | 36 × 76 | 0.475 |
| temenos | temenos_right.png | mirror of (90, 380, 128, 454) | 38 × 74 | 0.4868421052631579 |
| throne | throne_right.png | mirror of (32, 2, 64, 76) | 32 × 74 | 0.5 |

Missing requested deliverables: none. Eight unchanged original field sheets and 32 transparent native-resolution four-view crops are present. The eight ZIPs remain in ~/Downloads. The known-wrong agnea_side.png and hikari_side.png are absent; the index has no dangling file references. Existing <name>.png front assets were preserved.

Validation: 1,023 unit tests passed in the preceding crop pass; CLI --help passed. Final asset audit checks all 32 crop pixels (including exact right mirroring), source ZIP byte identity, metadata and scale ratios. No live/model tests, commits, or unrelated file edits.
