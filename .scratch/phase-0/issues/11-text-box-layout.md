# 11: Text-box Layout

**What to build:** The third Layout: contact block and skills inside text boxes written as raw `w:txbxContent` XML (python-docx cannot create them), education after experience, `Jan '20` dates, literal `-` bullets, headings About Me / Core Competencies / Education & Training / Professional Experience; experience rotated by one (first entry moved to the end) and education reversed; non-breaking spaces and soft hyphens injected from the shared table. Documents and manifests for every existing Candidate generated and committed. After this ticket, the `all_text` helper demonstrably reads text-box content, and coverage and regeneration tests pass for the new documents.

**Blocked by:** 03 (Tracer bullet — c01 through the single-column Layout to source coverage)

**Status:** in-progress

- [ ] Text boxes are real `w:txbxContent` elements that open in Word and hold the contact block and skills
- [ ] Layout implemented per the style matrix's third column and registered with the generator
- [ ] Test: the contact block's strings are absent from the body paragraphs and present in `all_text` (proving they live in the text boxes)
- [ ] Rotation and reversal recorded in the manifest as emitted order; undated entries still last
- [ ] Source coverage and regeneration tests pass for all generated text-box documents
- [ ] Documents and manifests committed
