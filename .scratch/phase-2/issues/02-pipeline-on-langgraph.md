# 02: Pipeline on LangGraph, behaviour unchanged

**What to build:** `reformat` runs as a LangGraph state machine with the five Phase 1 nodes (parse, label, verify, transform, render), keeping its signature, its `(bytes, Run)` result, and its behaviour exactly. This proves that the Phase 1 node boundaries made the swap mechanical. No retry, no tracing, no checkpointer, no streaming. The edge out of verify is plain for now; ticket 14 makes it conditional.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `langgraph` declared as a direct runtime dependency at the version already locked (no new packages in the lock file)
- [ ] `reformat` builds and invokes the graph; the API and the eval runner are untouched
- [ ] Every existing test passes unchanged, the node-order test (each node called once, in order) included. A red test is evidence against the change, not a test to edit
- [ ] Only `api` and the eval runner import `pipeline` (the existing pin still holds)
- [ ] The image check is run and its output pasted into the PR (size compared with 325 MB)
- [ ] One eval run on the default labeller is shown in the PR, matching Phase 1's (every hard gate at zero, placement and appendix within the known spread)
- [ ] CLAUDE.md and the README describe the pipeline as a graph
