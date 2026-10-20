# 03: The comparison record and the verdict

**What to build:** A committed, dated **Model comparison** that a reviewer can read without the CI artifacts or the maintainer's local reports, plus a verdict.

The reference side is the three Opus runs on prompt 1.3.0: the `eval-report` artifacts of CI runs 37065847534, 37066259507 and 37536287167, which expire around 2026-12-31. The first candidate is Haiku: the three reports from ticket 02, in `.cache/phase-1.5-runs/run-N/`. Haiku failed widely, so Sonnet 5.5 was added as the second candidate (ticket 06): its three reports are in `.cache/phase-1.5-runs/sonnet-run-N/`. Nine runs in all.

Build one file under `eval/`, named `model-comparison-<date>`, in JSON and shaped like `baseline-2026-09-29.json`. It holds:
- the reference and candidate configurations, and the prompt and schema versions;
- documents per run;
- the per-run totals of all nine runs;
- each side's spread per metric (structural and tunable precision and recall, appendix rate, punctuation, every hard-gate count, labelling failures, errors, retries, tokens, cost, wall time);
- each run's gate result;
- the sources (CI run ids, local run labels and dates);
- a `notes` field saying the sides differ in effort as well as model (Opus `medium`, Haiku `high`, Sonnet `medium`);
- a `verdict` field.

The verdict rule comes from the spec. Any hard-gate breach, wrongful removal, labelling failure or non-provider error in any Haiku run disqualifies it. Thresholds are applied unchanged. Above the gate, write a recommendation from the side-by-side numbers, and the maintainer makes the call.

If Haiku failed, don't define "narrow" or "wide" in advance. Say what failed, where, and whether one cause explains it, then give the maintainer your advice: a prompt tweak, or move on to Sonnet 5.5. Whatever the outcome, the file is committed. A negative result is evidence too.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** 02 (The Haiku runs), 06 (The Sonnet runs)

**Status:** done

- [x] The three Opus artifacts were downloaded, and each was re-checked as `claude-opus-5-5`, `medium`, prompt 1.3.0, 48 documents, 48 live calls, the cache not read
- [x] The comparison file is committed. Every number in it was checked against its source report, and the ticket comment says so
- [x] The comparison file names all nine sources and states the difference in effort
- [x] A markdown table setting both sides beside each other (per-run figures and spreads, for all three sides) and the verdict with its reasoning are posted as a comment below
- [x] The maintainer's decision is recorded in a comment: switch the default (go to ticket 04), tweak the prompt, or test Sonnet (Haiku: move on to Sonnet; Sonnet: switch the default)
- [x] The Baseline file and `eval/thresholds.yaml` are untouched

## Comments

**2026-10-19, comparison record and verdict.** The record is `eval/model-comparison-2026-10-19.json` (reference: Opus 5.5 at `medium`, CI runs 37065847534, 37066259507, 37536287167; candidate 1: Haiku 5.5 at `high`, local runs 1 to 3; candidate 2: Sonnet 5.5 at `medium`, local runs 1 to 3). The sides differ in effort as well as model. All nine runs: prompt 1.3.0, schema 1.0.0, 48 documents, 48 live calls, cache not read, no retries. The three Opus artifacts were downloaded and re-checked as `claude-opus-5-5`, `medium`, no `extra`. Both 5.5 candidates ran with `max_tokens` 128000 through `CVR_LABEL_EXTRA`, because the locked langchain-anthropic has no model profile for them. A fourth, accidental Opus run (PASS, $3.3247) is in the file's notes and kept out of the reference spread.

| Per run (1 / 2 / 3), spread in brackets | Opus 5.5 medium (reference) | Haiku 5.5 high | Sonnet 5.5 medium |
|---|---|---|---|
| Gate | PASS / PASS / PASS | FAIL / FAIL / FAIL | PASS / PASS / PASS |
| Wrongful removals | 0 / 0 / 0 | 2 / 4 / 3 [2 to 4] | 0 / 0 / 0 |
| Other hard-gate counts, labelling failures, errors, retries | all 0 | all 0 | all 0 |
| Structural precision = recall | 100 / 100 / 100 | 100 / 99.72 / 99.81 [99.72 to 100] | 100 / 100 / 100 |
| Tunable precision | 99.91 / 100 / 100 [99.91 to 100] | 98.94 / 98.41 / 98.59 [98.41 to 98.94] | 99.56 / 99.73 / 99.65 [99.56 to 99.73] |
| Tunable recall | 99.91 / 100 / 100 [99.91 to 100] | 99.02 / 98.49 / 98.94 [98.49 to 99.02] | 99.65 / 99.73 / 99.65 [99.65 to 99.73] |
| Appendix rate (%) | 0.70 / 0.70 / 0.70 | 1.30 / 1.34 / 1.09 [1.09 to 1.34] | 0.70 / 0.70 / 0.70 |
| Input tokens | 269,974 each | 269,974 each | 269,974 each |
| Output tokens | 111,810 / 112,533 / 112,309 | 227,427 / 229,659 / 226,587 | 105,330 / 105,274 / 105,253 |
| Cost (USD) | 3.3161 / 3.3306 / 3.3261 [3.3161 to 3.3306] | 0.1407 / 0.1418 / 0.1403 [0.1403 to 0.1418] | 1.5932 / 1.5927 / 1.5925 [1.5925 to 1.5932] |
| Wall time (s) | 216.0 / 237.8 / 213.6 [213.6 to 237.8] | 201.0 / 200.1 / 202.2 [200.1 to 202.2] | 163.3 / 138.8 / 138.5 [138.5 to 163.3] |

Thresholds applied unchanged: tunable placement at least 98%, appendix at most 2%, punctuation hard.

**Verdict.**
- **Haiku 5.5 at `high`: disqualified.** It failed the hard gates in all three runs. Three patterns: `RM_REFEREE` removes c04's "with a reference available" (every run); `RM_PERSONAL` removes c07's "EU citizen" (runs 2 and 3); quotes are clipped at commas and clause ends (c05, c08, c12, c10), which breaks structural leaves in runs 2 and 3 and doubles the appendix rate. No added or dropped text, provenance, PII, image or labelling failure. It costs about $0.14 a run (96% less than Opus), but removed content lines are not a trade the gate allows.
- **Sonnet 5.5 at `medium`: recommended.** It passed every gate on every run with every hard-gate count at zero, structural 100/100 and appendix 0.70%, the same as Opus. Tunable placement is 99.56 to 99.73 against Opus's 99.91 to 100, well above the 98% threshold. Its only systematic difference from Opus: it files c04's second profile paragraph under Additional (a section choice, no wording lost). It costs about $1.59 a run against $3.32 (52% less) and runs in 139 to 163 s against 214 to 238 s (about 30 to 35% faster). It matches Opus's effort, so the comparison isolates the model.

**Maintainer's decisions (2026-10-19).** Haiku: a wide gap; move on to Sonnet 5.5 (ticket 06). A Haiku-specific prompt approach might be tried later; nothing is planned. Sonnet: switch the default to Sonnet 5.5 at `medium` (ticket 04, done in parallel); the 128K `max_tokens` has to live in code.

**Checking.** Every number in the record was checked against its source report twice: once when the file was generated straight from the reports, and again by a separate script that re-read the nine reports and compared per-run totals, gate results, tokens, cost, wall time, configurations and every spread (no mismatches). Neither script is committed. The Baseline file and `eval/thresholds.yaml` are untouched.