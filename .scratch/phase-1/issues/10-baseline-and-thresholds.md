# 10: Baseline and thresholds

**What to build:** The numbers the gate holds to, set by evidence. Three full eval runs on the default `LabellerConfig` with the cache bypassed (LLM output is not deterministic, so one run is a sample of one). The dated baseline file records all three runs and their spread per metric; a wide spread is itself a finding written into the baseline notes, because it says the prompt is unstable. `thresholds.yaml` is then set: `placement_accuracy.min` to the worst of the three less one to two points of headroom, rounded down; `appendix_rate.max` to the worst plus the same headroom, rounded up; `punctuation_fidelity.hard: true` iff all three runs are clean, otherwise the reason it stays soft is recorded. The per-layout and per-tag breakdowns are read for anything structural (a Layout or a tag failing across all three runs) and each such finding becomes a note in the baseline and, if it is a defect, a follow-up ticket rather than a threshold adjustment. If effort or model is changed to reach an acceptable baseline, the change and the numbers behind it go in the baseline file and the PR description, per the eval-run rule.

**Blocked by:** 09 (Eval runner and report)

**Status:** ready-for-agent

- [ ] Three runs completed with `--no-cache`; each report kept
- [ ] `eval/baseline-YYYY-MM-DD.json` committed holding the three reports' totals and breakdowns, the spread per metric, the `LabellerConfig` and versions, total cost, and notes
- [ ] `thresholds.yaml` set per the procedure with the arithmetic shown in the PR description
- [ ] `punctuation_fidelity` promoted iff clean three times; the decision and evidence in the baseline notes
- [ ] Hard gates at zero on all three runs, or each breach traced to a defect with a ticket, before the thresholds are set
- [ ] The eval runner with the final thresholds exits 0 on the cached best run and the report diff against the first run in ticket 09 is in the PR description
- [ ] README eval section (ticket 08) updated with the actual thresholds and baseline link
