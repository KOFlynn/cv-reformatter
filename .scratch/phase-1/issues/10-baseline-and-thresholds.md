# 10: Baseline and thresholds

**What to build:** The numbers the gate holds to, set by evidence. Three full eval runs on the default `LabellerConfig` with the cache bypassed (LLM output is not deterministic, so one run is a sample of one). The dated baseline file records all three runs and their spread per metric; a wide spread is itself a finding written into the baseline notes, because it says the prompt is unstable. `thresholds.yaml` is then set: `placement_accuracy.min` to the worst of the three less one to two points of headroom, rounded down; `appendix_rate.max` to the worst plus the same headroom, rounded up; `punctuation_fidelity.hard: true` iff all three runs are clean, otherwise the reason it stays soft is recorded. The per-layout and per-tag breakdowns are read for anything structural (a Layout or a tag failing across all three runs) and each such finding becomes a note in the baseline and, if it is a defect, a follow-up ticket rather than a threshold adjustment. If effort or model is changed to reach an acceptable baseline, the change and the numbers behind it go in the baseline file and the PR description, per the eval-run rule.

**Blocked by:** 09 (Eval runner and report), 17 (Removal precision hard gate), 18 (Narrow RM_PERSONAL in the prompt)

**Status:** in-review

- [x] Three runs completed with `--no-cache`; each report kept
- [x] `eval/baseline-YYYY-MM-DD.json` committed holding the three reports' totals and breakdowns, the spread per metric, the `LabellerConfig` and versions, total cost, and notes
- [x] `thresholds.yaml` set per the procedure with the arithmetic shown in the PR description
- [x] `punctuation_fidelity` promoted iff clean three times; the decision and evidence in the baseline notes
- [x] Hard gates at zero on all three runs, or each breach traced to a defect with a ticket, before the thresholds are set
- [x] The eval runner with the final thresholds exits 0 on the cached best run and the report diff against the first run in ticket 09 is in the PR description
- [x] README eval section (ticket 08) updated with the actual thresholds and baseline link

## Comments

### 2026-09-29: baseline taken, thresholds set, in review (branch `phase-1/10-baseline-and-thresholds`)

**The three runs.** All 48 documents each, on the default `LabellerConfig` (`anthropic`, `claude-opus-5-5`, effort `medium`, no temperature), prompt 1.1.0 (`9b688aca3f8c5fa0`), schema 1.0.0. None used the cache: 0 hits, 48 live calls each.
- **Run 1** is ticket 18's live run on this prompt. The maintainer counted it instead of paying for a fourth run: same config, same prompt, and nothing but documentation changed between it and runs 2 and 3.
- **Runs 2 and 3** were taken with `--no-cache --out .cache/baseline/runN --cache-dir .cache/baseline/runN/cache`, so each run's answers stay replayable.
- The reports are kept under the gitignored `.cache/baseline/run{1,2,3}/`. They are not committed: they quote the golden set per document. The committed baseline holds their totals and breakdowns.

| Run | Tunable P / R % | Appendix % | Punctuation | Hard-gate failures | Cost | Wall time |
|---|---|---|---|---|---|---|
| 1 | 100.00 / 99.82 | 0.73 | 0 | 0 | $3.2736 | 227.9s |
| 2 | 100.00 / 99.65 | 0.76 | 0 | 0 | $3.2544 | 223.5s |
| 3 | 99.91 / 99.65 | 0.75 | 0 | 0 | $3.2767 | 225.8s |

The three runs cost **$9.8047** in all. Every hard gate held in every run: added, dropped, wrongful removals, provenance, PII, images, ordering, structural placement 100/100, label failures, errors, retries.

**The spread is narrow**, so the prompt is judged stable, not flagged:
- tunable precision: 0.09 points;
- tunable recall: 0.17 points;
- appendix rate: 0.03 points.

