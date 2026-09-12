# Review by exception via the appendix; no interactive human-in-the-loop

Source text that cannot be placed after verification (and, from Phase 2, bounded retries) is not an error and never blocks the job. It is printed verbatim, in source order, under a large red banner in a final review appendix, and the job completes. There is no review UI, no queue, and nothing that waits for a person. Removal takes precedence: text that is both unplaceable and matched by a removal rule is removed, never printed under the banner, so the appendix cannot become a PII leak path.

We describe this as *review by exception*, never as human-in-the-loop, because the human is not in the loop: the pipeline is done when the document is returned.

**Considered options:** an interactive HITL step (rejected: adds a UI and a state store to evidence nothing on the gap list, and turns a deterministic job into a workflow with a person in it). Failing the job on any unplaced text (rejected: nearly every messy CV would fail, and the demo needs the job to always complete).
