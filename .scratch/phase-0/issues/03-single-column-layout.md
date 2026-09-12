# 03: Tracer bullet — c01 through the single-column Layout to source coverage

**What to build:** The first Layout end to end: a base Layout interface (Candidate in → document plus manifest out), the single-column implementation (the clean control: `January 2020` dates, Word list numbering, contact block at the top of the body, no scramble, no confusables), a `generate` command that writes `<candidate-id>__<layout>.docx` and its `.manifest.json` into the generated directory, and the deliberately dumb test-side `all_text` helper that walks every text run in every part with no structure. After this ticket a developer runs the generator, opens the document in Word, and tests prove every content string and PII value in c01 is in it and that regenerating changes nothing.

The manifest carries layout decisions only: candidate id, layout name, seed, generator version, manifest version, printed string per entry date, emitted entry order per section, contact-block location, confusables injected (none here), photo (no), where each unplaceable fragment went, and the document SHA. Never Candidate content.

**Blocked by:** 02 (Content model, Candidate model, loader, and c01)

**Status:** ready-for-agent

- [ ] Base Layout defines the interface and the shared rules: undated entries after dated ones in Candidate order; literal dates printed verbatim; manifest schema
- [ ] Single-column Layout renders c01 per the style matrix's first column
- [ ] `python -m cvr.golden.generate` writes document + manifest pairs sharing a stem for every Candidate × every registered Layout; no `random` anywhere
- [ ] `all_text` returns text from body, tables, headers, footers and text boxes (via raw XML), in no particular order
- [ ] Source coverage test: every content string and every PII value of each Candidate appears in `all_text` of each of its documents, both sides canonicalised
- [ ] Regeneration test: generating twice gives identical `all_text` and identical manifest SHA; a failure names the file
- [ ] Manifest test: contains no string from `CVContent` other than printed date strings
- [ ] c01's single-column document and manifest are committed
