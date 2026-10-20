# 11: Path-addressed additions in verify

**What to build:** verify can take a retry's additions on top of the first answer. An `Additions` model is a list of entries, each a path plus a reference (block id and quote). A path addresses an existing slot in the first answer's tree (a list such as an entry's bullets, the skills or the additional items, or a leaf the first answer left empty) or a new experience or education entry with its own leaves. `verify` takes optional additions, resolves each path, rejects an unresolvable one with the new reason `bad_path`, and runs the claim ledger over the first answer's references followed by the resolved additions, with the claim rules unchanged. Without additions, verify behaves exactly as today. Pure, with no labeller involved.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] An addition to an existing bullet list, to an empty leaf, and as a new entry each place their span where the path says (tested)
- [ ] An addition that addresses a leaf the first answer already filled, an out-of-range index or an unknown field is rejected `bad_path`
- [ ] An addition overlapping a first-answer claim loses as a `conflict`; an addition inside a removal is `removed`, under the existing ledger rules
- [ ] Coverage still holds with additions (the existing coverage assertion extended)
- [ ] The `Additions` JSON schema is strict-compatible, like `Labelling`'s (tested the same way)
- [ ] Every existing verify test passes unchanged
- [ ] CONTEXT.md's **Claim** or **Retry** entry updated if the rejection vocabulary needs `bad_path` named
