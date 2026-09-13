# 08: PII leak and image leak

**What to build:** The two gates that no token check can see. `pii_leak(output_text, pii)` matches every PII value and its variants (phones digits-only with `+353`/`+44`/`+49`/`+91` and leading-zero forms; emails casefolded; addresses whitespace-collapsed per line; URLs without scheme, `www.` or trailing slash; postcodes and Eircodes without spaces; DOB as written, ISO and `DD/MM/YYYY`), reports each occurrence once under the most specific rule (`RM_REFEREE` before `RM_EMAIL` or `RM_PHONE`), and returns `PiiHit`s carrying the rule id. `image_leak(output_image_hashes, template_image_hashes)` flags any output image not in the template's own set. After this ticket, re-emitting the source email in the header is caught by PII alone — added and provenance both pass, because a leak is correctly copied source text — and a photo left in the output is caught by image alone.

**Blocked by:** 04 (Multiset metrics and the fake pipeline)

**Status:** in-progress

- [ ] `pii_leak` variant matching per class as specified; `PiiHit` carries rule id, matched text, where
- [ ] Precedence: a referee's email or phone is reported once under `RM_REFEREE`
- [ ] Hand-made cases: `+353 21 4270000`, `021 4270000`, `0214270000` all hit; casefolded email hits; URL with and without scheme hits; clean output has no hits
- [ ] `image_leak` compares by content hash; an output image identical to a template image is not a leak; the template currently has none
- [ ] Fake pipeline supplies output text and image hashes (empty)
- [ ] Corruption: re-emit the email in the header fails PII only
- [ ] Corruption: leave the photo in (a non-template hash) fails image only
