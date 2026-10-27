# WE4 and WE Phase test

Date: 2026-10-27 (Asia/Shanghai). **WE4 PASS; WE Phase test FAIL (8/10 completion, required ≥9/10).**
The single full suite attempt is finished. No simulation case was rerun. No commit or push was made.

## Implementation and local checks

WE4 changes `src/story_engine/eval/world.py`, `prompts/world_judge.md`, and fake-SDK tests in
`tests/unit/test_eval_world.py`. Code lists commitments past their time and still unreleased,
and situations past due and still open, using the configured part-of-day order. The judge
classifies fulfillment/closure evidence and cites each candidate's path and durable ID.
With candidates present, its state-finding schema enumerates legal paths. With no candidates,
state_follows_log is zero by construction: code requests only the other metrics, ignores and
traces unsolicited state findings, and preserves canon/continuity findings. Legacy worlds
retain the old whereabouts/commitment/situation rule. No text-content heuristics were added.

- `uv sync`: passed; no dependency changes.
- `uv run pytest tests/unit`: **873 passed**, no live model calls.
- `uv run story-engine --help`: passed.
- `git diff --check`: passed.

## WE4 acceptance on the three specified worlds

These are the final successful targeted evaluations, after the schema and empty-candidate fixes.
The first two have no stale candidates. The third has four stale entities grouped into three
findings; it includes both required catches and no scene-move or null-spot complaints.

| World | Judge run | State findings | Canon findings (raw) | Cost |
|---|---|---:|---:|---:|
| `20261026-154814-d38670` | `20261027-042102-b2db21` | 0 | 2 | $0.26150415 |
| `20261026-154850-32c1d7` | `20261027-042155-125189` | 0 | 1 | $0.28870905 |
| `20261026-154900-298b48` | `20261027-041842-21443a` | 3 | 0 | $0.33705330 |

Required catches: `genesis:gil:0` and `reguluss_gratitude`. Other cited entries are
`genesis:dolcinaea:0` and `genesis:osvald:0`. These IDs and their stale state are real.
The Osvald explanation incorrectly calls Temenos's release suspicious: genesis does contain
`genesis:temenos:0`, and event 78 validly releases that commitment. Osvald's separate commitment
is still unreleased. This is an explanation error, not a fold failure.

Initial acceptance runs were `20261026-164014-17c727`, `20261026-164104-17859f`, and
`20261026-164219-fafa48` ($0.88071060). Subsequent targeted acceptance attempts and their
failures are retained; all are included in the cost ledger below.

## Full suite method and results

Manifest: `runs/suites/we4_overnight.json`. The serial task driver
`runs/we4_overnight/run_suite.py` uses the same `_simulate_case` and ordinary CLI calls as
`eval run-suite --mode simulation --stop-after day`, preserving all ten original inputs.
It saves the manifest after each case and evaluates each created world immediately.
`stopped` is the expected successful run status for `--stop-after day`.

Independent verifier: `runs/we4_overnight/verify.py`, evidence in
`runs/we4_overnight/verification.json`. It folds genesis plus all committed ops with
`load_state`, separately parses actual on-disk `state.json`, and compares the models.
All nine created worlds match, including the incomplete day. The failed initializer produced
no world (N/A, not a fold pass). Part-of-day outcomes are exactly the persisted events with
`scene is None and of is not None`: **0 across all nine worlds**.

Eight completed worlds have successful semantic reports. An incomplete day is skipped;
failed reports' empty findings are never counted as clean results. Counts below are raw
findings from the latest successful report for each completed world.

| Case | Day complete | Scenes/rounds | State findings | Canon/scope findings |
|---|---|---:|---:|---:|
| osvald_temenos_1 | yes | 4/47 | 0 | 2 |
| osvald_temenos_2 | yes | 7/45 | 0 | 2 |
| agnea_throne_1 | yes | 4/48 | 1 | 2 |
| agnea_throne_2 | yes | 5/49 | 0 | 1 |
| hikari_ochette_1 | no | — | — | — |
| hikari_ochette_2 | no | — | — | — |
| castti_partitio_1 | yes | 4/44 | 0 | 1 |
| castti_partitio_2 | yes | 4/48 | 0 | 2 |
| osvald_temenos_agnea_1 | yes | 5/58 | 2 | 2 |
| osvald_temenos_agnea_2 | yes | 8/62 | 2 | 3 |

