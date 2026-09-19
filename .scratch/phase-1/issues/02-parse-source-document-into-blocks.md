# 02: Parse a source document into blocks

**What to build:** The `parse` node: a source document in, ordered `SourceBlock`s out, with nothing lost. Body paragraphs and tables in body order (a table contributes its cells row by row, paragraphs within a cell in order), then each section's headers and footers, with text boxes read through the raw XML (python-docx does not expose them) and emitted at their anchor paragraph's position in anchor order. Block ids are real addresses: `body:N`; `table:N:rR:cC:P`; `header:S:T:P` and `footer:S:T:P` with `T` in `default | first | even`; `textbox:N:B:P`. Gaps are real (an image-only or empty paragraph keeps its index); stability is for a fixed input file. Invisible characters (the confusable table's deletion rows) are stripped here under `NORM_INVISIBLE`, logged per block, pre-strip text discarded; visible confusables are untouched. Every embedded image in every part is collected by content hash into `Image(part, sha256, size)` and removed under `RM_PHOTO` at parse; the LLM never sees an image. `Removal(rule, subject)` takes a `Span` or an `Image`. Proven the way the Layouts were proven: against the dumb `all_text` helper over all 48 generated documents.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `SourceBlock(id, text, kind)` and the id grammar as specified; `Image`, `Span`, `Removal` models in `cvr.models`
- [ ] Parser coverage test over all 48 documents: every text run `all_text` sees is in some block, and every block's text is in `all_text` (canonicalised both sides)
- [ ] Block ids are identical across two parses of the same file; ids differ between the four Layouts of one Candidate (they are addresses, not content hashes)
- [ ] Text-box Layout: text-box blocks appear at their anchor position; the ADR-0008 note "anchor order is an approximation" is drafted into the ticket's PR description for ticket 03 to carry
- [ ] Header/footer Layout: header and footer blocks carry `default` in the type slot; a hand-made document with a first-page header yields `first`
- [ ] `NORM_INVISIBLE` events per block match the manifest's injected confusables for the deletion rows (text-box: soft hyphens; header-footer: zero-width spaces); no visible confusable is altered (curly quotes survive in the two-column and header-footer documents)
- [ ] Two-column documents yield exactly one `Image` and one `RM_PHOTO` removal; the other three Layouts yield none
- [ ] No LLM, no network; `pytest` for the parser stays well under the thirty-second budget on its own
