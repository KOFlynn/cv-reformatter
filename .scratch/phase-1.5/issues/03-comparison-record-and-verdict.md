# 03: The comparison record and the verdict

**What to build:** A committed, dated **Model comparison** that a reviewer can read without the CI artifacts or the maintainer's local reports, plus a verdict.

The reference side is the three Opus runs on prompt 1.3.0: the `eval-report` artifacts of CI runs 37065847534, 37066259507 and 37536287167, which expire around 2026-12-31. The candidate side is the three Haiku reports from ticket 02, in `.cache/phase-1.5-runs/run-N/`.

Build one file under `eval/`, named `model-comparison-<date>`, in JSON and shaped like `baseline-2026-09-29.json`. It holds:
- the reference and candidate configurations, and the prompt and schema versions;
- documents per run;
- the per-run totals of all six runs;
- each side's spread per metric (structural and tunable precision and recall, appendix rate, punctuation, every hard-gate count, labelling failures, errors, retries, tokens, cost, wall time);
- each run's gate result;
- the sources (CI run ids, local run labels and dates);
- a `notes` field saying the sides differ in effort as well as model (Opus `medium`, Haiku `high`);
- a `verdict` field.

The verdict rule comes from the spec. Any hard-gate breach, wrongful removal, labelling failure or non-provider error in any Haiku run disqualifies it. Thresholds are applied unchanged. Above the gate, write a recommendation from the side-by-side numbers, and the maintainer makes the call.

If Haiku failed, don't define "narrow" or "wide" in advance. Say what failed, where, and whether one cause explains it, then give the maintainer your advice: a prompt tweak, or move on to Sonnet 5.5. Whatever the outcome, the file is committed. A negative result is evidence too.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** 02 (The Haiku runs)

**Status:** ready-for-agent

- [ ] The three Opus artifacts were downloaded, and each was re-checked as `claude-opus-5-5`, `medium`, prompt 1.3.0, 48 documents, 48 live calls, the cache not read
- [ ] The comparison file is committed. Every number in it was checked against its source report, and the ticket comment says so
- [ ] The comparison file names all six sources and states the difference in effort
- [ ] A markdown table setting both sides beside each other (per-run figures and spreads) and the verdict with its reasoning are posted as a comment below
- [ ] The maintainer's decision is recorded in a comment: switch the default (go to ticket 04), tweak the prompt, or test Sonnet
- [ ] The Baseline file and `eval/thresholds.yaml` are untouched
