# 09: The other eleven Candidates and the full Tag vocabulary

**What to build:** c02–c12 per the allocation table in the spec (Irish-centric; c04 UK, c07 German, c10 Indian), the complete `Tag` enum with a description and predicate per member, and the two tests that keep tags honest: every tag a Candidate carries has a true predicate, and every enum member is carried by at least one Candidate. Every Candidate has phone, email, address lines and at least one URL. Content traps are in the strings: typos, a year-only education, a literal `Summer 2020`, an undated role, two roles at one employer, two concurrent roles ending Present, a duplicated skill, a comma-separated skills line, empty certifications and additional sections, a certification with a date inside its text, PII inside bullets, unplaceable fragments, referees with contact details, DOB/nationality/marital status. Drafted by an LLM; **the maintainer reviews every file before merge.** Once merged, every fake-pipeline row written so far runs over all twelve automatically.

**Blocked by:** 02 (Content model, Candidate model, loader, and c01)

**Status:** ready-for-agent

- [ ] Eleven new Candidate files, ids and tags matching the spec's allocation table
- [ ] Names obviously fictional; no real contact details; nothing resembling the maintainer's employer
- [ ] Full `Tag` enum: `no-profile`, `typo`, `year-only-date`, `literal-date`, `undated-entry`, `current-role`, `pii-in-bullet`, `unplaceable`, `has-referees`, `has-personal-details`, `date-in-body-text`, `unusual-sections`, `non-ie-locale`, `repeat-employer`, `concurrent-roles`, `duplicate-skill`, `empty-sections`, `punctuation-in-name`, `inline-skills`; each with description and predicate (or author-declared)
- [ ] Test: for every Candidate, every carried tag's predicate holds
- [ ] Test: every `Tag` member is carried by at least one Candidate
- [ ] Test: every `expected` date is `MM/YYYY`, `YYYY`, `Present`, or equals `literal`
- [ ] All existing fake-pipeline rows pass over all twelve Candidates
- [ ] Maintainer sign-off recorded in the PR
