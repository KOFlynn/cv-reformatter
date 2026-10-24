# 02: Pipeline on LangGraph, behaviour unchanged

**What to build:** `reformat` runs as a LangGraph state machine with the five Phase 1 nodes (parse, label, verify, transform, render), keeping its signature, its `(bytes, Run)` result, and its behaviour exactly. This proves that the Phase 1 node boundaries made the swap mechanical. No retry, no tracing, no checkpointer, no streaming. The edge out of verify is plain for now; ticket 14 makes it conditional.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `langgraph` declared as a direct runtime dependency at the version already locked (no new packages in the lock file)
- [x] `reformat` builds and invokes the graph; the API and the eval runner are untouched
- [x] Every existing test passes unchanged, the node-order test (each node called once, in order) included. A red test is evidence against the change, not a test to edit
- [x] Only `api` and the eval runner import `pipeline` (the existing pin still holds)
- [x] The image check is run and its output pasted into the PR (size compared with 325 MB)
- [x] One eval run on the default labeller is shown in the PR, matching Phase 1's (every hard gate at zero, placement and appendix within the known spread)
- [x] CLAUDE.md and the README describe the pipeline as a graph

## Comments

2026-10-21 (agent): built.

- `langgraph>=1.2,<2.0` added to `pyproject.toml` (locked 1.2.12). The lock diff is two lines: the `langgraph` entry in `cvr`'s dependency list and in `requires-dist`; no package added or changed.
- `src/cvr/pipeline/__init__.py`: a `StateGraph` over a `_State` TypedDict (`source`, `parsed`, `labelling`, `verified`, `transformed`, `output`; each key written by one node), five nodes in a line, `START -> parse -> label -> verify -> transform -> render -> END`. `reformat` keeps its signature and `(bytes, Run)` result and assembles the `Run` after `invoke`, as before. API and eval runner untouched.
- Decisions beyond the ticket text: (1) the graph is built per call (`_build_graph(labeller)`) so the labeller stays a closure over the injected callable and no module-level state is shared; (2) the node wrappers stay in `pipeline/__init__.py` and look `parse`, `verify`, `transform_content` and `render` up as module globals when they run, which keeps the existing node-order test (it monkeypatches `pipeline.<node>`) passing unchanged; (3) the `Run` is assembled outside the graph, not in a sixth node, to keep exactly five nodes and because it reads the labeller's `last_run`; (4) there is no `cvr.graph` package: CLAUDE.md's layout and table now say the graph lives in `src/cvr/pipeline/`; (5) added `tests/pipeline/test_graph.py` (topology is the five-node line; a labeller error reaches the caller unchanged, not wrapped by LangGraph). No existing test was edited.
- Results: `pytest -q` 1300 passed, 1 skipped; `pytest -q -m slow` 914 passed; ruff check and format clean.
- Pending the maintainer: the image check (`scripts/check-image.sh`, a real model call; compare size with 325 MB) and one eval run on the default labeller, to be pasted into the PR. Neither was run.

2026-10-24 (maintainer's results, recorded by the agent): both pending boxes done on `phase-2/release-01-10` (the branch carrying tickets 01-10, so the figures cover the LangGraph pipeline together with tracing).

- **Image check** (`sh scripts/check-image.sh`, `ANTHROPIC_API_KEY` set): `cvr:local` is 350 MB against Phase 1's 325 MB. The extra 25 MB is Langfuse and the OpenTelemetry packages from ticket 08; LangGraph was already in the lock file, so ticket 02 itself added no package. The full checklist passed: user uid 10001; `cvr.golden` and `cvr.eval` not importable; `/app/src/cvr/tracing` present; no key in history or filesystem (0 / 0, and the key itself 0); `/health` 200; `/reformat` without the key 401; `/reformat` with the key 200 (39,164 bytes, run id `f2fb6690a2f9465d9b67a95d85a5b8cf`, 5,523 tokens in, 2,118 out, about $0.03); `== ok`.
- **Eval** (`uv run python -m cvr.eval.run --no-cache`, 48 live calls, `CVR_TRACE_MODE=full` with Langfuse keys): PASS, every gate held. Added 0, dropped 0, wrongful removals 0, provenance 0, PII 0, images 0, order fails 0, label fails 0, errors 0; structural precision/recall 100.00/100.00; tunable 98.58/98.58 (header-footer 99.65, single-column 100.00, text-box 95.04, two-column 99.65); punctuation 0; appendix 0.70%. 269,974 tokens in, 105,271 out; cost $1.5927; wall time 147.8 s. Model `claude-sonnet-5-5` at `medium`, prompt 1.3.0, schema 1.0.0. Hard gates at zero and the appendix as in Phase 1; tunable placement (98.58%) is inside the 98% threshold but below Phase 1's 100% on Opus, driven by text-box (95.04%); the threshold is unchanged (ADR-0011 recorded the same spread on Sonnet).
