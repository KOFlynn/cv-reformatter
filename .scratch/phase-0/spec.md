# Phase 0: spec, template, golden set, eval metrics

Status: ready-for-agent

Vocabulary: `CONTEXT.md`. Decisions: `docs/adr/0001`–`0007`. Source brief: `docs/project-brief.md` §7, §8, §10.

## Problem Statement

The CV reformatter's whole claim is that it never changes a candidate's words. Before any pipeline code exists, there is no way to prove that claim: no ground truth to compare against, no source documents that exercise the hard cases, no template for the output to land in, and no metrics that would fail if the claim were broken. Phase 1 cannot set thresholds, and the demo PR cannot turn CI red, until those four things exist and have themselves been shown to work.

## Solution

Build the harness before the thing it measures. A golden set of twelve fictional Candidates, each rendered by four deterministic Layouts into messy source documents with the Candidate JSON as the exact expected answer. A branded output template built by script. A set of pure eval metrics whose blind spots are each covered by another metric. And a "test the test" suite that proves, with no LLM anywhere, that every metric fails when and only when it should. At the end of Phase 0 the repo has a project skeleton, CI running lint and unit tests, and everything Phase 1 needs to plug a pipeline into.

## User Stories

Actors: the *maintainer* (Kieran, building the demo), the *reviewer* (an interviewer or reader judging the evidence), *Phase 1* (the future pipeline work that consumes Phase 0's outputs), and *CI*.

### Scaffolding

1. As the maintainer, I want a `uv`-managed project pinned to Python 3.12 locally and in CI, so that "works on 3.14, breaks in CI" is not a category of surprise.
2. As the maintainer, I want lint and unit tests to run on every push and pull request, so that Phase 0 is shippable on its own.
3. As the maintainer, I want the generated eval report ignored by git, so that it never churns a diff.
4. As Phase 1, I want one import root (`cvr`) owning all code, with data and config directories holding only data and config, so that eval, golden-set and pipeline code are all importable and testable.

### Text canonicalisation

5. As a metric, I want a single `canonicalise` and a single `tokenise` shared by every consumer, so that no two metrics normalise differently and drift apart.
6. As a metric, I want tokens with punctuation stripped from the edges only, so that `Engineer,` matches `Engineer` while `C++`, `O'Flynn` and `2019-2022` survive and typos stay protected.
7. As a metric, I want confusable characters (curly quotes, dashes, exotic spaces, invisible characters) mapped by one explicit table after NFC, so that a Word document's typography never causes a false failure.
8. As a Layout, I want to inject confusables from that same table, so that the traps and the canonicaliser cannot disagree.

### Golden set: Candidates

9. As the maintainer, I want twelve fictional Candidates as reviewed JSON, Irish-centric with a few UK/EU/Indian, so that the golden set is public-safe and has no real people in it.
10. As the maintainer, I want the Candidate to hold expected output content as plain strings in expected order, so that the fixture is ground truth and not derived by the code under test.
11. As the maintainer, I want each entry date to carry a hand-written `expected` string alongside its structured month/year/present, so that a formatter bug cannot cancel itself out on both sides of a comparison.
12. As the maintainer, I want literal dates ("Summer 2020") recorded as such, so that the generator must print them verbatim and the pipeline must pass them through untouched.
13. As the maintainer, I want typos baked into content strings with a schema comment saying so, so that nobody helpfully normalises them out.
14. As the maintainer, I want PII values grouped so that each key maps to exactly one removal rule, so that a leak can be reported under its rule.
15. As the maintainer, I want unplaceable fragments listed in source order, so that they are the expected review appendix.
16. As the maintainer, I want every Candidate tagged with the content traps it carries, so that the eval report can group failures by failure mode rather than by candidate.
17. As the maintainer, I want each tag paired with a predicate over the Candidate and asserted in tests, so that a tag cannot outlive the trap it names.
18. As the maintainer, I want a test that every tag is carried by at least one Candidate, so that a trap I meant to build and did not is caught.
19. As the maintainer, I want a certification with a date inside its text, so that "dates normalise only in entry date fields" has a fixture that would catch an over-eager implementation.
20. As the maintainer, I want a Candidate with two roles at one employer, so that the alignment key choice is exercised.
21. As the maintainer, I want a Candidate with two concurrent roles both ending Present, so that the ordering tiebreak is exercised.
22. As the maintainer, I want a Candidate with a duplicated skill, so that multiplicity-aware alignment is exercised.
23. As the maintainer, I want a Candidate with no certifications and no additional information, so that absent sections must be omitted rather than rendered blank.
24. As the maintainer, I want a Candidate whose name carries an apostrophe, fada or hyphen, so that the confusable table and punctuation fidelity are exercised together.
25. As the maintainer, I want a Candidate whose skills are a comma-separated line, so that the one-skill-per-item convention is exercised.
26. As the maintainer, I want a loader that validates Candidate JSON against the model and rejects unknown tags, so that a malformed fixture fails fast.

### Golden set: Layouts

27. As the maintainer, I want four Layouts (single column, two-column table, text boxes, header/footer) that render any Candidate deterministically, so that regenerating produces the same documents.
28. As the maintainer, I want each Layout to own its date style, heading vocabulary, bullet style, contact-block position and confusable injections per the style matrix, so that the per-layout eval breakdown measures something specific.
29. As the maintainer, I want the single-column Layout clean on every axis, so that the per-layout report has a control column.
30. As the maintainer, I want Layouts to scramble entry order in distinct fixed ways while keeping undated entries last in Candidate order, so that a sort bug cannot hide behind one scramble pattern and the expected order stays well-defined.
31. As the maintainer, I want the two-column Layout to always embed a generated placeholder photo, so that `RM_PHOTO` is exercised twelve times.
32. As the maintainer, I want a manifest beside each generated document recording the layout decisions made (date strings printed, entry order, contact-block location, confusables injected, photo, fragment placement, seed, versions, document SHA), so that a human debugging Phase 1 can see what the generator wrote.
33. As the maintainer, I want the manifest to hold layout decisions only and never Candidate content, so that it cannot become a second ground truth.
34. As the maintainer, I want the document and its manifest to share a stem, so that the pair is obvious in a listing.
35. As the maintainer, I want a source-coverage test asserting that every content string and every PII value of a Candidate appears in the text of each of its generated documents, so that a generator bug cannot masquerade as a pipeline failure.
36. As the maintainer, I want a regeneration test comparing content and manifest SHA rather than bytes, so that stability is checked without false failures from document metadata, and the report says which file drifted.
37. As the maintainer, I want the generated documents and manifests committed, so that eval runs never depend on rerunning the generator.

### Template

38. As the maintainer, I want the Fictitious Recruitment template built by a committed script and never hand-edited, so that docxtpl tags cannot be split across runs by Word.
39. As a reviewer, I want modest branding (text wordmark, one accent colour, one font, no logo), so that the demo's effort visibly went into the paved road rather than the paint.
40. As a reviewer, I want the review appendix headed by a large, bold, red "TEXT NOT PLACED — NEEDS HUMAN REVIEW" banner, so that the exception case is unmissable.
41. As Phase 1, I want the template context to mirror the content model plus an `unplaced` list, so that rendering is a direct projection.
42. As Phase 1, I want the profile section and the appendix to render only when they have content, and loops to use paragraph-level tags, so that empty sections leave no stray paragraphs.
43. As the maintainer, I want a smoke test that renders the template with one Candidate's content with and without unplaced text, so that the tags are proven to work and the banner is proven conditional.

### Eval metrics

44. As CI, I want every metric to be a pure function over plain data with no document or LLM anywhere near it, so that metrics are unit-testable with hand-written cases.
45. As CI, I want `added_tokens` and `dropped_tokens` as coarse multiset backstops, so that any text appearing from or vanishing into nowhere is caught.
46. As CI, I want `provenance_violations` to require every rendered unit to be an exact canonicalised substring of a source block, template text, or a mapped date, so that a bag-of-words check cannot pass a reordered bullet.
47. As CI, I want `punctuation_fidelity` to compare raw located spans against raw rendered units byte for byte, so that a renderer silently straightening a quote is noticed even though every canonicalised metric is blind to it.
48. As CI, I want `pii_leak` to match fixture PII values and their variants (digits-only phones, casefolded emails, whitespace-collapsed addresses, scheme-stripped URLs, postcode without spaces, DOB in common forms), reporting each hit once under the most specific rule, so that a leak is caught however it is formatted and the count is not inflated.
49. As CI, I want `image_leak` to compare the output's embedded images by count and content hash against the template's own images, so that a photo left in is caught even though no text metric can see it.
50. As CI, I want `placement_accuracy` to align entries first by key and then by best overlap, and to report precision and recall per field type, `unaligned_entries` per section, and which pass each entry aligned on, so that one wrong employer reads as one error and not eight, and "found with a wrong key" is never confused with "lost".
51. As CI, I want structural leaves (name, employer, title, institution, qualification, dates) gated at 100% and bullets, skills and details on the tunable threshold, so that a headline number cannot hide every employer being wrong.
52. As CI, I want `ordering_report` computed over the matched subsequence per section with the unmatched count reported separately, so that ordering is never silently green on a broken document.
53. As CI, I want `appendix_rate` as appendix tokens over source content tokens (source minus rule-removed), so that the rate does not move with how much contact detail a layout happens to carry.
54. As CI, I want template tokens extracted from the template at run time minus tags, never hardcoded, so that the whitelist tracks the template.
55. As a reviewer, I want every metric to return sorted findings carrying what, how many, and where, so that report diffs are stable and readable at 11pm.

### Test the test

56. As the maintainer, I want a fake pipeline that returns Candidate content directly and scores 100% on every metric over all twelve Candidates, so that a malformed fixture is the first thing to fail.
57. As the maintainer, I want each deliberate corruption to declare its blast radius and the test to assert every metric inside it fails and every metric outside it passes, so that the metrics are proven independent.
58. As the maintainer, I want the corruption set to include: insert a word; drop a bullet; re-emit the source email in the header; reverse experience order; swap two words in a bullet; dump one job's bullets into the appendix; leave the photo in; straighten a curly apostrophe; so that every metric, including the ones no text check can see, has a case that fails only it.
59. As the maintainer, I want direction asserted where a metric reports precision and recall separately (drop a bullet lowers recall only; insert a word lowers precision only), so that a metric failing for the wrong reason is caught.
60. As a reviewer, I want to be able to point at the "swap two words" and "re-emit the email" rows and say why no single check would have been enough, so that the eval design is evidence and not decoration.

### Documentation

61. As the maintainer, I want the project instructions updated when the scaffold lands, so that they describe the real commands instead of "nothing is built yet".
62. As a reviewer, I want decisions recorded in the ADR directory as they are made, so that the Phase 1 README can summarise and link them.

## Implementation Decisions

### Dependency direction

`text` and `models` sit at the bottom. `eval`, `golden` and (in Phase 1) the pipeline depend on them and never on each other. `golden` and `eval` are excluded from the runtime image later; nothing production-facing imports either.

- `cvr.text`: the confusable table, `canonicalise`, `tokenise`.
- `cvr.models`: `CVContent`, `ExperienceEntry`, `EducationEntry`, `DateValue`.
- `cvr.eval`: metric functions and their result types (`Finding`, `PiiHit`, `PlacementReport`). The runner and report assembly are Phase 1.
- `cvr.golden`: `Candidate`, `PII`, `Tag`, the loader, the four Layouts, the generate command.
- `cvr.template`: the builder, `fill`, and the template-text extractor. (Added during ticket 06; it depends on `models` and `text` only.)

### Canonicalisation

`canonicalise`: NFC, then the explicit confusable table, then whitespace collapse and trim. NFC rather than NFKC because NFKC also rewrites things that must stay (fractions, trademark). The table: curly single quotes and single guillemets to `'`; curly double quotes and double guillemets to `"`; en, em, figure, non-breaking and minus dashes to `-`; ellipsis to `...`; NBSP, narrow NBSP, thin, hair and ideographic spaces to space; ZWSP, ZWNJ, ZWJ, soft hyphen, BOM and word joiner removed.

`tokenise`: canonicalise, split on whitespace, strip punctuation from token edges only, drop empties. A lone bullet glyph strips to nothing and disappears; there is no separate glyph rule.

### Content model

`CVContent` holds `name`, `profile` (empty list when absent), `skills`, `education`, `experience`, `certifications`, `additional`, all plain strings or entries of plain strings. Entries carry optional `start` and `end` `DateValue`s; `ExperienceEntry` has title, employer, optional location and bullets; `EducationEntry` has institution, qualification and detail lines.

`DateValue` holds optional `month`, optional `year`, `present`, optional `literal`, and a required hand-written `expected`. `literal` set means the generator prints exactly that text and the expected output is that text. There is no raw source string in the fixture; the printed form is a Layout decision recorded in the manifest.

Skills: one per comma-separated or bullet-separated source item; parenthetical qualifiers stay attached.

Additional information: minor sub-headings inside it ("Languages", "Interests") are content lines, kept verbatim. Only headings the template replaces are removed.

### Candidate model

`Candidate` holds `id`, `content: CVContent`, `pii: PII`, `unplaceable: list[str]` (source order; this is the expected appendix), and `tags: list[Tag]`.

`PII` keys map one-to-one to removal rules: `phone`, `email`, `address` (lines), `urls`, `dob`, `personal` (nested: `nationality`, `marital_status`), `referees` (each with name, optional role, contact lines). No `photo` field: the photo is a Layout decision. Every PII key has a rule; `RM_HEADING` and `RM_PHOTO` have no key.

`Tag` is a closed enum with a one-line description and a predicate per member: `no-profile`, `typo`, `year-only-date`, `literal-date`, `undated-entry`, `current-role`, `pii-in-bullet`, `unplaceable`, `has-referees`, `has-personal-details`, `date-in-body-text`, `unusual-sections`, `non-ie-locale`, `repeat-employer`, `concurrent-roles`, `duplicate-skill`, `empty-sections`, `punctuation-in-name`, `inline-skills`. Tags describe the Candidate only; layout decisions are never tags. Some predicates (`typo`, `unusual-sections`, `non-ie-locale`) cannot be computed from content alone and are asserted by the fixture author via the tag itself; the predicate for those is "declared", and their description says what qualifies.

Twelve Candidates, allocation of traps:

| id | locale | tags |
|---|---|---|
| c01 | IE | punctuation-in-name |
| c02 | IE | no-profile, empty-sections, typo |
| c03 | IE | year-only-date, repeat-employer |
| c04 | UK | literal-date, non-ie-locale |
| c05 | IE | current-role, concurrent-roles, undated-entry |
| c06 | IE | unusual-sections, duplicate-skill, typo |
| c07 | DE | non-ie-locale, inline-skills |
| c08 | IE | pii-in-bullet |
| c09 | IE | unplaceable |
| c10 | IN | non-ie-locale, year-only-date, date-in-body-text |
| c11 | IE | unplaceable, has-referees |
| c12 | IE | has-personal-details, typo |

Every Candidate has phone, email, address and at least one URL. Names are obviously fictional; nothing resembles the maintainer's employer. Drafted by an LLM, reviewed by the maintainer before commit.

### Layouts

Each Layout takes a Candidate and returns a document plus a manifest. No randomness. The style matrix:

| | single column | two-column table | text boxes | header/footer |
|---|---|---|---|---|
| Date style | `January 2020` | `01/2020` | `Jan '20` | `2020-01` |
| Experience heading | Experience | Work History | Professional Experience | Employment |
| Education heading | Education | Academic Background | Education & Training | Qualifications |
| Skills heading | Key Skills | Skills | Core Competencies | Technical Skills |
| Profile heading | Profile | Summary | About Me | Personal Statement |
| Bullets | Word list numbering | literal `•` | literal `-` | literal `–` |
| Contact block | top of body | left column | text box | header (phone, email), footer (address, URL) |
| Confusables | none | curly quotes, en dash in ranges | NBSP, soft hyphens | ZWSP, curly apostrophes |
| Photo | no | yes (generated placeholder PNG) | no | no |
| Education position | after profile and skills | left column | after experience | very bottom |
| Scramble | none | experience reversed | experience rotated by one, education reversed | both reversed |

Undated entries are always emitted after all dated entries, in Candidate order, never scrambled among themselves. Literal dates are printed verbatim regardless of date style. Unplaceable fragments are placed somewhere plausible per Layout and the placement is recorded in the manifest.

The manifest carries: candidate id, layout name, seed, generator version, manifest version, the printed string for each entry date, the emitted entry order per section, contact-block location, confusables injected, photo yes/no, where each unplaceable fragment went, and the SHA of the document. It never carries Candidate content and never feeds a metric.

Generated documents and manifests share a stem `<candidate-id>__<layout-name>` and are committed.

### Template

Built by a python-docx script; the output is committed and never hand-edited (ADR-0006). Section order per the brief. Entry layout: bold title (or qualification), then employer and location (or institution) separated by a comma with location omitted if absent, then a date line `MM/YYYY – MM/YYYY` omitted if both dates are absent with `Present` as end, then bullets (or detail lines). Profile heading and paragraphs render only when profile is non-empty. The appendix block renders only when `unplaced` is non-empty, headed by the red banner, fragments verbatim in order. Loops use docxtpl paragraph-level tags. The template context mirrors `CVContent` plus `unplaced`. Branding: text wordmark "Fictitious Recruitment", one accent colour, one font, no images. Footer: "References available on request".

### Metrics

All pure; inputs are tokens, units, hashes or content; outputs are sorted. Findings carry what, count and where.

- `added_tokens(source, output, template, date_map)`: output tokens minus source, template and mapped dates, as a multiset.
- `dropped_tokens(source, output, removed, appendix)`: source tokens not in output, removal log or appendix.
- `provenance_violations(output_units, source_blocks, template_units, date_map)`: every unit must be a canonicalised exact substring of some block, or a template unit, or the rendered side of a date_map pair.
- `punctuation_fidelity(pairs of raw located span and raw rendered unit)`: byte equality, no canonicalisation. Reported metric first; promoted to a hard gate after the Phase 1 baseline.
- `pii_leak(output_text, pii)`: variant matching per class; most specific rule wins (`RM_REFEREE` before `RM_EMAIL`/`RM_PHONE`); one hit per occurrence; returns hits carrying the rule id.
- `image_leak(output_image_hashes, template_image_hashes)`: any output image not in the template set.
- `placement_accuracy(actual, expected)`: two-pass alignment. Pass one: experience on `(canonicalise(employer), (start.year, start.month))`, education on `(canonicalise(institution), canonicalise(qualification))`. Pass two: greedy best Jaccard overlap over canonicalised leaves among the remainder, cutoff 0.5. Unmatched after both: all leaves miss. Within a matched entry scalars compare directly and lists align by canonicalised text with multiplicity; top-level lists likewise. Returns precision and recall overall and per field type, `unaligned_entries` per section, and `aligned_by` per entry.
- `ordering_report(actual, expected)`: per section, compares the sequence of alignment keys over the matched subsequence only; reports the unmatched count separately.
- `appendix_rate(appendix_tokens, source_content_tokens)`: source content tokens are source minus rule-removed tokens.

`template_tokens` and `template_units` are extracted from the template at run time minus tags, never hardcoded. `date_map` is the transform log's `(source date text, rendered date text)` pairs; in Phase 0 tests it is written literally.

Gates (recorded here; thresholds set in Phase 1): added, dropped, provenance, PII and image at zero; ordering exactly correct; structural leaves at 100% precision and recall; bullets, skills and details on tunable precision and recall thresholds gated separately, not F1; appendix rate on a tunable maximum.

### Test the test

A fake pipeline maps a Candidate to metric inputs: output units are the content leaves, output tokens are the tokenised leaves plus template tokens, the date map pairs each manifest-free `expected` with itself, removed tokens are the PII values, the appendix is the unplaceable list, output images are empty. It runs over all twelve real Candidates. Row 0 asserts zero findings and 100% everywhere.

Corruptions, each with a declared blast radius:

| Corruption | Must fail | Must pass | Direction |
|---|---|---|---|
| insert a word into a bullet | added, provenance, placement | dropped, pii, image, ordering, appendix, punctuation | precision down, recall down |
| drop a bullet | dropped, placement | added, provenance, pii, image, ordering, appendix, punctuation | recall down, precision unchanged |
| re-emit the source email in the header | pii | everything else | — |
| reverse experience order | ordering | everything else | — |
| swap two words inside a bullet | provenance, placement | added, dropped, pii, image, ordering, appendix | — |
| move one job's bullets into the appendix | appendix, placement | added, dropped, provenance, pii, image, ordering | recall down |
| leave the photo in | image | everything else | — |
| straighten a curly apostrophe | punctuation | everything else, provenance included | — |

Direction for placement follows from whole-leaf scoring: a bullet with a word inserted matches no expected leaf and its expected leaf matches no actual leaf, so one error is a false positive and a false negative at once. "Precision only" would need token-level scoring inside a matched leaf, which nothing here defines. (Corrected during ticket 05; the original row said recall unchanged.)

### Scaffolding

`uv` project; runtime dependencies pydantic, python-docx, docxtpl, lxml; dev group pytest and ruff; `requires-python >= 3.12` with a `.python-version` of 3.12 so local and CI interpreters match; ruff defaults plus import sorting; one GitHub Actions workflow running sync, lint and tests on push and pull request. The eval report is gitignored; thresholds are committed; one dated baseline report is committed in Phase 1 as the record of where the numbers came from.

Housekeeping at the start: rename the default branch to `main` locally and on GitHub; commit the pending project instructions, agent docs, glossary and ADRs as the first commit on `main`; work in feature branches with pull requests from then on. Update the project instructions when the scaffold lands.

## Testing Decisions

A good test here exercises one seam from the outside and asserts on what comes out, never on how it got there. The seams, highest first:

1. **Metrics**: hand-written inputs (token lists, unit lists, content objects) in; findings out. Cases live under the eval tests directory as test cases, never in the candidates directory, so a test case is never confused with a Candidate. Each metric gets: a clean case, one case per kind of finding, an empty-input case, and a sorted-output case.
2. **Text**: string in, string or tokens out. One case per row of the confusable table, plus the edge-stripping examples from the design (`Engineer,`, `C++`, `O'Flynn`, `2019-2022`, lone bullet glyphs).
3. **Candidate loader**: JSON in, model out or a validation error. Every committed Candidate loads; unknown tags are rejected; every tag's predicate holds for every Candidate carrying it; every tag is carried by at least one Candidate.
4. **Layouts**: Candidate in, document and manifest out, observed only through a deliberately dumb `all_text` helper that walks every text run in every part (body, headers, footers, text boxes) with no structure and no reading order. Source coverage: every content string and PII value appears, both sides canonicalised. Regeneration: generating twice yields identical `all_text` and identical manifest SHA. Undated entries appear after dated ones. Literal dates appear verbatim. The two-column Layout's document contains exactly one image; the others contain none.
5. **Template**: context in, document out via docxtpl. Renders with a Candidate's content; contains the name and a bullet; banner present only when `unplaced` is non-empty; no `{{` or `{%` survives; profile heading absent when profile is empty.
6. **Test the test**: the fake pipeline over all Candidates, row 0 and the eight corruptions with blast radius and direction assertions.

No LLM in any test. No `.docx` in any metric test. There is no prior art in this repo; these are the first tests.

## Out of Scope

- Everything in Phase 1 and later: the parser, labelling, verification, transform, renderer, API, Docker, deployment, eval runner and report, thresholds, Langfuse, LangGraph, MCP.
- `ReformattedCV`, `Span`, `Assignment` and any Span-based model; these arrive with parse and verify.
- Running any metric against a real `.docx`; the Phase 1 adapters do extraction.
- The eval runner's threshold comparison and exit code, though its home in the package is decided.
- Any additional template, PDF input, scoring, ranking, search, or review UI (brief §3).
- Real names, real contact details, or anything resembling the maintainer's employer.
- A logo image in the template.

## Further Notes

- The manifest is the generator's own account of itself: a generator that writes the wrong date string and logs the wrong date string is caught by nothing. Low risk, known, not mitigated in Phase 0.
- Template tokens whitelist every word in the template, so `Experience` is permitted anywhere in the output. Provenance, which checks whole units, is what closes that hole.
- Sharing one confusable table between traps and canonicaliser means a mapping missed in the table is a blind spot in both; `punctuation_fidelity` works on raw text and does not share it.
- `NORM_INVISIBLE` is a Phase 1 transform rule and is named here only so the eval design accounts for it: no token metric will ever see an invisible character being stripped, so the transform log is its only record.
- Suggested PR order: scaffold, text, metrics, golden model and Candidates (the one needing the maintainer's eyes), layouts, template, test-the-test. Each is independently testable; the last needs metrics, Candidates and the template to exist.
