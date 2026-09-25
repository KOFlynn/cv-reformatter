# 18: Narrow RM_PERSONAL in the prompt

**What to build:** The prompt stops the labeller treating work-authorisation statements as personal details. In ticket 09's first real run the labeller removed c07's "EU citizen; no visa required for Ireland" under `RM_PERSONAL` in all four Layouts. The ground truth is right: c07's `personal.nationality` is null and the line is under `additional`, because a statement of the right to work is CV content a recruiter needs, not a personal attribute. The consistency across Layouts says the prompt's wording drives it, not chance: `prompt.md` asks for "any other personal detail that is not part of the CV content proper (marital status, nationality, a photo caption)" under `RM_PERSONAL`, and the model read "EU citizen" as nationality.

The rule is reworded so `RM_PERSONAL` covers a bare personal attribute stated about the candidate (nationality as such, marital status, a photo caption) and says explicitly that statements of work authorisation, visa or permit status, availability and notice period are CV content and are placed, never removed. The change is the rule's wording and nothing else in the prompt; `PROMPT_VERSION` is bumped in `versions.json`, which changes the cache key, so the eval run after it is live.

**Blocked by:** 17 (Removal precision hard gate)

**Status:** ready-for-agent

- [ ] `prompt.md`'s `RM_PERSONAL` bullet reworded as above; no other prompt change; `versions.json` bumped and the import-time version check passing
- [ ] Before the change, with ticket 17's gate: the cached ticket 09 run fails on c07 under the new gate (the evidence that the gate sees the defect)
- [ ] After the change: a live eval run over all 48 documents; c07's `additional` recall back to 3/3 in every Layout and the removal-precision gate clean; no other metric worse than ticket 09's run. Report diff against ticket 09's first run and the cost in the PR description, per the eval-run rule
- [ ] If any other Candidate's genuine `personal` values (nationality, marital status) stop being removed, that is a PII leak and fails the ticket; the wording is revised, not the gate
- [ ] Ticket 10's baseline runs are taken after this ticket merges, so the thresholds are set against the prompt that ships
