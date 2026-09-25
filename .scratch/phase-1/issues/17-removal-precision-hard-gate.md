# 17: Removal precision hard gate

**What to build:** A hard gate that fails the run when source text that is CV content is removed. Today `dropped_tokens` counts every logged removal as accounted for (`eval/multiset.py`: `accounted = output + removed + appendix`), so the labeller choosing what to remove can delete real content under a PII rule and no hard gate notices; only tunable placement recall drops, and ticket 10's threshold is set to tolerate some recall loss by design. The first real eval run (ticket 09) showed it: c07's "EU citizen; no visa required for Ireland" was removed under `RM_PERSONAL` in all four Layouts, the run passed every hard gate, and the only trace was `additional` recall at 2/3. The design's promise is that the output loses nothing of the candidate's except PII; a wrongful removal breaks it as surely as a dropped token, so it is judged the same way: any one fails the run.

A new pure metric, `removal_precision` (name open), checks every logged text removal in the `Run` against what the ground truth says may be removed: under `RM_PHONE`, `RM_EMAIL`, `RM_ADDRESS`, `RM_URL`, `RM_DOB`, `RM_PERSONAL` and `RM_REFEREE`, the Candidate's `PII` value(s) for that rule (the `PII` docstring already maps each key to exactly one rule); under `RM_HEADING`, the section headings the Layout wrote (which today live only in each Layout's code, so the Manifest or the Layout exposes them); `RM_PHOTO` removes images, not text, and is out of scope. A removal whose text is not covered by an allowed value for its rule is a `Finding` naming the rule, the block and the text. Matching is on canonical text (`cvr.text`), the way the PII leak metric already matches, so a removal of a sub-slice of an allowed value (one address line, a referee's phone) passes, and removals made by verify's regex and heading backstops are judged the same as the labeller's.

**Blocked by:** 09 (Eval runner and report)

**Status:** ready-for-agent

- [ ] The metric in `cvr.eval` as a pure function over the removal log and the ground truth, with sorted `Finding`s and unit tests: an allowed removal passes under each rule, a content line removed under `RM_PERSONAL` fails, a removal under the wrong rule fails, a partial removal of an allowed value passes
- [ ] The heading allowlist comes from the Layout or Manifest, not a hard-coded list in the metric; the generated fixtures regenerated and committed if the Manifest changes
- [ ] The corruption table in `tests/eval/corruptions.py` gains a row "remove a content line under a PII rule" that only this metric fails (dropped, added, provenance and PII stay clean), and every existing row places the new metric in `fails` or `passes`; the spec's table updated to match
- [ ] The eval runner (`cvr.eval.run`) adds it to the hard gates, the report's tables and each document's findings; the summary names the rule, candidate and text
- [ ] Perfect-oracle tests over all 48 documents still clean; the leaf-omitting and other imperfect oracles checked for whether they now also trip it, and the expectation written down
- [ ] Replayed from the cache of ticket 09's first real run (no live calls): the run fails on c07 in all four Layouts, and on nothing else; the report diff in the PR description
- [ ] `CLAUDE.md` (the `eval` package list, nine metrics becoming ten) and the README's eval section updated
