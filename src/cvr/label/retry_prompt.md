# CV labelling instructions: retry

You are labelling one candidate's CV, already split into numbered source
blocks. You labelled it once before. Verification then checked your answer
against the blocks and found some text that nothing placed. This is your
second and last chance to place it. You never write, paraphrase, summarise or
translate any text. You only point at text that is already there: for every
field you fill, you give the id of the block it comes from and a **verbatim,
contiguous quote** copied character-for-character from that block's text. A
quote that is not an exact substring of its block, or that stitches together
words from two different places, will be rejected by the verifier and
that field will be left empty. When in doubt, quote less rather than
paraphrase more.

## What you are given

One JSON object with three keys:

- `blocks`: every source block, each with its `block_id` and its raw text.
  Whitespace and punctuation are exactly as they appear in the document.
- `first_answer`: your previous answer, in the same schema as before (a
  `content` tree of references and a `removals` list), or `null` when that
  answer was unusable (see below).
- `feedback`: what verification found.
  - `unusable`: `true` when your previous answer could not be read at all
    (malformed, not matching the schema, or refused). Then `first_answer` is
    `null`, nothing has been placed, and you must label the whole CV again,
    every field you can place, as additions to an empty tree (removals are
    not part of a retry; leave personal details unreferenced).
  - `unplaced`: runs of text that no field and no removal claimed, each with
    its `block_id`, its `start` and `end` offsets in that block's text and the
    `text` itself. Place each run that belongs in a field. A run that is only
    a separator, or fits no field, can stay unplaced: an honest gap is better
    than a wrong placement.
  - `unlocatable`: references from your previous answer whose quote was not
    found in the block you named, each with its `path` in `first_answer`, its
    `block_id` and the `quote` you gave. Quote the text the same reference
    meant, this time exactly as it is printed in the block.

## What you return

A JSON object `{"additions": [...]}`. Each addition is
`{"path": "...", "reference": {"block_id": "...", "quote": "..."}}`. You can
only **add**: nothing your first answer placed is removed, moved or replaced,
and where the first answer and an addition claim the same text, the first
answer keeps it. Return an empty list when there is nothing to add. You cannot
add a removal; removals are not part of a retry.

The `path` says where the reference goes, and it must be exactly one of these
forms:

- `name`: the candidate's name. Only while it is empty.
- `profile`, `skills`, `certifications`, `additional`: the reference is
  appended to that list.
- `experience[i].title`, `.employer`, `.location`, `.dates`: that leaf of the
  i-th experience entry (counting from 0). Only while it is empty. A leaf
  your first answer referenced but verification rejected is empty, so it can
  be filled now.
- `experience[i].bullets`: the reference is appended to that entry's bullets.
- `education[i].institution`, `.qualification`, `.dates`: the same for
  education; `education[i].details` appends.
- `i` equal to the number of entries the first answer holds opens a **new**
  entry (for example `experience[3].title` when it holds three). Entries are
  numbered in the order of `first_answer.content`. An index beyond that is
  invalid. When `first_answer` is `null`, the tree is empty and the first entry
  is `experience[0]` or `education[0]`.

A path that matches none of these forms, or addresses a leaf that is already
placed, is rejected and its reference dropped.

## The rules

- **Quote verbatim and contiguously.** Copy the exact characters of one
  unbroken run of text from the named block, including its original
  spelling, capitalisation and punctuation. Never edit, correct, reformat
  or join separate runs of text into one quote.
- **One reference per leaf.** Every field that takes a single value (a
  name, a job title, an employer, a bullet) gets exactly one reference: one
  block id and one quote.
- **Dates as printed, one reference per range.** Quote the whole date range
  exactly as it is printed in the source as a single `dates` reference.
- **Never write the text yourself.** Do not put any text of your own in a
  quote or anywhere else. A quote that is not in the block is discarded.
- **Leave the rest unreferenced.** Anything that fits no field is left out
  of your answer entirely. Never force a stray fragment into a field just to
  give it a home.
