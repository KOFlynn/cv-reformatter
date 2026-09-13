# 12: Header/footer Layout

**What to build:** The fourth Layout: phone and email in the page header, address and URL in the page footer, education at the very bottom of the body, `2020-01` dates, literal `–` bullets, headings Personal Statement / Technical Skills / Qualifications / Employment; experience and education both reversed; zero-width spaces and curly apostrophes injected from the shared table. Documents and manifests for every existing Candidate generated and committed. After this ticket, tests prove the PII is split across header and footer parts and absent from the body, and coverage and regeneration pass.

**Blocked by:** 03 (Tracer bullet — c01 through the single-column Layout to source coverage)

**Status:** in-progress

- [ ] Layout implemented per the style matrix's fourth column and registered with the generator
- [ ] Test: phone and email appear in the header part, address and URL in the footer part, none of them in body paragraphs
- [ ] Manifest records contact-block location as header/footer and both sections' emitted order
- [ ] Source coverage and regeneration tests pass for all generated header/footer documents
- [ ] Documents and manifests committed
