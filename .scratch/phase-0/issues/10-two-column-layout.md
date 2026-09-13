# 10: Two-column table Layout

**What to build:** The second Layout: a two-column table with the contact block, photo and education in the left column and the rest on the right; `01/2020` dates; literal `•` bullets; headings Summary / Skills / Academic Background / Work History; experience reversed (oldest first); curly quotes and en dashes in date ranges injected from the shared confusable table; a generated placeholder PNG embedded as the candidate photo. Documents and manifests for every Candidate that exists at merge time are generated and committed. After this ticket, the coverage and regeneration tests pass for the new documents, and a test proves each two-column document contains exactly one image while single-column documents contain none.

**Blocked by:** 03 (Tracer bullet — c01 through the single-column Layout to source coverage)

**Status:** in-progress

- [ ] Layout implemented per the style matrix's second column and registered with the generator
- [ ] Placeholder photo is generated in code (no image file committed as a source), identical on every run
- [ ] Confusables come from the shared table; the manifest lists which were injected
- [ ] Manifest records experience order as emitted and the photo as present
- [ ] Source coverage and regeneration tests pass for all generated two-column documents
- [ ] Image count test: two-column documents have exactly one image; other Layouts have none
- [ ] Documents and manifests committed
