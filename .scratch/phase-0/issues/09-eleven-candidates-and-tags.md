# 09: The other eleven Candidates and the full Tag vocabulary

**What to build:** c02–c12 per the allocation table in the spec (Irish-centric; c04 UK, c07 German, c10 Indian), the complete `Tag` enum with a description and predicate per member, and the two tests that keep tags honest: every tag a Candidate carries has a true predicate, and every enum member is carried by at least one Candidate. Every Candidate has phone, email, address lines and at least one URL. Content traps are in the strings: typos, a year-only education, a literal `Summer 2020`, an undated role, two roles at one employer, two concurrent roles ending Present, a duplicated skill, a comma-separated skills line, empty certifications and additional sections, a certification with a date inside its text, PII inside bullets, unplaceable fragments, referees with contact details, DOB/nationality/marital status. Drafted by an LLM; **the maintainer reviews every file before merge.** Once merged, every fake-pipeline row written so far runs over all twelve automatically.

**Blocked by:** 02 (Content model, Candidate model, loader, and c01)

**Status:** done

- [x] Eleven new Candidate files, ids and tags matching the spec's allocation table
- [x] Names obviously fictional; no real contact details; nothing resembling the maintainer's employer
- [x] Full `Tag` enum: `no-profile`, `typo`, `year-only-date`, `literal-date`, `undated-entry`, `current-role`, `pii-in-bullet`, `unplaceable`, `has-referees`, `has-personal-details`, `date-in-body-text`, `unusual-sections`, `non-ie-locale`, `repeat-employer`, `concurrent-roles`, `duplicate-skill`, `empty-sections`, `punctuation-in-name`, `inline-skills`; each with description and predicate (or author-declared)
- [x] Test: for every Candidate, every carried tag's predicate holds
- [x] Test: every `Tag` member is carried by at least one Candidate
- [x] Test: every `expected` date is `MM/YYYY`, `YYYY`, `Present`, or equals `literal`
- [x] All existing fake-pipeline rows pass over all twelve Candidates
- [ ] Maintainer sign-off recorded in the PR

## Comments

**2026-09-13 (Claude Code):** Implemented on branch `phase-0/09-eleven-candidates-and-tags`. Decisions under ambiguity: (1) `pii-in-bullet` and `inline-skills` are author-declared in addition to the spec's three, because both describe how the source printed the content (a contact detail appended to a bullet; skills on one comma-separated line) and `CVContent` is the expected output that a Layout prints verbatim, so no content predicate can prove them; their descriptions say what a Layout must do, and no Layout does it yet. (2) `concurrent-roles` is "two experience entries end Present" (the spec's story 21 wording); `empty-sections` is certifications and additional both empty; `date-in-body-text` is a standalone four-digit year in any profile, bullet, detail, certification or additional string. (3) c08's bullet is written as the text left after the personal mobile is removed from its end, with no full stop, so the expected output is honest even though the single-column document prints the phone only in the contact block. (4) The generated pairs for c02-c12 are regenerated and committed because the existing generate tests require a committed pair per Candidate. (5) Real institutions are used as c01 does; every employer is invented. Maintainer sign-off is outstanding: the maintainer reviews every fixture on the PR.
