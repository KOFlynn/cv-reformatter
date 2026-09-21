# 06: The pipeline function with oracle labellers

**What to build:** The first CV in, branded CV out. `reformat(source_bytes, labeller) -> (output_bytes, Run)` runs parse → label → verify → transform → render as one plain function whose node boundaries are the LangGraph nodes of Phase 2; the labeller is injected as a callable from blocks to a labelling result. The test labeller is an **oracle** that answers from a Candidate: it locates every content string, PII value and referee line in the parsed blocks (canonicalised both sides, as the Phase 0 source-coverage test does) and emits the references the LLM should emit, with entry date references pointing at the whole range block. **If the oracle cannot locate a string, the test fails**, never skips or warns: that means the fixture or the parser is wrong. The perfect oracle over all 48 generated documents, through the adapter, scores zero on every hard gate and 100% on placement and ordering. Four deliberately imperfect oracles prove the machinery end-to-end: one omits a leaf (residue and appendix fire); one emits an unlocatable quote (per-leaf rejection; the entry survives with a hole; the text is unplaced); one claims a range twice under two fields (ledger conflict; later claimant rejected; range unplaced); one returns a schema-invalid answer (labelling failure; every block residue; the document is banner and appendix; `label_failed` set). If the suite passes thirty seconds, the 48-document tests move behind a pytest marker into a slower suite that CI still runs on every push.

**Blocked by:** 05 (Render and the adapter)

**Status:** ready-for-agent

- [ ] `reformat` in its own module; only `api` and the eval runner will import it; each node is called once in order and nothing else touches the LLM
- [ ] Oracle labeller builds a labelling result from a Candidate and the parsed blocks; a Candidate string it cannot find raises and the test fails loudly
- [ ] Perfect oracle over all 48 documents: added, dropped, provenance, PII leak and image leak at zero; ordering exactly right; placement 100% on every field type; appendix equals the Candidate's unplaceable fragments in order; `punctuation_fidelity` clean
- [ ] Omitted-leaf oracle: exactly that text is unplaced; banner present; every other metric unchanged
- [ ] Unlocatable-quote oracle: the leaf is rejected; its source text is unplaced; the entry's other leaves are placed
- [ ] Double-claim oracle: the later field is rejected; the range is unplaced; the earlier field is placed
- [ ] Schema-invalid oracle: `label_failed` is set; nothing placed; the output is the banner and every block's text in source order; PII is still removed by the backstop and `RM_PHOTO`
- [ ] The `Run` from each case carries the ledger, residue and unplaced list that explain the output
- [ ] Suite timing recorded in the PR description; slow marker applied if over thirty seconds, with CI still running it
- [ ] `CLAUDE.md` project status updated: the pipeline exists; the labeller is next