**Thresholds** (`eval/thresholds.yaml`; the arithmetic is also in the baseline's `thresholds`):
- `placement_accuracy.min`: the worst of tunable precision and recall over three runs is 99.65 (recall, runs 2 and 3). 99.65 − 1 = 98.65, rounded down to a whole percent: **98**.
- `appendix_rate.max`: the worst is 0.76 (run 2). 0.76 + 1 = 1.76, rounded up: **2**.
- `punctuation_fidelity.hard`: **true**. Every run had 0 punctuation findings.
- One point of headroom is the low end of the procedure's one to two. With a spread this narrow it is still about six times the widest range. Whole-percent rounding adds the rest.

**Baseline file.** `eval/baseline-2026-09-29.json` holds:
- the config and versions;
- total cost;
- the spread per metric (each run's value, min, max and range);
- the thresholds with their arithmetic;
- the notes;
- each run's totals and per-layout, per-tag and per-candidate breakdowns, with tokens, cost, wall time and retries.

It holds aggregates only, no document text. It was built by a one-off script from the three `report.json`s. The script is not committed, since `eval/` holds data and config, never code.

**Structural reading of the breakdowns** (also in the baseline's notes):
- **c06's repeated skill fails in all three runs. This is a defect, now ticket 19.** c06 lists "Microsoft Excel" twice (`duplicate-skill`). The labeller quotes it once and leaves the repeat to the appendix: in 2, 4 and 3 of the four Layouts, and in `single-column` and `header-footer` every run. The cached answers show a single `skills` reference to it. It pulls down the `duplicate-skill`, `unusual-sections` and `typo` rows, which are all c06's tags. It is not treated as a threshold matter.
- **The appendix floor is by design.** c09 ("Page 1 of 2", "Fortune favours the prepared.") and c11 (the declaration line, "Page 2 of 2") send the same unplaceable lines to the appendix in every Layout of every run (tag `unplaceable`, recall 100). They are most of the 0.7% appendix rate.
- **No Layout fails across all three runs.** Each of the four is at 99.29% tunable recall or better in every run.
- **One-off, run 3 only:** in `c04__text-box` one profile sentence was placed in `additional`. Judged sampling variance.

**The replay with the final thresholds.** `uv run python -m cvr.eval.run --cache-dir .cache/baseline/run1/cache --out <tmp>`: 48 hits, 0 live calls, **PASS**, "Thresholds: tunable placement precision and recall at least 98%, appendix rate at most 2%, punctuation fidelity hard." Runs 2 and 3 replay from their own caches and pass too. The diff of the best run against ticket 09's first run (prompt 1.0.0), totals row:

```
< |  | Docs | Added | Dropped | Provenance | PII | Images | Order fails | Structural P/R % | Tunable P/R % | Punctuation | Appendix % | Label fails | Errors |
< | all | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 100.00 / 100.00 | 100.00 / 99.56 | 0 | 0.72 | 0 | 0 |
> |  | Docs | Added | Dropped | Wrongful removals | Provenance | PII | Images | Order fails | Structural P/R % | Tunable P/R % | Punctuation | Appendix % | Label fails | Errors |
> | all | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100.00 / 100.00 | 100.00 / 99.82 | 0 | 0.73 | 0 | 0 |
```

The per-layout, per-tag and per-candidate rows are ticket 18's diff (ticket 18's comment), because run 1 is that run.

**Tests changed.** Three tests assumed the committed thresholds were the placeholders:
- `test_the_committed_thresholds_are_the_placeholders` is now `test_the_committed_thresholds_are_the_ones_the_baseline_records`. `thresholds.yaml` must equal the committed baseline's `thresholds` and name the baseline file.
- The two command tests that relied on the placeholders tolerating a lost bullet now pass an explicit admit-everything thresholds file: `test_the_same_omission_passes_thresholds_that_admit_it` and the removal-precision test.

**Docs.**
- The README's eval section has the baseline, the thresholds table and the findings, replacing "Neither file exists yet".
- `CLAUDE.md`'s status, `run.thresholds` entry and layout are updated.
