# E3: Thinking for the Baseline Writer (roadmap 2.7)

**Date:** 2026-10-19
**Result:** thinking off won 3 pairs, adaptive won 2, and there were no ties. Adaptive needed a majority of the decided pairs, so `baseline.thinking` stays `off`.

## Setup

- **Cases:** the first case of each test-suite group, 5 in all.
- **Runs:** each case got one scene context (Director, Sonnet 4.6, thinking off). The baseline writer (Opus 4.6, effort high) then wrote twice from that same context: once with `thinking: off` (`config/models.yaml`) and once with `thinking: adaptive` (`eval/e3_models_adaptive.yaml`). All runs went through the relay (`api_host` `api.sandboxai.top`).
- **Judging:**
  - Each pair was packed twice, first in random order and then swapped.
  - Each packet was judged in its own Codex session (`gpt-6.1-sol`, effort high) with `eval/judge_pairwise.md`, with the session's working directory set to the packet, outside the repo.
  - The session logs show no reads outside the packets, and the packet stories are byte-identical to the runs.
  - A pair goes to an arm only if both judgments agree.
- **Raw data:** run IDs, packets, and verdicts are in `e3_thinking_baseline_verdicts.json`.

## Results

| Case | Off run | Adaptive run | Judge 1 | Judge 2 (swapped) | Pair |
|---|---|---|---|---|---|
| osvald_temenos_1 (Montwise) | `114022-89d03f` | `114147-5136ae` | adaptive | adaptive | **adaptive** |
| agnea_throne_1 (Merry Hills) | `114018-7e4afb` | `114141-c58cb4` | off | off | **off** |
| hikari_ochette_1 (southern Oresrush wilds) | `114023-d292e8` | `114151-0fb541` | adaptive | adaptive | **adaptive** |
| castti_partitio_1 (Oresrush) | `114008-d87107` | `114206-0fb04f` | off | off | **off** |
| osvald_temenos_agnea_1 (New Delsta) | `114026-ae20a4` | `114206-193972` | off | off | **off** |

The table abbreviates run IDs; all of them start with `20261019-`.

Pairs by axis:

| Axis | Off | Adaptive | Tie |
|---|---|---|---|
| Lore | 0 | 2 | 3 |
| Voice | 3 | 2 | 0 |
| Readability | 2 | 1 | 2 |

## Cost and thinking

The costs are the SDK's `total_cost_usd`, calculated at official rates.

| Case | Scene context | Writer off | Writer adaptive | Adaptive thinking (blocks / chars) | Words (off / adaptive) |
|---|---|---|---|---|---|
| osvald_temenos_1 | $0.19 | $0.14 | $0.17 | 1 / 4,382 | 2,084 / 2,384 |
| agnea_throne_1 | $0.19 | $0.13 | $0.19 | 1 / 4,044 | 1,903 / 3,159 |
| hikari_ochette_1 | $0.22 | $0.19 | $0.15 | 1 / 3,330 | 2,048 / 2,082 |
| castti_partitio_1 | $0.16 | $0.20 | $0.18 | 2 / 3,814 | 2,788 / 2,345 |
| osvald_temenos_agnea_1 | $0.33 | $0.18 | $0.20 | 1 / 6,884 | 2,501 / 2,758 |
| **Total** | **$1.09** | **$0.84** | **$0.88** | | |

The E3 total was $2.81. Every adaptive run thought, and no off run did.

## Observations

- **Consistent judges:** each judge agreed with itself across the swap in all 5 pairs, so there was no position bias.
- **Lore favors thinking:** adaptive won lore in both pairs where lore was decided. The judges caught canon slips in off stories:
  - Osvald spending five years believing Elena was alive
  - the Sacred Flame's origin
  - Throné's collar recalled as a wrist cuff
  
  These are the slips the validator (Phase 4) must catch, and thinking may help the validator itself (4.3).
- **Voice favors off (3 to 2):** the judges found that adaptive stories over-explain. One "repeatedly explains the same lesson", and Osvald's analytical tics were "pushed toward caricature" ("impact-to-audience ratio").
- **Cost didn't decide it:** thinking cost about 5% more across the five writer runs.
- **Weak evidence:** with 5 pairs, a 3-to-2 result is weak. Rerun if the writer prompt changes materially.
