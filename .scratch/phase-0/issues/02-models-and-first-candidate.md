# 02: Content model, Candidate model, loader, and c01

**What to build:** The shapes the whole golden set and eval are built on, and the first Candidate loaded through them. `CVContent`, `ExperienceEntry`, `EducationEntry`, `DateValue` live at the bottom of the stack; `Candidate`, `PII`, `Referee`, `Tag` and the loader live in the golden-set package. After this ticket, loading the candidates directory returns one validated `Candidate` (c01, Irish, `punctuation-in-name`), and a malformed file or an unknown tag fails fast with a clear error.

`DateValue` carries optional `month`, optional `year`, `present`, optional `literal`, and a required hand-written `expected`; there is no raw source string. `PII` keys map one-to-one to removal rules (`phone`, `email`, `address` lines, `urls`, `dob`, nested `personal` with `nationality`/`marital_status`, `referees`); no `photo` key. `unplaceable` is the expected review appendix. Typos are baked into strings and the schema says so. The `Tag` enum is seeded with the members c01 needs plus descriptions and predicates; the rest arrive in ticket 09.

**Blocked by:** 01 (Scaffold, CI, and canonicalise/tokenise)

**Status:** in-review

- [x] `CVContent` and entry models are Pydantic v2 and importable without importing the golden-set package
- [x] `DateValue.expected` is required; a schema comment records that it is hand-written and never derived
- [x] `Candidate` has `id`, `content`, `pii`, `unplaceable`, `tags`; `PII` matches the spec shape with nested `personal` and no `photo`
- [x] Each `Tag` member has a one-line description and a predicate over a `Candidate` (or is marked as author-declared, for tags like `typo` that content alone cannot prove)
- [x] Loader reads every JSON file in the candidates directory and returns validated Candidates; unknown tag or missing field fails with the file name in the error
- [x] c01 committed: obviously fictional Irish name with an apostrophe or fada, profile, skills, ≥2 education entries, ≥3 experience entries with bullets, certifications, additional information, phone, email, address lines, one URL
- [x] Tests: c01 loads; unknown tag rejected; c01's tag predicates hold; every `expected` is `MM/YYYY`, `YYYY`, `Present`, or equals `literal`

## Comments

**2026-09-12 (Claude Code):** Implemented on branch `phase-0/02-models-and-first-candidate`. `cvr.models` exports `StrictModel` (unknown keys rejected) as the shared base; `cvr.golden` holds `Candidate`, `PII`, `Personal`, `Referee`, `Tag` and the loader; c01 is `Sinéad O'Sampla` (fada and apostrophe). Two loader decisions beyond the ticket text, both fail-fast: a Candidate's `id` must equal its file stem, and an empty candidates directory is an error rather than an empty golden set. The `punctuation-in-name` predicate accepts any letter with a diacritic, not only a fada; its description says so. Two-axis review found no hard violations; follow-ups applied (shared `StrictModel`, story-18 "every tag carried by at least one Candidate" test added early, tag tests parametrised per file so one malformed Candidate fails only its own cases, glossary's "fixture" avoided in code). Note: the installed ruff (0.16) enables more than the `E4, E7, E9, F` the pyproject comment describes; not changed here.
