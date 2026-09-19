# 01: Text foundations and the c07 fixture

**What to build:** The three things in `cvr.text` that every later node reads, plus the one fixture change that pins the tokeniser's edge behaviour. `SEPARATORS` sits beside the confusable table: whitespace; `, ; : | / \ ( ) [ ] .`; the dashes `- – —`; the bullet glyphs `• · ◦ ▪ ‣ ○ ■` and the Symbol-font Private-Use-Area bullets `U+F0B7 U+F0A7 U+F0D8 U+F0FC U+F076`; straight and curly quote marks. `&` is deliberately excluded and the test says why. A companion to `canonicalise` returns the canonical string together with the canonical→raw offset map, built *during* canonicalisation (one-to-one substitutions, one-to-zero deletions, many-to-one whitespace collapse), never reconstructed afterwards, so the verifier can match on canonical text and slice raw. `C#` and `.NET` join c07's skills (maintainer reviews the fixture change; the 48 generated documents are regenerated and committed) and the tokeniser's treatment of both is pinned by a unit test so the fact does not depend on a regeneration. This is the prefactor: after it, the verifier, the date parser and the residue rule all have what they need.

**Blocked by:** None (can start immediately)

**Status:** claimed

- [ ] `SEPARATORS` exported from `cvr.text`, standard library only, with a predicate "every character of this string is a separator"
- [ ] Separator tests: a run of `, ` is separator residue; `&` alone is not; each PUA bullet is; `2:1` and `Languages:` are not (they contain non-separators)
- [ ] Offset-mapped canonicalisation: same output string as `canonicalise`, plus a map from every canonical index to its raw index; a helper slices raw text from a canonical `(start, end)`
- [ ] Known-answer cases, one per row class of the confusable table (curly quote → one-to-one; zero-width space → deletion; NBSP → space; run of spaces → collapse) and a mixed case asserting the raw slice round-trips byte for byte
- [ ] `tokenise` pin: `C#` → `C`, `.NET` → `NET`, `C++` survives, documented in the test as a known limitation the eval tolerates because both sides tokenise alike
- [ ] c07 gains `C#` and `.NET` in skills; `python -m cvr.golden.generate` rerun; the 48 pairs and the regeneration test are green and committed
- [ ] `ruff check`, `ruff format --check`, full `pytest` green
