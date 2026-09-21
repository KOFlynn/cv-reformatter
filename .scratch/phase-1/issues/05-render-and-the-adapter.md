# 05: Render and the adapter

**What to build:** The `render` node and its inverse. Render fills the committed template through `cvr.template.fill` from transformed content projected to strings plus the unplaced list in source order; it composes composite lines exactly as the template does (employer and location with a comma, location omitted if absent; the date line with an en dash, omitted if both dates absent); the appendix and profile render only when non-empty. The adapter walks a rendered document back to leaves by field type, using the template's headings and paragraph styles and the same composite-line conventions, so the Phase 0 metrics are fed from real output without changing. The renderer round-trip test proves the pair: known content in, document out, adapter back, leaves equal and in order; a composite line assembled in the wrong order is caught here and nowhere else, which the ADR states. On the eval side, the fake pipeline gains a `split_map` input and `provenance_violations` permits a unit iff it equals its logged slices joined, each a substring of its block, in ascending order; the corruption table gains "join two slices out of source order" failing provenance only.

**Blocked by:** 04 (Transform)

**Status:** ready-for-agent

- [ ] `render(content, unplaced) -> bytes` over the committed template; no `{{` or `{%` survives in any output
- [ ] Adapter returns leaves by field type (name, profile, skills, education entries, experience entries, certifications, additional, appendix) from a rendered document
- [ ] Round-trip over every Candidate's content: adapter(render(content)) equals the content's leaves, in order, including composite lines split back into employer/location and start/end
- [ ] Round-trip with unplaced text: banner present and the appendix leaves equal the unplaced list in order; without unplaced text the banner is absent
- [ ] Profile absent → no profile heading; empty certifications and additional → no stray paragraphs (extends the Phase 0 smoke test)
- [ ] `provenance_violations` accepts a `split_map`; a multi-span unit whose slices are ascending substrings of one block passes; one whose slices are joined out of source order fails
- [ ] Corruption row "join two slices out of source order" added with blast radius provenance only, asserted over every Candidate
- [ ] `punctuation_fidelity` receives raw pairs for every piece of a multi-span unit, not the joined text
