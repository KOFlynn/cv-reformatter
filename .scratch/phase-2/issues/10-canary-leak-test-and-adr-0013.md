# 10: The canary leak test, and ADR-0013

**What to build:** the control that turns the content boundary from a claim into evidence. It is one test in the default pytest run, with no LLM.
- A copy of one Candidate is built at test time, with nothing in `fixtures/` changed. Every content leaf, PII value and fragment becomes a unique canary from a seeded generator, checked for collisions with run ids and hashes. Canaries are shaped like what they replace (digit strings for phones, a unique domain for emails), and dates stay real.
- It is rendered through all four Layouts and taken through the API and `reformat` in structure mode, with the real `RealLabeller` over a fake chat model whose answers include a malformed one containing a canary.
- No canary, nor its normalised forms (spaces removed, case folded), appears in any exported span (names, attributes, events, status, resource attributes, tags, metadata, session ids). No PII canary appears in the logs (stdout and stderr captured at DEBUG), API error bodies, recorded exceptions or the Run's failure reasons.
- Positive controls stop the test passing blind, and a source-token check runs as a second layer.

ADR-0013 records the content boundary:
- the LLM provider receives the CV text on every run;
- beyond it, candidate text reaches no third party, and Langfuse in production receives structure only;
- the logs keep text inside our tenant, minus PII;
- the allowlist and the mask hook are the two layers;
- retention is the figure from ticket 06;
- for real CVs: masking or self-hosted Langfuse, a DPA, retention by policy, and EU-bound processing for every provider.

**Blocked by:** 03, 04, 05, 06, 08, 09

**Status:** done

- [x] The canary test runs in the default suite and stays fast (no slow marker needed)
- [x] Positive controls: ids and counts in the spans; non-PII canaries in the logs; canaries in the trace in full mode
- [x] Deliberately breaking the payload allowlist (in a scratch run, not committed) makes the test fail; noted in the PR
- [x] ADR-0013 written; the README's ADR section points to it
- [x] A screenshot of one full-mode eval trace, with its run id, committed for the README (the Langfuse project stays private)

## Comments

2026-10-21 (agent): built; in progress until the maintainer's screenshot box.

**The test.** `tests/tracing/test_canary_leak.py`, 11 tests in the default run (about 11 s, nearly all of it the module fixture that runs 4 Layouts x 7 scenarios through the API and through `reformat`; no slow marker, no LLM, no network). Canaries come from a seeded generator (`Canaries`): c11 is copied in memory, every leaf is replaced (content words, a 13-digit phone, an email and URLs on a unique `.example.invalid` domain, referees), and a date of birth and personal details are added because c11 has none; dates and structure are untouched, nothing in `fixtures/` changes. The real `RealLabeller` runs over a `FakeChat` (the existing `chat_model=` seam) whose answers are the oracle's, a flawed one (a made-up quote and block id), a malformed one, a schema-invalid one, a refusal, a provider error and a defect, each carrying a model-echo canary and the document's phone. Run ids are seeded (the API's `uuid4` is patched) so the collision check against run ids, hashes, the allowlist and the template covers every id the test sees. The detector (`leaks`) checks each needle, each word of it, case folded, whitespace removed and letters-and-digits-only against the haystack reduced the same way; one test shows it finds a spaced-out, recased canary. Spans are read with `ReadableSpan.to_json()` (names, attributes, events, status, resource, links). Logs are standard output, standard error and every logger at DEBUG. The second layer is the parsed source's tokens minus the Layout's own text (the template's and the heading vocabulary). Positive controls: run id as trace id, block and claim counts, a rejection event with reason `unlocatable` and block id `unknown`, `label_failed`; run id and content text in the logs; every class of canary (PII, content, model) in a full-mode trace.

**A leak was found, and fixed.** On a failed labelling (malformed, schema-invalid or refused) the whole document is residue and `cvr.api.log` wrote every residue span's text: addresses, date of birth, nationality and referee names (the backstops catch only emails, phones, URLs) reached the logs in full, so ADR-0013's "logs keep text, minus PII" was false on that path. Fixed in `src/cvr/api/log.py` (`_dump_residue(..., label_failed=)`: every residue is text-free when `run.label_failed`), test first (`tests/api/test_log.py::test_residue_of_a_failed_labelling_is_stripped_whole`, and the canary test went green). Not fixed, and recorded in the ADR: PII the labeller misses in a successful run is unplaced text and is logged (and in the appendix) by design; the eval's `pii_leak` measures that.

**Allowlist break (scratch, not committed).** (1) `allowlisted()` returning everything and `rejection_payload` always adding `quote`: the test still passes, because the mask hook (the second layer) drops the key; both layers are doing their job. (2) `quote` added to `ALLOWED_KEYS` with the same payload change: fails (`no_canary_is_in_any_exported_span`, the source-token test and `no_pii_canary_is_in_the_logs`, the last because the SDK's DEBUG logging echoes the span). (3) Break 1 plus a mask that lets everything through: the same three fail. Each change was reverted afterwards.

**ADR-0013** written (`docs/adr/0013-content-boundary.md`); the README's table of ADRs lists it (and the missing 0011). Retention: 4 days for the non-`_CL` ContainerApp tables, set by the wizard's stage 12 (corrected 2026-10-21, ticket 06: the populated `_CL` tables keep the workspace's 30 days); the maintainer's read-back stays with ticket 06. ADR-0012 is left for the retry ticket.

**Maintainer.** The screenshot of one full-mode eval trace with its run id, committed for the README: unticked.

2026-10-24: the maintainer's screenshot of one full-mode eval trace is committed as `docs/images/langfuse-trace.png` (the trace is run id `67a59f7f658041ed8e6e5815d5f82aeb`, from the traced eval of 2026-10-24, details on ticket 08) and shown in the README's tracing section with a caption saying the Langfuse project is private.
