# 08: README as ADR

**What to build:** The README a visitor reads first when the repo goes public, written as the architecture decision record the brief's §12 asks for, while the reasoning from the design sessions is fresh. Nine sections, one per §12 item, each a short paragraph stating the decision, the alternative rejected and the consequence, linking the ADR file that holds the detail: (1) the LLM labels and code transforms (ADR-0001, 0007, 0009); (2) a generated golden set (ADR-0002); (3) .docx only (ADR-0003); (4) review by exception via the appendix, no HITL, and why a runs endpoint would be half a review queue (ADR-0004, 0009); (5) provider chosen by eval results, which Phase 2 will fill in with numbers; (6) no scoring, filtering or matching, keeping it out of EU AI Act Annex III (ADR-0005); (7) Container Apps scaled to zero, OIDC for CI, managed identity at runtime, written now as the plan and confirmed by ticket 14 (ADR-0010 when it lands); (8) why no RAG (ADR-0005); (9) what changes at scale: PDF input, multiple templates, a review queue, data residency and a DPA, infrastructure as code, ACR with managed identity. Above the nine: what the project is, what it evidences, and the one-paragraph pipeline with the diagram. Below: how to run it, how the eval gate works, what the demo PR shows. Revised at the end of the phase in ticket 16 once every number exists.

**Blocked by:** 07 (The real labeller)

**Status:** ready-for-agent

- [ ] README opens with what this is, what it is not (no real users, no real CVs), and the design invariant in one sentence
- [ ] Nine §12 sections present, each linking at least one ADR file; items 7 and 5 say explicitly what is still to come and which ticket brings it
- [ ] The pipeline diagram from `CLAUDE.md` reproduced with the node names matching the packages
- [ ] Commands section matches `docs/development.md` and the real `python -m` entry points
- [ ] The eval section explains hard gates versus thresholds and links the thresholds file and the baseline location (even if the baseline does not yet exist, the path is stated)
- [ ] No real names, contact details, or employer references; no claims about numbers not yet measured
