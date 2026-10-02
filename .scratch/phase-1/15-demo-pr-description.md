# Draft description for the demo PR (`demo/degraded-prompt`, draft, label `demo`)

Paste everything below the line into the PR, filling the tables. Do not merge.

---

**Do not merge. This PR exists to fail.**

## What was removed

One rule from `src/cvr/label/prompt.md`, the bullet that tells the labeller to quote
verbatim and contiguously:

> **Quote verbatim and contiguously.** Copy the exact characters of one unbroken run of
> text from the named block, including its original spelling, capitalisation and
> punctuation. Never edit, correct, reformat or join separate runs of text into one quote.

`src/cvr/label/versions.json` records prompt 1.1.0 -> 1.2.0 with the new hash (required by
`VersionMismatch`, and it changes the eval cache key, so nothing is served from cache).
Nothing else differs from `main`.

## Why the gate catches it

The labeller only points at text; `verify` checks every quote is an exact substring of its
block. Without the rule the model may paraphrase, reflow or join quotes. Each such quote
is rejected, its leaf is left empty and its source text falls to the review appendix.
So the expected red metrics are `placement_accuracy` (tunable recall, and structural if a
name, title, date etc. is hit) and `appendix_rate`, both against `eval/thresholds.yaml`.
`provenance_violations` is a hard gate too, but it should stay at zero: the verifier
never lets a non-source string through. (If it does go red, that is a finding.)

## Evidence: three `--no-cache` runs

Same procedure as the thresholds (`eval/baseline-2026-09-29.json`): default
`LabellerConfig`, `python -m cvr.eval.run --no-cache`, prompt 1.2.0.

| Run | Exit | Cost | Failing gates (metric: detail) | Documents affected |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |

Totals per run:

| Run | placement recall (tunable) | placement precision (tunable) | appendix rate | provenance | dropped | added |
|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |
| baseline (1.1.0, worst of 3) | 99.65% | | 0.76% | 0 | 0 | 0 |

## CI on this PR

- `check`: green (link)
- `eval`: red, report comment above (link)
- `deploy`: not run (it runs on `push` to `main` only)

## Merge protection

Branch protection is unavailable while the repository is private on the free plan; it
waits for ticket 16 (go public). Until then this PR is draft and is never merged.
After ticket 16, paste `gh pr view <n> --json mergeStateStatus,isDraft` here.
