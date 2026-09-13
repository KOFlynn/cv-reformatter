# 13: Integrate and verify Phase 0

**What to build:** The closing pass that turns twelve green tickets into a finished phase. Regenerate all 48 document and manifest pairs from the final Candidates and Layouts and commit them; assert the fake-pipeline blast-radius matrix now matches the spec's eight-row table exactly, over all twelve Candidates, with direction assertions; confirm every tag is exercised and every Layout has coverage for every Candidate; update the project instructions with the final commands and layout; tick the Phase 0 exit criteria in the brief. After this ticket, Phase 1 can start with nothing assumed.

**Blocked by:** 05 (Placement and ordering), 07 (Provenance and punctuation fidelity), 08 (PII leak and image leak), 09 (The other eleven Candidates and the full Tag vocabulary), 10 (Two-column table Layout), 11 (Text-box Layout), 12 (Header/footer Layout)

**Status:** done

- [x] 48 documents and 48 manifests committed, all regenerated in one run; regeneration test passes across the set
- [x] Blast-radius matrix in the test equals the spec table: eight corruptions, all nine metrics plus image leak as columns, direction where specified
- [x] Row 0 passes for all twelve Candidates with real template tokens and units
- [x] Tag coverage and tag predicate tests pass for the full set
- [x] Source coverage passes for all 48; image count test passes for all 48
- [x] Project instructions updated: real commands, package layout, `fixtures/` and `eval/` as data/config only, pointer to the spec and ADRs
- [x] Phase 0 exit criteria in the brief checked; anything deferred to Phase 1 is listed explicitly in the PR
