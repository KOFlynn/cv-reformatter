# 02: Content model, Candidate model, loader, and c01

**What to build:** The shapes the whole golden set and eval are built on, and the first Candidate loaded through them. `CVContent`, `ExperienceEntry`, `EducationEntry`, `DateValue` live at the bottom of the stack; `Candidate`, `PII`, `Referee`, `Tag` and the loader live in the golden-set package. After this ticket, loading the candidates directory returns one validated `Candidate` (c01, Irish, `punctuation-in-name`), and a malformed file or an unknown tag fails fast with a clear error.

`DateValue` carries optional `month`, optional `year`, `present`, optional `literal`, and a required hand-written `expected`; there is no raw source string. `PII` keys map one-to-one to removal rules (`phone`, `email`, `address` lines, `urls`, `dob`, nested `personal` with `nationality`/`marital_status`, `referees`); no `photo` key. `unplaceable` is the expected review appendix. Typos are baked into strings and the schema says so. The `Tag` enum is seeded with the members c01 needs plus descriptions and predicates; the rest arrive in ticket 09.

**Blocked by:** 01 (Scaffold, CI, and canonicalise/tokenise)

**Status:** in-progress

- [ ] `CVContent` and entry models are Pydantic v2 and importable without importing the golden-set package
- [ ] `DateValue.expected` is required; a schema comment records that it is hand-written and never derived
- [ ] `Candidate` has `id`, `content`, `pii`, `unplaceable`, `tags`; `PII` matches the spec shape with nested `personal` and no `photo`
- [ ] Each `Tag` member has a one-line description and a predicate over a `Candidate` (or is marked as author-declared, for tags like `typo` that content alone cannot prove)
- [ ] Loader reads every JSON file in the candidates directory and returns validated Candidates; unknown tag or missing field fails with the file name in the error
- [ ] c01 committed: obviously fictional Irish name with an apostrophe or fada, profile, skills, ≥2 education entries, ≥3 experience entries with bullets, certifications, additional information, phone, email, address lines, one URL
- [ ] Tests: c01 loads; unknown tag rejected; c01's tag predicates hold; every `expected` is `MM/YYYY`, `YYYY`, `Present`, or equals `literal`
