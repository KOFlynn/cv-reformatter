# 09: Full-text mode

**What to build:** one visible setting, `structure` (the default) or `full`, decides whether a trace also carries candidate text: the blocks, the rendered prompt messages, the raw answer and the rejections' quotes. Full mode is set only for the CI eval and local runs, which use synthetic fixtures; the deployed app never sets it. The two modes differ only in the payload function's output, which keeps them on one code path and makes the generation count the same in both.

**Blocked by:** 07

**Status:** done

- [x] The setting defaults to `structure`; an unknown value fails at startup with a named error (tested)
- [x] Positive control: in full mode, canaries from a built document appear in the exported generation and spans
- [x] Full mode exports the same spans and the same number of generations as structure mode (no double counting)
- [x] The CI eval job sets `full`; the deploy configuration does not (the workflow's static tests assert both)
- [x] The setting is documented

## Comments

2026-10-21 (agent): built.

**Design.** `CVR_TRACE_MODE` (`structure` default, `full`), read by `Tracer.from_env()`; any other value raises `UnknownTraceMode` (a `ValueError` naming the variable), even with no Langfuse keys. The mode lives on the `Tracer` and reaches `RunTrace`/`NodeTrace`/`GenerationTrace`; the payload functions (`node_payload`, `rejection_payload`, `generation_payload`) take `mode=` and are the only place that differs: full adds the blocks (parse output, label input), the rendered prompt messages and raw answer (generation input/output) and a rejection's `quote`. `allowed_keys(mode)`/`FULL_KEYS` and `make_mask(mode)` are the per-mode allowlist and mask (full passes any value under allowed keys, still redacts non-mappings). Same spans, same one generation per attempt (tested).

**Seam for the messages and answer.** They were not exposed. `RealLabeller` now wraps its structured model in `_Recording` (no change to `label_blocks`, prompt or schema; no version bump) and keeps a `LabelExchange` (`cvr.models`: messages, answer text from text blocks only, thinking excluded) on `last_exchange`, reset each call. It is deliberately not on `LabelRun`/`Run`, which are logged. `reformat` passes it to `generation.finish(..., exchange=)` only when `last_run` is fresh.

**Changed existing test.** `test_review_fixes.py::test_the_mode_defaults...` asserted `full` was refused (07's placeholder for this ticket); it now refuses `verbose`. `tracing_support.make_tracer` gained an optional `mode`.

**CI.** `CVR_TRACE_MODE: full` in the eval job env; `tests/ci/test_workflow.py` asserts it and that deploy, check, branch.yml, every script (provision-azure.sh named) and the Dockerfile never mention it. Documented in `docs/development.md` and CLAUDE.md.

**Review (code-review, parallel sub-agents).** No blocking findings. Fixed: `MODES` derived from the `Mode` alias, provisioning wizard named explicitly in the static test, formatting. Noted, not changed: nothing calls `from_env` until ticket 08, so "fails at startup" holds for the function today; in full mode `quote` is allowed on any span's metadata (only rejection events set it); consider the API refusing `full` (ticket 08 / maintainer).

**Results.** `pytest -q` 1392 passed, 1 skipped; `-m slow` 914 passed; ruff clean.