| Case | World | Simulation run (initializer if no world) | Final successful judge | Init + simulation cost |
|---|---|---|---|---:|
| osvald_temenos_1 | `20261026-164650-3706ca` | `20261026-164651-8b35df` | `20261026-170538-d3b27d` | $2.709312 |
| osvald_temenos_2 | `20261026-170938-34a050` | `20261026-170939-dd431f` | `20261026-172142-3d41c1` | $2.242724 |
| agnea_throne_1 | `20261026-172536-1181a4` | `20261026-172537-cea58b` | `20261026-180357-53f293` | $2.404696 |
| agnea_throne_2 | `20261026-174707-6f477d` | `20261026-174708-3c7d92` | `20261027-040802-a58586` | $2.596319 |
| hikari_ochette_1 | `20261026-180834-309533` | `20261026-180834-0728e5` | `—` | $1.309645 |
| hikari_ochette_2 | `—` | `20261026-181644-dc095a` | `—` | $0.301182 |
| castti_partitio_1 | `20261026-182308-74701b` | `20261026-182309-ed65f2` | `20261026-184129-1031f1` | $2.460207 |
| castti_partitio_2 | `20261026-184510-a1d511` | `20261026-184511-c8d145` | `20261027-040935-d50d32` | $3.041825 |
| osvald_temenos_agnea_1 | `20261026-191127-f03f8c` | `20261026-191128-727c60` | `20261027-041126-9825ed` | $3.411306 |
| osvald_temenos_agnea_2 | `20261026-193725-b984b4` | `20261026-193725-908de8` | `20261027-041315-9ee41e` | $3.754348 |

### Against W1

| Metric | W1 | This attempt | Interpretation |
|---|---:|---:|---|
| Completion | 9/10 | **8/10** | Fails the WE phase threshold ≥9/10 |
| Part-of-day outcomes | 35 across the 10 suite worlds | **0 across 9 created worlds** | Data guarantee, not a prose-quality judgment |
| Fold equals saved state | Not event-sourced | **9/9 created worlds** | Includes 1 partial day; initializer failure N/A |
| state_follows_log | 25 raw findings on 9 completed suite days | **5 raw findings on 8 completed days** | WE4 is narrower; counts are not like-for-like |
| canon_and_scope | 6 raw findings on 9 completed suite days | **15 raw findings on 8 completed days** | Numerous false positives; not 15 confirmed canon errors |

W1 source: `eval/results/world_v1.md`. W1's audited settled-interaction rate was 7/10
world-days; it is not interchangeable with the part-of-day outcome count.
This attempt traces **8 event_dropped** and **14 encounter_name_dropped** records.
These show rejection handling continues in many cases, not that all validation failures
have been eliminated. Multi-day continuity and situation renewal were not tested here.

## Failures retained in the original denominator

1. **hikari_ochette_1**, run `20261026-180834-0728e5`: failed during afternoon with
   `World validation failed after one retry: closing resolution has no next minor moves`.
   Earlier trace errors include a minor-move spot mismatch and an op missing its discriminator.
   Init + simulation cost $1.30964460. Partial state still folds correctly. Semantic judge
   `20261026-181643-5b5bc7` is skipped ($0).
2. **hikari_ochette_2**, initializer `20261026-181644-dc095a`: $0.30118170, failed before
   world creation. The model returned an empty `characters` map while situations touched
   `hikari` and `ochette`; retry still failed reference validation.

Both are simulation/initializer output-boundary failures outside WE4. They are recorded,
not fixed or replaced by new simulation attempts. **The phase remains open.**

## Judge audit and remaining limitations

### State findings

Five raw findings cite four distinct stale entries in the suite:

- Agnea/Throné 1: `genesis:Veronica:0`, expired/unreleased security patrol. Morning patrol
  is visible, so the judge's afternoon-only interpretation of fulfillment is debatable.
- Three-character 1: `scholar_and_cleric_reunion`, still open after day 1 night.
  The other finding borrows this same valid path while discussing already-closed performance
  and sabotage situations. It is an unrelated-history false positive, not an omitted-op catch.
- Three-character 2: `genesis:agnea:0`, evening performance still unreleased, and
  `genesis:clarissa:0`, caregiving commitment still past its recorded time. Ongoing care may
  require a different temporal interpretation; do not infer its real-world completion from expiry.
  The Agnea explanation misreads event 113: its release is for
  `genesis:maestro_fiorello:0`, not Agnea. The stale Agnea entry is nevertheless present.

