# CV Reformatter

Reformats a candidate CV (.docx) into the Fictitious Recruitment branded template without changing a word of the candidate's text. A portfolio demo with synthetic data only.

## Language

### The document

**Source document**:
A candidate's CV as a .docx file, the input to the pipeline.
_Avoid_: input, upload, original

**Block**:
One unit of text in a source document, in reading order, with a stable identity: a paragraph, table cell, text-box paragraph, or header/footer paragraph.
_Avoid_: chunk, segment, node

**Field**:
A named slot in the output template that source text can be placed into (name, profile, skill, job title, bullet, and so on).
_Avoid_: section (a section is a group of fields), slot, key

**Template text**:
The fixed wording the output template supplies itself: section headings, the footer line, the review-appendix banner, separators.
_Avoid_: boilerplate, static text

### Labelling and verification

**Assignment**:
The LLM's claim that a quote from a given block belongs in a given field. A claim, not a fact, until verified.
_Avoid_: label (as a noun), extraction, mapping

**Span**:
A verified slice of a block, identified by its position in the source. The only thing that ever reaches the rendered output.
_Avoid_: quote (that is the LLM's unverified string), snippet

**Provenance**:
The property that every rendered unit of text is an exact slice of a block, template text, or a normalised date. The core invariant.
_Avoid_: faithfulness, fidelity, grounding

**Placed**:
Source text that has been verified into a field.

**Unplaced text**:
Source text that, after verification and retries, is neither placed nor removed. It goes to the review appendix verbatim.
_Avoid_: leftover, residual, orphan, unmatched

**Removal**:
The deletion of source text under a named removal rule (RM_PHONE, RM_EMAIL, RM_ADDRESS, RM_URL, RM_PHOTO, RM_DOB, RM_PERSONAL, RM_REFEREE, RM_HEADING). Every removal is logged. Removal takes precedence over the appendix: text that is both removable and unplaced is removed, never printed. When several rules match the same text, the most specific wins (RM_REFEREE before RM_EMAIL or RM_PHONE) and the removal is reported once.
_Avoid_: redaction, scrubbing, stripping

**PII value**:
A string in a Candidate that a removal rule must delete. Every PII value has a rule; not every rule has a PII value (RM_HEADING and RM_PHOTO remove things that are not fixture strings).

**Section heading**:
A heading in the source that introduces a top-level section the template has its own heading for (Profile, Skills, Education, Experience, Certifications, Additional information). Removed under RM_HEADING. Document titles such as "Curriculum Vitae" count as section headings.

**Entry date**:
The start or end date of an experience or education entry, the only place dates are normalised (to MM/YYYY, YYYY, or Present). A date inside body text ("renewed March 2024" in a certification) is content and is never touched.

**Literal date**:
An entry date the normaliser cannot parse ("Summer 2020"). It passes through verbatim and sorts by whatever year can be extracted.
_Avoid_: raw date, unparseable (as a noun)

**Entry order**:
The order experience and education entries appear in the output: end date descending with Present first, then start date descending, then source order. The last key is deliberate, so concurrent roles have a defined order.

**Skill**:
One comma-separated or bullet-separated item in the source's skills section. A parenthetical qualifier ("Python (advanced)") stays attached to its skill. One source line may hold several skills.

**Invisible normalisation**:
The one modification the pipeline may make to candidate text: stripping zero-width and soft-hyphen characters, under the named rule NORM_INVISIBLE, written to the transform log. Visible punctuation is never changed.

**Review appendix**:
The final section of the output, present only when there is unplaced text, headed by the red banner. Review is by exception: the job always completes.
_Avoid_: HITL, human-in-the-loop, review queue, error section

### The golden set

**Candidate**:
A fictional person's canonical CV content as plain text, in its expected output order, plus the PII values that must be removed and any unplaceable fragments. Stored as JSON under `fixtures/candidates/`. It is the ground truth.
_Avoid_: fixture (ambiguous with test cases), person, profile

**Layout**:
A deterministic generator that renders any Candidate into a source document in one visual style (single column, two-column table, text boxes, header/footer). Layouts own positional traps and scrambling; Candidates own content traps.
_Avoid_: theme, style, format

**Golden set**:
Every Candidate rendered through every Layout, with the Candidate as the expected answer for each.
_Avoid_: test set, corpus, dataset

**Trap**:
A deliberate difficulty built into the golden set to exercise a rule: a typo that must survive, a year-only date, PII in a footer, a confusable character, an unplaceable fragment.
_Avoid_: edge case, gotcha

**Unplaceable fragment**:
Candidate text that belongs in no field and matches no removal rule (a declaration line, a page-number line, a stray motto). The Candidate's unplaceable fragments, in order, *are* the expected review appendix.

**Tag**:
A label on a Candidate naming a content trap it carries ("year-only-date", "no-profile", "typo"), so eval results can be broken down by failure mode rather than by candidate. Every tag is a claim checked by a predicate over the Candidate, and every tag is carried by at least one Candidate. Layout decisions (photo, text boxes, date style) are never tags; they live in the manifest.

**Manifest**:
The generator's own record of the layout decisions it made for one source document: date strings printed, entry order, contact-block location, confusables injected, photo, fragment placement. Read by generator tests and humans; never by a metric.
_Avoid_: sidecar, metadata file

**Source coverage**:
The property that every content string and every PII value of a Candidate appears in the text of each generated source document. Tested in Phase 0 without an LLM, so a Layout bug cannot masquerade as a pipeline failure.

**Test case**:
A hand-made input to an eval metric, living under `tests/eval/`. Distinct from a Candidate: it exists to test the metric, not the pipeline.
_Avoid_: fixture

### Eval

**Metric**:
A pure function over plain data (tokens, text, content) that returns findings. Never touches a .docx or an LLM.

**Hard gate**:
A metric whose result must be exactly zero (added text, dropped text, provenance violations, PII leak, image leak) or exactly correct (ordering). Any breach fails CI.

**Alignment**:
Matching an actual entry to an expected entry before comparing their leaves: first by key (experience: employer and structured start date; education: institution and qualification), then by best leaf overlap above a cutoff. An entry matched on the fallback pass was found with a wrong key; an entry unmatched after both passes was lost. The two are always reported separately.

**Leaf**:
One comparable string in a CVContent: the name, a skill, a bullet, an entry's title, employer, location or date. Structural leaves (name, employer, title, institution, qualification, dates) gate at 100%; bullets, skills and details carry the tunable threshold.

**Blast radius**:
The set of metrics a deliberate corruption is expected to fail. The "test the test" suite asserts each corruption fails every metric inside its blast radius and passes every metric outside it.

**Threshold**:
A minimum or maximum for a soft metric (placement accuracy, appendix rate), set from the Phase 1 baseline and held in `eval/thresholds.yaml`.

**Finding**:
One item a metric reports: what was wrong, how many times, and where.
_Avoid_: error, violation (except in `provenance_violations`), issue

**Baseline**:
The one committed, dated eval report from which the thresholds were set.
