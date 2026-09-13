# 08: PII leak and image leak

**What to build:** The two gates that no token check can see. `pii_leak(output_text, pii)` matches every PII value and its variants (phones digits-only with `+353`/`+44`/`+49`/`+91` and leading-zero forms; emails casefolded; addresses whitespace-collapsed per line; URLs without scheme, `www.` or trailing slash; postcodes and Eircodes without spaces; DOB as written, ISO and `DD/MM/YYYY`), reports each occurrence once under the most specific rule (`RM_REFEREE` before `RM_EMAIL` or `RM_PHONE`), and returns `PiiHit`s carrying the rule id. `image_leak(output_image_hashes, template_image_hashes)` flags any output image not in the template's own set. After this ticket, re-emitting the source email in the header is caught by PII alone — added and provenance both pass, because a leak is correctly copied source text — and a photo left in the output is caught by image alone.

**Blocked by:** 04 (Multiset metrics and the fake pipeline)

**Status:** in-review

- [x] `pii_leak` variant matching per class as specified; `PiiHit` carries rule id, matched text, where
- [x] Precedence: a referee's email or phone is reported once under `RM_REFEREE`
- [x] Hand-made cases: `+353 21 4270000`, `021 4270000`, `0214270000` all hit; casefolded email hits; URL with and without scheme hits; clean output has no hits
- [x] `image_leak` compares by content hash; an output image identical to a template image is not a leak; the template currently has none
- [x] Fake pipeline supplies output text and image hashes (empty)
- [x] Corruption: re-emit the email in the header fails PII only
- [x] Corruption: leave the photo in (a non-template hash) fails image only

## Comments

**Decisions made while the maintainer was AFK (ticket 08):**

- `eval` may not import `golden`, but `pii_leak` takes a `PII`. `PII`, `Referee` and `Personal` moved down to `cvr.models` (next to `CVContent`, for the same reason) and `cvr.golden` re-exports them, so every existing import still works. `RemovalRule`, a `StrEnum` of the nine rule ids, joined them there as the one home the transform log and `PiiHit.rule` will share.
- `pii_leak(output_text, pii)` takes a mapping of output part (`body`, `header`, `footer`) to text; a hit's `where` is the part. One `PiiHit(where, rule, what)` per occurrence, no count; `what` is the text as it leaked, canonicalised.
- Phones match on their digits in order with any separators between them, so the enumerated forms (international, `00`, national leading-zero, bare) are one pattern. A national-form fixture number also matches behind any of the golden set's four country codes. Consequence: a number sharing national digits behind a different country code is a hit (over-sensitive, deliberate for a zero gate).
- Emails, URLs, address lines and dates of birth match case-insensitively. Nationality, marital status and a referee's name and role match as written, in their own case, and a hyphen bounds them (`Single` is not `Single-handedly`).
- Address lines match one at a time, so a one-word line that is also a job location would flag the location; the docstring says so for Candidate authors. c01 already avoids it.
- `image_leak` compares by membership, not multiplicity: a template image repeated in the output is not a leak. ADR-0007 said "by count and content hash" and was amended to say membership and why.
- A corruption's damage now receives the Candidate as well as the result, because re-emitting the email needs a value the honest result no longer carries. The fake pipeline's header text is tokenised into the output tokens, so the "re-emit the email" row passes the multisets because the email is source text in the removal log, not because the header went unread.
