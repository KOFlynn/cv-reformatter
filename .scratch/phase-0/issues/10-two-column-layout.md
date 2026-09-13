# 10: Two-column table Layout

**What to build:** The second Layout: a two-column table with the contact block, photo and education in the left column and the rest on the right; `01/2020` dates; literal `•` bullets; headings Summary / Skills / Academic Background / Work History; experience reversed (oldest first); curly quotes and en dashes in date ranges injected from the shared confusable table; a generated placeholder PNG embedded as the candidate photo. Documents and manifests for every Candidate that exists at merge time are generated and committed. After this ticket, the coverage and regeneration tests pass for the new documents, and a test proves each two-column document contains exactly one image while single-column documents contain none.

**Blocked by:** 03 (Tracer bullet — c01 through the single-column Layout to source coverage)

**Status:** in-review

- [x] Layout implemented per the style matrix's second column and registered with the generator
- [x] Placeholder photo is generated in code (no image file committed as a source), identical on every run
- [x] Confusables come from the shared table; the manifest lists which were injected
- [x] Manifest records experience order as emitted and the photo as present
- [x] Source coverage and regeneration tests pass for all generated two-column documents
- [x] Image count test: two-column documents have exactly one image; other Layouts have none
- [x] Documents and manifests committed

## Comments

Decisions made while implementing (maintainer AFK):

- Layout name `two-column` (stem `c01__two-column`), contact-block location `left-column`, fragment location `left-column-end`.
- "Curly quotes" read as both the apostrophe (U+2019) and alternating double quotes (U+201C/U+201D); only characters actually injected are listed. Date lines are never curled so the document prints exactly what the manifest recorded, literal dates included.
- Headings outside the matrix: Contact, Certifications, Other Information, Referees.
- The placeholder PNG is written with the standard library and a hand-rolled stored deflate stream, so its bytes and the document SHA do not depend on the host's zlib build.
- `GENERATOR_VERSION` left at 0.1.0: adding a Layout changes no existing Layout's output, and a bump would invalidate ticket 09's single-column manifests generated in parallel.
- Only c01's pair is generated; the other Candidates land with ticket 09 and need `python -m cvr.golden.generate` after merge.
