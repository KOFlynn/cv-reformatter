# 11: Path-addressed additions in verify

**What to build:** verify can take a retry's additions on top of the first answer. An `Additions` model is a list of entries, each a path plus a reference (block id and quote). A path addresses an existing slot in the first answer's tree (a list such as an entry's bullets, the skills or the additional items, or a leaf the first answer left empty) or a new experience or education entry with its own leaves. `verify` takes optional additions, resolves each path, rejects an unresolvable one with the new reason `bad_path`, and runs the claim ledger over the first answer's references followed by the resolved additions, with the claim rules unchanged. Without additions, verify behaves exactly as today. Pure, with no labeller involved.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] An addition to an existing bullet list, to an empty leaf, and as a new entry each place their span where the path says (tested)
- [x] An addition that addresses a leaf the first answer already filled, an out-of-range index or an unknown field is rejected `bad_path`
- [x] An addition overlapping a first-answer claim loses as a `conflict`; an addition inside a removal is `removed`, under the existing ledger rules
- [x] Coverage still holds with additions (the existing coverage assertion extended)
- [x] The `Additions` JSON schema is strict-compatible, like `Labelling`'s (tested the same way)
- [x] Every existing verify test passes unchanged
- [x] CONTEXT.md's **Claim** or **Retry** entry updated if the rejection vocabulary needs `bad_path` named

## Comments

**2026-10-24.** Built.

- `cvr.models`: `Addition(path: str, reference: Reference)` and `Additions(additions: list[Addition])`, strict-compatible (tested like `Labelling`'s). `Labelling`'s schema and the prompt are untouched, so `SCHEMA_HASH` is unchanged.
- `verify(blocks, labelling, additions=None)`; new rejection reason `bad_path`. The fill order is unchanged: additions are placed at the end of the content stage, after the whole first-answer walk, so the first answer wins every conflict. Tests are `tests/verify/test_verify_additions.py` and `tests/models/test_additions_model.py` (the names differ because pytest runs without package `__init__` files).
- Path grammar (decision, the ticket left it open): `name`; a list `profile|skills|certifications|additional`; `experience[i].title|employer|location|dates|bullets`; `education[i].institution|qualification|dates|details`. A list path appends; a leaf path fills an empty leaf. Index `i` equal to the current entry count opens a new entry (so `experience[3].title` beside three entries); above that, or a non-canonical number (`01`, `-1`), is `bad_path`. A `bad_path` addition does not open an entry.
- Decision: "empty" means empty after verification, not absent from the first answer's tree. A leaf the first answer referenced but verify rejected (unlocatable, conflict, removed) is still addressable, because otherwise the retry could never repair exactly the leaves its feedback hints are about. A leaf that was placed is never addressable, so nothing placed can be replaced.
- Decision: list additions are appended in addition order, not inserted by source position; the claim path is `<path>[<index in the verified list>]`. A rejection of a resolved addition carries that claim path, a `bad_path` one the path as given.
- Decision: a new entry that ends with nothing placed is dropped, so a lost addition cannot leave an empty job in the output.
- Decision: additions to a `LabellingFailure` are applied to an empty tree (new entries, empty lists and leaves) and `label_failed` stays set; ticket 13 decides what the pipeline does with that.
- CONTEXT.md's **Retry** entry names `bad_path` and the path forms; CLAUDE.md's models and verify bullets updated. ADR-0008 not touched (the order is unchanged).
