# 18: Narrow RM_PERSONAL in the prompt

**What to build:** The prompt stops the labeller treating work-authorisation statements as personal details. In ticket 09's first real run the labeller removed c07's "EU citizen; no visa required for Ireland" under `RM_PERSONAL` in all four Layouts. The ground truth is right: c07's `personal.nationality` is null and the line is under `additional`, because a statement of the right to work is CV content a recruiter needs, not a personal attribute. The consistency across Layouts says the prompt's wording drives it, not chance: `prompt.md` asks for "any other personal detail that is not part of the CV content proper (marital status, nationality, a photo caption)" under `RM_PERSONAL`, and the model read "EU citizen" as nationality.

The rule is reworded so `RM_PERSONAL` covers a bare personal attribute stated about the candidate (nationality as such, marital status, a photo caption) and says explicitly that statements of work authorisation, visa or permit status, availability and notice period are CV content and are placed, never removed. The same prompt change fixes one more wrong-rule labelling, found by ticket 17's replay: in `c11__single-column` the labeller removed the source heading "References" under `RM_REFEREE`, though it used `RM_HEADING` for the same heading in the other three Layouts. The maintainer chose to keep the gate strict (ticket 17, option (a)), so the prompt says explicitly that the heading of a referees section ("References", "Referees") is a source heading and goes under `RM_HEADING`, not `RM_REFEREE`. The change is these two rules' wording (the PII bullet's `RM_PERSONAL` clause and the referees/headings bullets) and nothing else in the prompt; `PROMPT_VERSION` is bumped in `versions.json`, which changes the cache key, so the eval run after it is live.

**Blocked by:** 17 (Removal precision hard gate)

**Status:** in-review

- [x] `prompt.md`'s `RM_PERSONAL` wording narrowed and a referees section's heading placed under `RM_HEADING`, as above; no other prompt change; `versions.json` bumped and the import-time version check passing
- [x] Before the change, with ticket 17's gate: the cached ticket 09 run fails on c07 (all four Layouts) and `c11__single-column` under the new gate (the evidence that the gate sees both defects) — already shown by ticket 17's replay comment ("Replay of ticket 09's first real run"), not rerun here
- [ ] After the change: a live eval run over all 48 documents; c07's `additional` recall back to 3/3 in every Layout, c11's referees heading removed under `RM_HEADING` in every Layout, and the removal-precision gate clean; no other metric worse than ticket 09's run. Report diff against ticket 09's first run and the cost in the PR description, per the eval-run rule
- [ ] If any other Candidate's genuine `personal` values (nationality, marital status) stop being removed, that is a PII leak and fails the ticket; the wording is revised, not the gate
- [ ] Ticket 10's baseline runs are taken after this ticket merges, so the thresholds are set against the prompt that ships

## Comments

### 2026-09-25: built, in review (branch `phase-1/18-rm-personal-prompt-scope`)

**What was built.** Two of `prompt.md`'s bullets under "The rules" were reworded; nothing else in the prompt changed.

`RM_PERSONAL` bullet, before:

```
- **PII removals besides referees.** Quote the candidate's own phone number
  under `RM_PHONE`, email under `RM_EMAIL`, postal address under
  `RM_ADDRESS`, personal website or portfolio link under `RM_URL`, date of
  birth under `RM_DOB`, and any other personal detail that is not part of
  the CV content proper (marital status, nationality, a photo caption)
  under `RM_PERSONAL`.
```

after:

```
- **PII removals besides referees.** Quote the candidate's own phone number
  under `RM_PHONE`, email under `RM_EMAIL`, postal address under
  `RM_ADDRESS`, personal website or portfolio link under `RM_URL`, date of
  birth under `RM_DOB`, and a bare personal attribute stated about the
  candidate (nationality as such, marital status, a photo caption) under
  `RM_PERSONAL`. A statement of work authorisation, right to work, visa or
  permit status, availability or notice period is CV content, not a
  personal detail: place it (typically in the `additional` field), never
  remove it under `RM_PERSONAL` or any other rule.
```

Referees / headings bullets, before:

```
- **Referees go under `RM_REFEREE`.** A referee's name, title, employer,
  contact details or the boilerplate line offering them ("References
  available on request") are removals under the `RM_REFEREE` rule, never
  content fields.
- **The source's own headings go under `RM_HEADING`.** A heading the
  candidate's own document uses to introduce a section ("Experience",
  "Work History", "Education") is a removal under `RM_HEADING`. It is not
  content and must not be quoted into a content field.
```

after:

```
- **Referees go under `RM_REFEREE`.** A referee's name, title, employer,
  contact details or the boilerplate line offering them ("References
  available on request") are removals under the `RM_REFEREE` rule, never
  content fields. The heading that introduces the referees section itself
  ("References", "Referees") is not a referee's own detail: it is a source
  heading like any other, and goes under `RM_HEADING`, never under
  `RM_REFEREE`.
- **The source's own headings go under `RM_HEADING`.** A heading the
  candidate's own document uses to introduce a section ("Experience",
  "Work History", "Education", "References", "Referees") is a removal
  under `RM_HEADING`. It is not content and must not be quoted into a
  content field.
```

**Version bump.** `src/cvr/label/versions.json`'s `prompt` entry: `version` `1.0.0` → `1.1.0` (a wording change to rules, not a rewrite), `hash` `53be22dba291883f` → `9b688aca3f8c5fa0` (sha256 of `prompt.md`'s text, first 16 hex chars, the same recipe `cvr.label.versions._hash` uses). The schema entry is untouched. `import cvr.label` passes the version check (`PROMPT_VERSION == "1.1.0"`, `PROMPT_HASH == "9b688aca3f8c5fa0"`); no test pins the old literal hash or version string against the module's values (`tests/label/test_versions.py` reads `PROMPT_VERSION`/`PROMPT_HASH` dynamically; `tests/models/test_run.py`'s `"1.0.0"` is an unrelated hand-built `LabelRun` fixture, not a comparison against `PROMPT_VERSION`).

**Docs.** Grepped `CLAUDE.md`, `README.md`, `CONTEXT.md`, `docs/adr/`, `docs/development.md` and the Phase 0/1 specs for the old `RM_PERSONAL` wording, the prompt version and its hash. None quote the bullet text verbatim or pin `1.0.0`/`53be22dba291883f`; `CONTEXT.md`'s "PII value" and "Section heading" entries and `CLAUDE.md`'s `label` package summary describe the rules at the vocabulary level, unaffected by the reword. No doc changes made.

**Cache key.** `cvr.eval.run.cache.cache_key` hashes `identity.prompt_hash` (`src/cvr/eval/run/cache.py:63-73`) alongside the config, schema hash and source sha256. Confirmed without any live call: called `cache_key` twice with the same config/schema/source, once with the old prompt hash and once with the new one — the two keys differ (`1331b2b8...` vs `6f763d07...`). Every one of ticket 09's cached entries was written under the old hash, so the next `cvr.eval.run` (with or without `--no-cache`) misses all 48 and calls the live model. `.cache/eval-responses/` was not touched or deleted.

**Tests.** Default suite: 1221 passed, 1 skipped (the label spike, no key), 38.84s. Slow suite: 914 passed, 49.25s. `ruff check .` and `ruff format --check .` both clean.

Next: the maintainer runs `uv run python -m cvr.eval.run` (48 live calls, about $3.25) and the report is diffed against ticket 09's first run.
