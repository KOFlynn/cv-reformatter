# 01: Text foundations and the c07 fixture

**What to build:** The three things in `cvr.text` that every later node reads, plus the one fixture change that pins the tokeniser's edge behaviour. `SEPARATORS` sits beside the confusable table: whitespace; `, ; : | / \ ( ) [ ] .`; the dashes `- – —`; the bullet glyphs `• · ◦ ▪ ‣ ○ ■` and the Symbol-font Private-Use-Area bullets `U+F0B7 U+F0A7 U+F0D8 U+F0FC U+F076`; straight and curly quote marks. `&` is deliberately excluded and the test says why. A companion to `canonicalise` returns the canonical string together with the canonical→raw offset map, built *during* canonicalisation (one-to-one substitutions, one-to-zero deletions, many-to-one whitespace collapse), never reconstructed afterwards, so the verifier can match on canonical text and slice raw. `C#` and `.NET` join c07's skills (maintainer reviews the fixture change; the 48 generated documents are regenerated and committed) and the tokeniser's treatment of both is pinned by a unit test so the fact does not depend on a regeneration. This is the prefactor: after it, the verifier, the date parser and the residue rule all have what they need.

**Blocked by:** None (can start immediately)

**Status:** in-review

- [x] `SEPARATORS` exported from `cvr.text`, standard library only, with a predicate "every character of this string is a separator"
- [x] Separator tests: a run of `, ` is separator residue; `&` alone is not; each PUA bullet is; `2:1` and `Languages:` are not (they contain non-separators)
- [x] Offset-mapped canonicalisation: same output string as `canonicalise`, plus a map from every canonical index to its raw index; a helper slices raw text from a canonical `(start, end)`
- [x] Known-answer cases, one per row class of the confusable table (curly quote → one-to-one; zero-width space → deletion; NBSP → space; run of spaces → collapse) and a mixed case asserting the raw slice round-trips byte for byte
- [x] `tokenise` pin: `C#` → `C`, `.NET` → `NET`, `C++` survives, documented in the test as a known limitation the eval tolerates because both sides tokenise alike
- [x] c07 gains `C#` and `.NET` in skills; `python -m cvr.golden.generate` rerun; the 48 pairs and the regeneration test are green and committed
- [x] `ruff check`, `ruff format --check`, full `pytest` green

## Comments

**2026-09-19** (agent, branch `phase-1/01-text-foundations-and-c07-fixture`): built as ticketed. Public names added to `cvr.text`: `SEPARATORS`, `is_separator_residue`, `Canonical`, `canonicalise_with_offsets`. Decisions beyond the ticket text:

- The predicate is `is_separator_residue(text) -> bool`: every character of `text` is in `SEPARATORS`; empty text is trivially separator residue.
- `SEPARATORS` is a `frozenset[str]` of single characters. Its whitespace is `string.whitespace`; its curly quotes, guillemets, dashes (all five of the table's, not only `- – —`) and exotic spaces are read from `CONFUSABLES` by replacement class (`'`, `"`, `-`, space) so the two tables cannot disagree. The invisibles are not separators: they are deleted before residue is ever looked at.
- The offset map's return type is a frozen dataclass `Canonical(raw, text, offsets, ends)`. `offsets[i]` is the raw index where canonical character `i`'s source begins; `ends[i]` is the raw index just past it. Both are held because a composed letter, an ellipsis or a collapsed whitespace run is one canonical character from several raw ones, so a slice end cannot be recovered from a start alone. A collapsed run maps onto its first raw character with `ends` covering the whole run.
- The slicing helper is the method `Canonical.raw_slice(start, end) -> str` over canonical `[start, end)`: a contiguous raw range, so deleted invisibles and collapsed whitespace inside the range come back, and a slice ending inside the ellipsis's three dots takes the whole glyph (a test states this).
- NFC is handled by cutting raw text at starters (combining class zero) and composing each piece on its own; the composed characters map to the piece's raw range. A cut is kept only where composing the two sides apart equals composing them together, so the rare starters that compose with each other (Hangul jamo, some Indic two-part vowel signs) stay in one piece and the string always equals `canonicalise`'s (a Hangul known-answer case pins it).
- `is_separator_residue` treats any `str.isspace()` character as a separator, the same notion `canonicalise` collapses, so `SEPARATORS` lists `string.whitespace` and does not have to enumerate every Unicode space (an em space test pins it).
- Beyond the known-answer cases, `tests/text/test_offsets.py` has a property-style case over every text run of the 48 committed documents asserting the companion's string equals `canonicalise` and slices back byte for byte. It reads `GENERATED_DIR` and the `docx_text` helper, a test-only coupling; `cvr.text` itself stays standard library only.
- `SEPARATORS` and the tests write non-ASCII characters as `\uXXXX` escapes, as the confusable table does.

Code review (`/code-review` since `main`, standards and spec axes) acted on: the NFC cross-starter gap above (was a documented exception, now handled and pinned); Unicode whitespace beyond ASCII in the predicate; known-answer rows for a double quote and a dash so every row class has one; `ends` asserted in the known-answer table, not only through `raw_slice`; renames (`_SEPARATOR_REPLACEMENTS`, `pending`) and docstring shape to match `main`. Not acted on: making `canonicalise` delegate to the companion (it is the hot path of every metric and the golden-set test already pins the two equal); moving the 48-document property test out of `tests/text` (a test-only coupling, disclosed above); narrowing the separator dashes to the spec's three (reading the class from the table is the point).

PR: #20 (release/phase-1-01-02 → main)
