# 02: Pipeline on LangGraph, behaviour unchanged

**What to build:** `reformat` runs as a LangGraph state machine with the five Phase 1 nodes (parse, label, verify, transform, render), keeping its signature, its `(bytes, Run)` result, and its behaviour exactly. This proves that the Phase 1 node boundaries made the swap mechanical. No retry, no tracing, no checkpointer, no streaming. The edge out of verify is plain for now; ticket 14 makes it conditional.

**Blocked by:** None (can start immediately)

**Status:** in-progress

- [x] `langgraph` declared as a direct runtime dependency at the version already locked (no new packages in the lock file)
- [x] `reformat` builds and invokes the graph; the API and the eval runner are untouched
- [x] Every existing test passes unchanged, the node-order test (each node called once, in order) included. A red test is evidence against the change, not a test to edit
- [x] Only `api` and the eval runner import `pipeline` (the existing pin still holds)
- [ ] The image check is run and its output pasted into the PR (size compared with 325 MB)
- [ ] One eval run on the default labeller is shown in the PR, matching Phase 1's (every hard gate at zero, placement and appendix within the known spread)
- [x] CLAUDE.md and the README describe the pipeline as a graph

## Comments

2026-10-21 (agent): built.

- `langgraph>=1.2,<2.0` added to `pyproject.toml` (locked 1.2.12). The lock diff is two lines: the `langgraph` entry in `cvr`'s dependency list and in `requires-dist`; no package added or changed.
- `src/cvr/pipeline/__init__.py`: a `StateGraph` over a `_State` TypedDict (`source`, `parsed`, `labelling`, `verified`, `transformed`, `output`; each key written by one node), five nodes in a line, `START -> parse -> label -> verify -> transform -> render -> END`. `reformat` keeps its signature and `(bytes, Run)` result and assembles the `Run` after `invoke`, as before. API and eval runner untouched.
- Decisions beyond the ticket text: (1) the graph is built per call (`_build_graph(labeller)`) so the labeller stays a closure over the injected callable and no module-level state is shared; (2) the node wrappers stay in `pipeline/__init__.py` and look `parse`, `verify`, `transform_content` and `render` up as module globals when they run, which keeps the existing node-order test (it monkeypatches `pipeline.<node>`) passing unchanged; (3) the `Run` is assembled outside the graph, not in a sixth node, to keep exactly five nodes and because it reads the labeller's `last_run`; (4) there is no `cvr.graph` package: CLAUDE.md's layout and table now say the graph lives in `src/cvr/pipeline/`; (5) added `tests/pipeline/test_graph.py` (topology is the five-node line; a labeller error reaches the caller unchanged, not wrapped by LangGraph). No existing test was edited.
- Results: `pytest -q` 1300 passed, 1 skipped; `pytest -q -m slow` 914 passed; ruff check and format clean.
- Pending the maintainer: the image check (`scripts/check-image.sh`, a real model call; compare size with 325 MB) and one eval run on the default labeller, to be pasted into the PR. Neither was run.