Candidate enums guarantee valid citations, not that an explanation discusses its cited
candidate. No semantic text validator or case-specific prompt rule is added for this residual.

### Canon/scope findings

Keep raw counts separate from confirmed contradictions:

- Osvald/Temenos 1: a next-day Crackridge investigation hook is visible (event 103), but the
  judge overstates it as proof Harvey is alive. A multi-site lab absent from KB is not, alone,
  a demonstrated contradiction. Scope/continuation concern remains for author review.
- Osvald/Temenos 2: World events assert a new history/theory of will-based magic (43, 86),
  and the judge flags Moonshade-book circulation. Treat as scope/authority concerns, not
  proven hard contradictions solely because the KB lacks them.
- Agnea/Throné 1: a pickpocket called Roque may be an identity collision, not Roque Brilliante;
  festival prestige does not prohibit a relaxed post-ending performance. Neither claim alone
  proves a hard contradiction.
- Agnea/Throné 2: new rival dancer Marin is allowed invented local detail. Comparing this
  new post-ending episode with Chapter 1 as though it retells that chapter is a false positive.
- Castti/Partitio 1: the railway finding reverses the timeline: post-story plans are compatible
  with a post-true-ending premise. False positive.
- Castti/Partitio 2: new local tailor Marta is allowed. A dismantled Order stronghold is not
  disproved by the game-era KB's cultist network. Neither absence-from-KB argument proves error.
- Three-character 1: the judge conflates a new performance with the canonical epilogue and
  treats Osvald's departure priority as a lore error. Unresolved sabotage may be a scope concern;
  characterization needs author judgment.
- Three-character 2: the Elena claim exposes an actual **input conflict**:
  `cards/osvald.md` says Elena is healing and has not been told his full identity;
  `kb/characters/osvald/elena_vanstein.md` says she recovered and reunited by the true ending.
  No card/KB edits are authorized here. Two other findings overlap on institutional religious
  conflict; the fall of the Sacred Guard does not establish loss of all Order authority.

The confirmation-world audits likewise found Tanzy's post-ending return supported as a
canon violation, but false positives about surviving Blacksnakes, Hikari's defeated shadow,
and a newly invented hunt target. Canon judge precision is a separate outstanding issue.

## Targeted revalidation and costs

The original driver was already imported when reference schemas and budget guards changed.
Its two candidate-reference failures were `20261026-174346-8bcf69` and
`20261026-180425-61b54e`. Fresh targeted judges repaired those reports; three other fresh
judges replaced zero-cost refusals by the superseded $18/$2 guard. All eight completed suite
worlds now have successful reports. No model config, suite input, simulation mechanism,
card or KB content changed.

An intermediate no-candidate schema restriction caused acceptance run
`20261027-041512-e2af4d` to exhaust SDK structured-output retries. The final implementation
computes the empty-domain state metric as zero and traces unsolicited findings instead of
failing the entire judge. Fake-SDK tests cover retaining canon findings and day-2 continuity.
Final live empty-candidate regressions pass without SDK retry exhaustion.

The user increased the original $20 ceiling by $50 during case 3: **$70 total**, including
prior spend. A task-local inherited guard in `runs/we4_overnight/guard/sitecustomize.py`
uses a $65 threshold and $5 session/reserve limit in fresh processes. Existing processes
retained the earlier guard, accounting for the three zero-cost refusals above.

| Cost category | SDK-reported USD |
|---|---:|
| Ten suite cases: initialization + simulation, including failures | $24.23156355 |
| Suite judges: all first attempts, failed reference attempts and targeted rechecks | $3.56243085 |
| WE4 acceptance on the three old worlds: all initial/final attempts, including failure | $2.44621425 |
| **Total** | **$30.24020865 / $70** |

All costs reconcile against new runs' `trace.jsonl` stage_usage call deltas; there are no
unknown-cost usage records. They are SDK estimates, not an independently verified provider
invoice. Evidence: `runs/we4_overnight/status.py`, `audit.json`, `suite.log`, `rejudge.log`,
`confirm.log`, `confirm_final.log`, `confirm_empty_final.log`, and each listed run's
`meta.json`, `trace.jsonl`, and `world_report.json`.

Next work requires a new contract: stabilize closing-call/initializer output boundaries,
resolve the Osvald card/KB premise conflict with the author, and assess canon-judge precision.
No second suite, runtime repair, or Phase 5 work is performed in this contract.
