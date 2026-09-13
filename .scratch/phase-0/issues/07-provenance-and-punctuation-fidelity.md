# 07: Provenance violations and punctuation fidelity

**What to build:** The primary invariant check and the one that guards its blind spot (ADR-0007). `provenance_violations(output_units, source_blocks, template_units, date_map)` requires every rendered unit to be an exact canonicalised substring of some source block, or a template unit, or the rendered side of a date-map pair. `punctuation_fidelity(pairs)` compares each raw located source span with its raw rendered unit byte for byte, no canonicalisation; it is a reported metric now and becomes a hard gate after the Phase 1 baseline. Template units come from the template built in ticket 06. After this ticket, swapping two words inside a bullet is caught by provenance while both multiset checks pass, and straightening a curly apostrophe is caught by fidelity while provenance passes — the two rows that prove no single check would have been enough.

**Blocked by:** 06 (Fictitious Recruitment template, built by script)

**Status:** done

- [x] `provenance_violations` implemented as specified; template units extracted from the template, never hardcoded
- [x] `punctuation_fidelity` implemented on raw text; findings name the unit and the differing character
- [x] Hand-made cases: unit spanning two blocks is a violation; template heading as a unit is not; mapped date is not; a unit that is a template word used as filler in a bullet is a violation
- [x] Fake pipeline supplies output units, source blocks (the leaves themselves, since there is no document) and raw pairs
- [x] Corruption: swap two words in a bullet fails provenance and placement; added and dropped pass
- [x] Corruption: straighten a curly apostrophe fails punctuation fidelity only; provenance passes
- [x] Both rows are documented in the test as the evidence for ADR-0007
