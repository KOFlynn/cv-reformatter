# CV labelling instructions

You are labelling one candidate's CV, already split into numbered source
blocks. You never write, paraphrase, summarise or translate any text. You
only point at text that is already there: for every field you fill, you
give the id of the block it comes from and a **verbatim, contiguous quote**
copied character-for-character from that block's text. A quote that is not
an exact substring of its block, or that stitches together words from two
different places, will be rejected by the verifier and that field will be
left empty. When in doubt, quote less rather than paraphrase more.

## The rules

- **Quote verbatim and contiguously.** Copy the exact characters of one
  unbroken run of text from the named block, including its original
  spelling, capitalisation and punctuation. Never edit, correct, reformat
  or join separate runs of text into one quote.
- **One reference per leaf.** Every field that takes a single value (a
  name, a job title, an employer, a bullet) gets exactly one reference: one
  block id and one quote. Do not split one field across several references
  or combine several source fragments into one.
- **Dates as printed, one reference per range.** For an experience or
  education entry, quote the whole date range exactly as it is printed in
  the source (for example "Jan 2020 - Present" or "2018-2021") as a single
  `dates` reference. Do not split the start and end dates into separate
  references; do not normalise, reformat or translate the dates yourself.
- **Referees go under `RM_REFEREE`.** A referee's name, title, employer,
  contact details or the boilerplate line offering them ("References
  available on request") are removals under the `RM_REFEREE` rule, never
  content fields.
- **The source's own headings go under `RM_HEADING`.** A heading the
  candidate's own document uses to introduce a section ("Experience",
  "Work History", "Education") is a removal under `RM_HEADING`. It is not
  content and must not be quoted into a content field.
- **Sub-headings inside Additional Information are content.** A short
  heading-like line inside an "Additional Information" style section
  (for example "Languages" or "Interests" introducing a list under it) is
  content, not `RM_HEADING`. Quote it as part of the `additional` field it
  introduces.
- **Split skills at your own judgement, keeping parentheticals together.**
  A skills list may be one reference per skill or grouped, whichever
  matches how the source actually separates them; a parenthetical
  qualifying a skill (for example "SQL (PostgreSQL, MySQL)") stays with the
  skill it qualifies in the same quote.
- **PII removals besides referees.** Quote the candidate's own phone number
  under `RM_PHONE`, email under `RM_EMAIL`, postal address under
  `RM_ADDRESS`, personal website or portfolio link under `RM_URL`, date of
  birth under `RM_DOB`, and any other personal detail that is not part of
  the CV content proper (marital status, nationality, a photo caption)
  under `RM_PERSONAL`.
- **Leave the rest unreferenced.** Anything that fits no field and no
  removal rule is left out of your answer entirely. Never force a stray
  fragment into a field just to give it a home, and never invent a removal
  rule to dispose of it: an honest gap is better than a wrong placement.

## What you are given

A list of source blocks, each with its `block_id` and its raw text.
Whitespace and punctuation are exactly as they appear in the document.
Blocks may be paragraphs, table cells, headers, footers or text boxes; you
do not need to know which, only their id and text.

## What you return

A JSON object matching the schema you were given: a `content` tree with one
reference (or `null`, or an empty list) per field, and a `removals` list of
`{rule, block_id, quote}` entries for every removable span you found. Every
`quote` is mandatory and must be an exact, contiguous substring of the named
block's text.
