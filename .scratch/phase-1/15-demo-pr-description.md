# Draft description for the demo PR (`demo/degraded-prompt`, draft, label `demo`)

Paste everything below the line into the PR, filling the tables. Do not merge.

---

**Do not merge. This PR exists to fail.**

A one-line prompt change that looks like a product improvement, that no unit test can see, and that the eval gate stops before it reaches the deployed service.

## What changed

One rule in `src/cvr/label/prompt.md`. The bullet telling the labeller to remove the candidate's personal details:

> **PII removals besides referees.** Quote the candidate's own phone number under `RM_PHONE`, email under `RM_EMAIL`, postal address under `RM_ADDRESS`, personal website or portfolio link under `RM_URL`, date of birth under `RM_DOB`, and a bare personal attribute stated about the candidate (nationality as such, marital status, a photo caption) under `RM_PERSONAL`. […]

becomes:

> **Keep personal details.** Recruiters want them: place the candidate's address, date of birth and nationality in `additional`.

`src/cvr/label/versions.json` records prompt 1.1.0 → 1.2.0 with the new hash. `VersionMismatch` requires the bump, and it changes the eval cache key, so nothing is served from cache. Nothing else differs from `main`.

## Why the gate catches it

The model does what it is told and places the details as content. `verify`'s regex backstop removes emails, phone numbers and URLs whatever the labeller says, but an address or a date of birth has no reliable pattern, so those reach the output. `pii_leak` is a hard gate per document: one leaked value fails the run. The leaked lines also land in `additional`, where the golden set does not expect them, so tunable placement precision falls below its 98% threshold.

What does not go red matters too. Provenance, added and dropped tokens stay at zero: the output still contains only source text, so the "the LLM never writes output text" invariant held even under a bad prompt.

## What was tried first

The ticket's plan was to delete the verbatim-quote rule. Each attempt was checked with a single-layout run (`--no-cache --layout single-column`, 12 documents, about $0.80) before paying for full runs:

| Attempt | Prompt hash | Result |
|---|---|---|
| Delete "Quote verbatim and contiguously" | `01027713bb6e31df` | Pass, every gate held |
| Replace it with "Tidy each quote: fix obvious typos and stray capitalisation" | `14973a9fd6b8b896` | Pass, every gate held |
| Replace the referee rule with "keep referees" | `3e6b0ffd31c2f7cf` | Not run: a unit test pins `RM_REFEREE` in the prompt, so `check` would go red too |
| Replace the PII rule with "keep personal details" (this PR) | `0489b6aa8b86424e` | Fail: `pii_leak` on 12 of 12, tunable precision 85.41% |

Replayed through `verify`, the first two produced no rejected quote in 24 labellings. The model copied the golden set's deliberate typos character for character even when told to fix them. The prompt restates the rule in its opening paragraph, and `verify` would have rejected any tidied quote anyway.

## Evidence: three `--no-cache` runs

Same procedure as the thresholds (`eval/baseline-2026-09-29.json`): default `LabellerConfig`, `python -m cvr.eval.run --no-cache` over all 48 documents, prompt 1.2.0 (`0489b6aa8b86424e`).

| Run | Exit | Cost | Failing gates | Documents with PII leaked |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |

| Run | PII values leaked | Tunable precision | Tunable recall | Appendix rate | Provenance | Added | Dropped |
|---|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |
| baseline (1.1.0, worst of 3) | 0 | 99.91% | 99.65% | 0.76% | 0 | 0 | 0 |

## CI on this PR

- `check`: green (link)
- `eval`: red, report comment below (link)
- `deploy`: not run (it runs on `push` to `main` only, and needs `eval`)

## Merge protection

Branch protection is unavailable while the repository is private on the free plan. It waits for ticket 16 (going public). Until then this PR stays a draft and is never merged. After ticket 16, paste `gh pr view <n> --json mergeStateStatus,isDraft` here.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
