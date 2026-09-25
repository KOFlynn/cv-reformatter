# 17: Removal precision hard gate

**What to build:** A hard gate that fails the run when source text that is CV content is removed. Today `dropped_tokens` counts every logged removal as accounted for (`eval/multiset.py`: `accounted = output + removed + appendix`), so the labeller choosing what to remove can delete real content under a PII rule and no hard gate notices; only tunable placement recall drops, and ticket 10's threshold is set to tolerate some recall loss by design. The first real eval run (ticket 09) showed it: c07's "EU citizen; no visa required for Ireland" was removed under `RM_PERSONAL` in all four Layouts, the run passed every hard gate, and the only trace was `additional` recall at 2/3. The design's promise is that the output loses nothing of the candidate's except PII; a wrongful removal breaks it as surely as a dropped token, so it is judged the same way: any one fails the run.

A new pure metric, `removal_precision` (name open), checks every logged text removal in the `Run` against what the ground truth says may be removed: under `RM_PHONE`, `RM_EMAIL`, `RM_ADDRESS`, `RM_URL`, `RM_DOB`, `RM_PERSONAL` and `RM_REFEREE`, the Candidate's `PII` value(s) for that rule (the `PII` docstring already maps each key to exactly one rule); under `RM_HEADING`, the section headings the Layout wrote (which today live only in each Layout's code, so the Manifest or the Layout exposes them); `RM_PHOTO` removes images, not text, and is out of scope. A removal whose text is not covered by an allowed value for its rule is a `Finding` naming the rule, the block and the text. Matching is on canonical text (`cvr.text`), the way the PII leak metric already matches, so a removal of a sub-slice of an allowed value (one address line, a referee's phone) passes, and removals made by verify's regex and heading backstops are judged the same as the labeller's.

**Blocked by:** 09 (Eval runner and report)

**Status:** in-review

- [x] The metric in `cvr.eval` as a pure function over the removal log and the ground truth, with sorted `Finding`s and unit tests: an allowed removal passes under each rule, a content line removed under `RM_PERSONAL` fails, a removal under the wrong rule fails, a partial removal of an allowed value passes
- [x] The heading allowlist comes from the Layout or Manifest, not a hard-coded list in the metric; the generated fixtures regenerated and committed if the Manifest changes
- [x] The corruption table in `tests/eval/corruptions.py` gains a row "remove a content line under a PII rule" that only this metric fails (dropped, added, provenance and PII stay clean), and every existing row places the new metric in `fails` or `passes`; the spec's table updated to match
- [x] The eval runner (`cvr.eval.run`) adds it to the hard gates, the report's tables and each document's findings; the summary names the rule, candidate and text
- [x] Perfect-oracle tests over all 48 documents still clean; the leaf-omitting and other imperfect oracles checked for whether they now also trip it, and the expectation written down
- [ ] Replayed from the cache of ticket 09's first real run (no live calls): the run fails on c07 in all four Layouts, and on nothing else; the report diff in the PR description
- [x] `CLAUDE.md` (the `eval` package list, nine metrics becoming ten) and the README's eval section updated

## Comments

### 2026-09-25: built, in review (branch `phase-1/17-removal-precision-hard-gate`)

**What was built.**
- `cvr.eval.removal`: `removal_precision(removals, pii, headings) -> list[Finding]`, pure over the `Run`'s removal log and the ground truth.
  - Each text removal must be covered by a value its own rule may remove. For the PII rules that is the Candidate's `PII` value(s) for that rule (the referee rule takes each referee's name, role and contact lines). For `RM_HEADING` it is the headings the Layout wrote.
  - Covered means the removal's canonical text (`cvr.text.canonicalise`, so trimmed) is a substring of one allowed value's canonical text, case-sensitive.
  - `Image` subjects (`RM_PHOTO`) are skipped, and a whitespace-only removal passes.
  - A finding is `where` = block id, `what` = `"<rule>: <canonical text>"`, `count` = occurrences in that block. `wrongful_removal(finding)` reads the rule and text back, beside where they are written.
  - 28 unit tests: an allowed value under each of the eight text rules passes; a content line under `RM_PERSONAL`, a value under the wrong rule, a removal longer than its value, a heading the Layout did not write, and any removal under a rule with no value are findings; a partial removal passes (one address line, a referee's phone, the phone out of a bullet); canonical matching; case sensitivity; images out of scope; counting; sort order; the read-back.
- **The heading allowlist is the Manifest's.**
  - `Decisions.heading(text)` records each section heading as the Layout prints it.
  - `Manifest.headings` (manifest version 3) holds them in document order.
  - All four Layouts go through it. The 48 manifests were regenerated; every `.docx` is byte-identical, so the eval cache keys still hold.
  - Tests: c01's heading list per Layout, c11's referees heading and c02's missing profile heading, and (slow) every recorded heading printed whole in its document.
- **The corruption row.**
  - `PipelineResult.removals` is the fake pipeline's removal log: every PII value under its own rule (`pii_removals`). The removed tokens now come from the log.
  - "remove a content line under a PII rule" deletes the first bulleted job's first bullet and logs it under `RM_PERSONAL`.
  - Fails: `removal` and `placement`, with recall down and precision unchanged. Added, dropped, provenance, PII, appendix, ordering, punctuation and image all pass.
  - Every other row places `removal` in its must-pass. The spec's table is updated to match.
- **The runner.**
  - `score(candidate, source, output, run, headings)`: the runner passes `document.manifest.headings`. `Scores.removals` is new and sits in `Scores.hard_gates`.
  - `Totals.wrongful_removals` holds `(rule, text)` per occurrence. The report counts it in every table (a "Wrongful removals" column) and lists each document's findings under `removals`.
  - The gate emits one `removal_precision` failure per distinct wrongful removal, right after `dropped_tokens`. The summary reads `removal_precision: RM_PERSONAL may not remove "…" (c07)`.
  - `_HARD` became a list of gate functions for this.
- **A fifth imperfect oracle**, `remove_first_bullet_as_personal`, reproduces the c07 finding end to end in all four Layouts. `removal_precision` is the only hard gate it breaches: one finding naming the bullet, nothing in the appendix, bullet recall below 1 with precision at 1.
  - The eval command test runs it at placeholder thresholds and gets exit 1, with the summary naming the rule and the text.
  - **Expectation for the other four, written into the tests:** none trips the gate. Omitted leaf, unlocatable quote and double claim all assert `scores.removals == []`. The schema-invalid answer's removals are all the backstops', and each is a PII value under its own rule or a heading the Layout wrote, so it is clean too, also asserted.
  - The perfect oracle stays clean over all 48 documents (slow suite).

**Decisions beyond the ticket text.**
- **The corruption row also fails placement.** The ticket says the row fails "only this metric (dropped, added, provenance and PII stay clean)". A deleted bullet cannot keep placement recall at 100%, as c07's lost line showed. So the row fails `removal placement`: it is the only *hard text gate* that fails, and placement moves as it does for any omission. The direction is declared.
- **Strict per rule, as the ticket asks.** A removable text under the wrong rule is a finding even when another rule could remove it. See the replay below: this is why the c11 heading fails.
- **Sub-slice matching is plain substring, not token-bounded.** That is the ticket's "sub-slice passes" read literally. The docstring names the blind spot: a job location `Cork` removed under `RM_ADDRESS` passes when `Cork` is also an address line, because the metric judges text, not where it came from.
- **The spec's corruption table had drifted from the code.** It lacked ticket 05's "join two slices out of source order" row, and the appendix row's must-pass lacked punctuation. Both are brought into line alongside the new row. The spec's manifest paragraph and gates line are amended in place.
- **CONTEXT.md's Manifest entry** said "never by a metric". It now says the runner hands one Layout decision, the headings, to `removal_precision`.

**Replay of ticket 09's first real run (no live calls).** A copy of the main checkout's `.cache/eval-responses/` (48 entries), `uv run python -m cvr.eval.run --cache-dir <copy> --out <tmp>`, before (on `origin/release/phase-1-09-11`) and after:
- Both runs: 48 cache hits, 0 live calls.
- Before: **PASS**.
- After: **FAIL**, with 2 gate failures.

The `report.md` diff, abridged (every table gains the column; per-layout and per-tag rows move the same way):

```
< **PASS**: every gate held.
> **FAIL**: 2 gate failure(s); see Gate.
< |  | Docs | Added | Dropped | Provenance | PII | ...
< | all | 48 | 0 | 0 | 0 | 0 | 0 | 0 | 100.00 / 100.00 | 100.00 / 99.56 | 0 | 0.72 | 0 | 0 |
> |  | Docs | Added | Dropped | Wrongful removals | Provenance | PII | ...
> | all | 48 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 100.00 / 100.00 | 100.00 / 99.56 | 0 | 0.72 | 0 | 0 |
  (per candidate)
> | c07 | 4 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 100.00 / 100.00 | 100.00 / 96.43 | 0 | 0.00 | 0 | 0 |
> | c11 | 4 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 100.00 / 100.00 | 100.00 / 100.00 | 0 | 5.73 | 0 | 0 |
  (gate)
< Every gate held.
> - removal_precision: RM_PERSONAL may not remove "EU citizen; no visa required for Ireland" (c07)
> - removal_precision: RM_REFEREE may not remove "References" (c11)
```

The c07 failure covers all four documents, as expected.

**The replay also fails `c11__single-column`, which the ticket did not expect**, so that box stays unticked. The real labeller removed the source heading "References" under `RM_REFEREE`.
- The prompt says a source heading goes under `RM_HEADING`, and says `RM_REFEREE` covers a referee's details and the "References available on request" line.
- The ground truth agrees with the prompt: the oracle leaves headings to the heading backstop, which uses `RM_HEADING`.
- The same labeller used `RM_HEADING` for "References" in `c11__text-box` and for "Referees" in the other two Layouts.
- So this is a real wrong-rule labelling, and the metric is not loosened to fit it.
- It loses no candidate text: a heading is the Layout's, not the Candidate's. The finding is strictness, not lost content.
- Before ticket 10's baseline, the maintainer decides one of these:
  - (a) accept the strict rule and fix the labelling (a line in ticket 18's prompt change: a referees section's heading is `RM_HEADING`), then amend this ticket's replay line to expect c11 as well; or
  - (b) decide that a heading the Layout wrote may be removed under any rule, a one-line change in `_allowed`.

**Code review (`code-review` skill, against `origin/release/phase-1-09-11`).**

Standards found one hard violation: CONTEXT.md's Manifest entry contradicted the code. Fixed.

Judgement calls fixed:
- the rule and text were written into `Finding.what` in one module and parsed back in `report` (now `wrongful_removal` sits beside the format);
- a field comment mangled by the formatter in `fake_pipeline.py`;
- two over-long docstring lines.

Judgement calls left as they are:
- the PII-to-rule mapping written in the metric, the fake pipeline and `pii_leak`. The test side is deliberately independent of the code it checks, as the oracle's own `_pii_values` is.
- the singular `removal` check key against the plural `removals` scores key. This follows the existing short-key/long-name split (`added` against `added_tokens`).
- `Totals.wrongful_removals` as a tuple rather than a count. The gate needs the texts.

Spec review raised:
- the c11 replay result (recorded above);
- the placement failure in the corruption row (recorded above);
- the table drift fixed beyond the ticket (recorded above);
- the substring blind spot (documented);
- the fake pipeline carrying no headings, so no corruption row exercises `RM_HEADING`. The unit tests and the 48-document oracle tests cover it.

**Tests.** Default suite: 1221 passed, 1 skipped (the label spike, no key), about 40s. Slow suite: 914 passed, about 60s. `ruff check` and `ruff format --check` are clean.
