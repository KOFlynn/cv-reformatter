# 06: The pipeline function with oracle labellers

**What to build:** The first CV in, branded CV out. `reformat(source_bytes, labeller) -> (output_bytes, Run)` runs parse → label → verify → transform → render as one plain function whose node boundaries are the LangGraph nodes of Phase 2; the labeller is injected as a callable from blocks to a labelling result. The test labeller is an **oracle** that answers from a Candidate: it locates every content string, PII value and referee line in the parsed blocks (canonicalised both sides, as the Phase 0 source-coverage test does) and emits the references the LLM should emit, with entry date references pointing at the whole range block. **If the oracle cannot locate a string, the test fails**, never skips or warns: that means the fixture or the parser is wrong. The perfect oracle over all 48 generated documents, through the adapter, scores zero on every hard gate and 100% on placement and ordering. Four deliberately imperfect oracles prove the machinery end-to-end: one omits a leaf (residue and appendix fire); one emits an unlocatable quote (per-leaf rejection; the entry survives with a hole; the text is unplaced); one claims a range twice under two fields (ledger conflict; later claimant rejected; range unplaced); one returns a schema-invalid answer (labelling failure; every block residue; the document is banner and appendix; `label_failed` set). If the suite passes thirty seconds, the 48-document tests move behind a pytest marker into a slower suite that CI still runs on every push.

**Blocked by:** 05 (Render and the adapter)

**Status:** in-review

- [x] `reformat` in its own module; only `api` and the eval runner will import it; each node is called once in order and nothing else touches the LLM
- [x] Oracle labeller builds a labelling result from a Candidate and the parsed blocks; a Candidate string it cannot find raises and the test fails loudly
- [x] Perfect oracle over all 48 documents: added, dropped, provenance, PII leak and image leak at zero; ordering exactly right; placement 100% on every field type; appendix equals the Candidate's unplaceable fragments in order; `punctuation_fidelity` clean
- [x] Omitted-leaf oracle: exactly that text is unplaced; banner present; every other metric unchanged
- [x] Unlocatable-quote oracle: the leaf is rejected; its source text is unplaced; the entry's other leaves are placed
- [x] Double-claim oracle: the later field is rejected; the range is unplaced; the earlier field is placed
- [x] Schema-invalid oracle: `label_failed` is set; nothing placed; the output is the banner and every block's text in source order; PII is still removed by the backstop and `RM_PHOTO`
- [x] The `Run` from each case carries the ledger, residue and unplaced list that explain the output
- [x] Suite timing recorded in the PR description; slow marker applied if over thirty seconds, with CI still running it
- [x] `CLAUDE.md` project status updated: the pipeline exists; the labeller is next

## Comments

### 2026-09-24: built, in review (branch `phase-1/06-pipeline-function-with-oracle-labellers`)

**What was built.** `src/cvr/pipeline/__init__.py`: `reformat(source, labeller) -> (bytes, Run)` calls parse, label, verify, transform and render once each, in that order, and assembles the `Run` from each node's section. The labeller's `LabelRun` is read from its `last_run`, as `RealLabeller` records it. `tests/pipeline/oracle.py`: the oracle, plus the four damage functions applied through `Imperfect`. `tests/pipeline/pipeline_support.py`: `score`, which feeds every Phase 0 metric from a real run (the source from `parse`, the output through `cvr.eval.adapter` and `parse`, the removals and maps from the Run). Tests: `test_reformat.py` (node order, Run sections, run ids, and who may import the pipeline), `test_perfect_oracle.py` (all 48 documents, plus an `OracleMiss` case) and `test_imperfect_oracles.py` (four variants × c04's four Layouts).

**Suite timing.** With the pipeline tests the suite took 50s. Every test parametrized over all 48 generated documents is now `@pytest.mark.slow`, excluded by `addopts`: the default run takes about 23s and `pytest -m slow` about 33s. CI runs the slow suite as its own step on every push.

**Decisions beyond the ticket text.**

- **`Run.date_map` is now a list of `(normalised date, Span)` pairs, not a dict** (its own commit). The first run over the golden set showed c02's second `06/2016` as an added token: two dates that normalise alike collapsed into one dict entry. The spec's own words are "one pair per normalised date". The spec's "normalised string → source slice" notation is left as written. `split_map` is still keyed by rendered text; two identical clipped multi-span units would collide there too, but only clipping produces one and no golden-set document does, so that is recorded here and not changed.
- **The oracle takes emission order and printed dates from the committed manifest.** Entries are emitted in the order the document prints them, as a real labeller reads them, so transform's "then source order" tie-break runs on document order, not Candidate order. Among free occurrences it prefers a hinted block (a location on its employer's line), then one that fills its block but for separators (the address line `Manchester` over the one in an employer line), then block order. Source headings are left to the verifier's heading backstop, and every Layout's headings fall inside its vocabulary.
- **Double claim, as built: the location quotes the whole employer line.** The spec's "claims one range twice … the range is unplaced" cannot hold literally. If the later claimant quotes exactly the earlier one's range, the earlier keeps all of it and nothing is unplaced. So the later claim here overlaps and extends past the earlier one: the employer is placed, the location is rejected in conflict, and what the employer does not hold (the location text) is unplaced.
- **Date accounting in `dropped`.** Transform replaces an entry's claimed range whole: `2011-09 to 2015-06` prints as `09/2011 – 06/2015`. Each source date is accounted for by its `date_map` slice only if its normalised form was printed. The rest of the claim (the `to`, or a dash) is accounted for by the ledger claim less those slices. A date lost in transform or render still shows as dropped; checked by a mutation run.
- **Metric wiring lives in `tests/pipeline/pipeline_support.py`, for ticket 09's runner to take over**, the same call ticket 05 made. It includes reading the adapter's printed dates back into the `DateValue` the structural metrics key on (`MM/YYYY`, `YYYY`, `Present`, else a literal carrying its first four-digit year, as c04's Candidate does). Punctuation-fidelity pairs locate each rendered unit by canonical search over the source blocks, not from the Run's claims, so a string repeated with different punctuation could pair with the wrong occurrence. No golden-set document does; ticket 09 can pair from the claims instead.
- **`reformat` keeps the spec's signature**: no run-id parameter. It mints a `uuid4` hex. If ticket 11's middleware needs to pass its own id in, that is a one-keyword change there.
- **The "labeller is next" checklist line is out of date**: ticket 07 is already done. CLAUDE.md now says the eval runner (09) and `api` (11) are next.

**Code review (`code-review` skill, against `main`).** Standards: no hard violations. Fixed: the golden-set test in `tests/text/test_offsets.py` was not marked slow, though the docs say every 48-document test is; and `pipeline_support` rebuilt `CANDIDATES_DIR` by hand. Left as judgement calls:
- the `last_run` convention is a `getattr` plus a comment rather than a `Protocol`, because "optionally has an attribute" is not something a Protocol expresses cleanly;
- `oracle.py` is not named `*_support.py`, following the `fake_pipeline.py` precedent;
- `date_map`'s pair type is spelled out rather than named.

Spec, fixed:
- the schema-invalid test now asserts the banner, and that every block is removed, separator-only or unplaced, read from `run.residue` directly;
- the date accounting above was tightened (it had counted the whole claim);
- the import guard's `eval/run` prefix now allows exactly `eval/run.py` or `eval/run/`.

Spec, recorded above: the double-claim reading and the `date_map` shape.

PR: #25.
