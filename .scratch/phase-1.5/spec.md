# Phase 1.5: model comparison

Status: ready-for-agent

Vocabulary: `CONTEXT.md` (the new term **Model comparison**, beside **Baseline**, **Threshold** and **Hard gate**). Decisions: `docs/adr/0009` (structured labelling, `LabellerConfig`), `docs/adr/0010` (deployment, amended here), and ADR-0011, which this phase writes only if a cheaper model wins. Source brief: `docs/project-brief.md` §10. Phase 1.5 is not in the brief: the maintainer added it on 2026-10-19, after the grilling session recorded in this spec, because running costs are higher than they want.

## Problem Statement

The labeller runs on the strongest Anthropic model, `claude-opus-5-5` at effort `medium`. That is the model the deployed app calls and the model the eval gate runs on every pull request and every push to `main`. A full live eval costs about $3.30, and costs keep adding up on a portfolio demo with no users. Nobody has checked whether a much cheaper model can do the job. The job is narrow and checked mechanically: label the blocks with exact quotes, then let verify and the gate catch anything wrong. The maintainer wants evidence, not a guess, that a lower-tier model meets the same bar, so that the project stops paying for capability it doesn't use.

There's a second, unrelated cost problem. Closing the app's ingress was meant to leave it scaled to zero, and it doesn't. Closing ingress removes the app's only scale rule, the HTTP one, so a replica that is already awake never scales down. One replica ran from the deploy on 2026-10-06 until the maintainer deactivated its revision by hand on 2026-10-19. Once the monthly free grant ran out around 2026-10-11, that cost about €1.14 a day. Today the app is stopped only because its revision is deactivated, and the next deploy will start the leak again unless the deploy job's close step is fixed.

## Solution

Run a **Model comparison**: three full eval runs of `claude-haiku-5-5` at effort `high`, set beside three Opus runs, on the same prompt (1.3.0) and the same golden set.

The Opus side costs nothing new. The three pushes to `main` since prompt 1.3.0 each ran a full live eval: CI runs 37065847534, 37066259507 and 37536287167. Their reports are CI artifacts, kept until about 2026-12-31. All three were checked on 2026-10-19: `claude-opus-5-5` at `medium`, prompt 1.3.0 (`f326caf4f478e95d`), 48 documents, 48 live calls each, the cache never read, the gate passed, every hard gate at zero, structural leaves at 100/100, tunable leaves at 99.91 to 100, appendix rate 0.70%, $3.32 to $3.33 and 214 to 238 s per run. No more Opus runs will be paid for.

The maintainer runs the three Haiku runs locally, the same way as the ticket 10 baseline. The comparison is committed as a dated record.

- If Haiku passes, it becomes the default labeller, and an ADR records the choice and the numbers.
- If it fails narrowly, the maintainer decides at the time whether to tweak the prompt, with the agent's advice.
- If it fails widely, Sonnet 5.5 gets the same treatment.
- If Sonnet also fails, Opus stays the default, and the record says so.

Once a cheaper model is the default, Phase 2 starts.

The scale-to-zero fix ships in the same pull request, because that's the first merge to `main` that makes a real change. From then on, "off" means the app's revision is deactivated, not only that its ingress is closed. The deploy job's close step and the demo script's `down` deactivate the revision, and `up` activates it again first.

## User Stories

Actors: the *maintainer* (runs the evals, makes the calls), the *reviewer* (reads the evidence), *CI* (the eval gate and the deploy job), *Phase 2* (which inherits the default model and the comparison method), and a *sub-agent* (implements one ticket).

### The comparison

1. As the maintainer, I want to know whether Haiku 5.5 passes the eval gate on all three runs, so that I can stop paying Opus prices for a task a cheaper model handles.
2. As the maintainer, I want the comparison set against Opus runs that already exist, so that it costs no new Opus spend.
3. As the maintainer, I want the Opus reference to be on the same prompt version and golden set as Haiku, so that the only differences are the model and its effort.
4. As the reviewer, I want the record to state plainly that the two sides differ in effort as well as model (Opus `medium`, Haiku `high`), so that I read the result as a comparison of configurations.
5. As the maintainer, I want Haiku run at effort `high`, so that it gets a fair chance at a task Opus does at `medium`.
6. As the maintainer, I want three Haiku runs, not one, so that the result has a spread I can set beside Opus's.
7. As the maintainer, I want a one-document smoke run before the full runs, so that a wrong model id or a rejected effort setting costs a fraction of a cent, not a full run.
8. As the maintainer, I want each run uncached, so that each one is a real, independent labelling.
9. As the maintainer, I want the Haiku runs never to reuse or overwrite cached Opus answers, so that the cache stays valid for the configuration CI uses. The cache key already covers the whole `LabellerConfig`.
10. As the maintainer, I want each run's report kept outside the gitignored report path, which the next run overwrites, so that all three survive.
11. As the maintainer, I want Haiku's cost reported from the price table, not as zero, so that the comparison shows the saving in dollars.
12. As the maintainer, I want Haiku's price taken from Anthropic's own pricing page and the check date recorded, so that the cost figures can be trusted.

### The verdict

13. As the maintainer, I want any failed hard gate, any wrongful removal and any labelling failure in any run to disqualify the candidate, so that no PII leak or lost text is ever traded for cost.
14. As the maintainer, I want a run that failed only because the provider was unavailable to be re-run once and noted, so that the verdict is about the model's labelling, not Anthropic's uptime.
15. As the maintainer, I want the thresholds in `eval/thresholds.yaml` applied unchanged, so that the bar is the product's, not whatever the cheaper model managed.
16. As the maintainer, I want everything above the gate shown side by side: structural and tunable precision and recall, appendix rate, punctuation, cost, tokens, wall time and retries, each with both sides' spreads, so that I can make the call on the margins.
17. As the maintainer, I want the agent's advice on any failure, covering what failed, where, and whether one cause explains it, so that I can decide on a prompt tweak with the evidence in front of me.
18. As the maintainer, I want to make that call myself when a failure happens, not by rules set in advance.
19. As the maintainer, I want Sonnet 5.5 compared the same way if Haiku fails, so that I still find the cheapest model that passes.
20. As the reviewer, I want a negative result committed too, so that "Opus remains, and here's why" is evidence, not a gap.

### The record

21. As the reviewer, I want one committed, dated comparison file, so that the evidence outlives the CI artifacts, which expire around 2026-12-31.
22. As the reviewer, I want the comparison file in the same shape as the baseline file: the configurations, prompt and schema versions, documents per run, per-run totals, the spread of each side, gate results, cost and wall time, so that the two records read alike.
23. As the reviewer, I want the comparison file to name the six reports it was built from (CI run ids for Opus, local run numbers and dates for Haiku), so that every number can be traced to a source.
24. As the reviewer, I want the verdict and the reasoning in the ticket, so that the decision can be read without opening JSON.
25. As the reviewer, I want the comparison kept separate from the **Baseline**, so that the record the thresholds came from is never confused with this one.

### The default switch (only if a cheaper model passes)

26. As the maintainer, I want the winning model and its effort to become the labeller's defaults, so that CI's eval, the deployed app and local runs all switch at once. Nothing else pins the model.
27. As the reviewer, I want ADR-0011 to record which model was chosen, the alternatives, the numbers and the trade-off, so that a cheaper model looks like a deliberate decision.
28. As the maintainer, I want the docs that name the Opus configuration updated where they describe the current default (CLAUDE.md, the development guide, the thresholds file's header), so that nothing contradicts the code.
29. As the maintainer, I want the thresholds file's header to keep saying the thresholds were derived from the Opus baseline, so that the history is accurate.
30. As CI, I want the merge's live eval to run on the new default, so that the first post-switch gate is itself evidence that the switch holds, at a fraction of the old cost.
31. As Phase 2, I want the new default and the comparison method in place, so that the second-provider work compares against the cheaper default in the same way.

### Stopping the app properly

32. As the maintainer, I want the deploy job to leave the app with zero running replicas, so that a deploy never starts a replica that bills around the clock.
33. As the maintainer, I want the deploy job to deactivate the new revision after the smoke test, whether the test passed or failed, once the Azure login has succeeded, so that a failed smoke test can't leak either.
34. As the maintainer, I want `demo.sh up` to activate the revision before opening ingress and waking the app, so that demos still work.
35. As the maintainer, I want `demo.sh down` to close ingress and then deactivate the revision, and to fail loudly if a replica is still running afterwards, so that "closed" is checked, not assumed.
36. As the maintainer, I want the scripts' messages to stop claiming that closing ingress scales the app to zero, so that the logs don't repeat the mistake.
37. As the maintainer, I want the post-merge check to be the replica list, not the cost dashboard, so that the proof is direct and immediate. The dashboard lags and hides the free grant.
38. As the reviewer, I want ADR-0010 amended to say why closing ingress wasn't enough and what "off" means now, so that the deployment's reasoning stays honest.
39. As the maintainer, I want the static workflow and script tests to pin the deactivate and activate steps, so that a later edit can't quietly remove them.

### Delivery

40. As the maintainer, I want every ticket small enough for one sub-agent to finish in under about 180,000 tokens, so that the work can be done in parallel and reviewed in small pieces.
41. As the maintainer, I want everything in one pull request and one merge to `main`, so that there's one paid eval and one deploy.
42. As the reviewer, I want the pull request description to carry the comparison table, the verdict and the cost, per the eval-run rule, so that the evidence sits with the change.
43. As the maintainer, I want a release note and the CLAUDE.md status updated after the merge, so that the next session starts from the true state.

## Implementation Decisions

- **No pipeline, prompt or schema change.** Prompt 1.3.0 and schema 1.0.0 stay as they are. A prompt tweak happens only if the maintainer chooses one after a narrow failure. It would then be a version bump with its own eval, and the comparison record would name both prompt versions.
- **The eval runner is unchanged.** The configuration comes in through the existing `CVR_LABEL_MODEL` and `CVR_LABEL_EFFORT` environment variables. No new flag, workflow input or CI job.
- **Price table:** `cvr.label.pricing` gains `claude-haiku-5-5` (and, only if needed later, `claude-sonnet-5-5`), with input and output prices per million tokens from Anthropic's pricing page and the check date refreshed. Every prompt in the golden set is far below Haiku's 100K-token long-prompt tier, so the base rates apply. The price table stays a two-number lookup.
- **Runs:** the maintainer runs them locally in Git Bash, with the key in their shell. First a smoke run (one Candidate, one Layout), then three full runs, each with `--no-cache`. After each run, `report.json` and `report.md` are copied into a per-run folder under the gitignored `.cache/`.
- **Comparison record:** one committed file under `eval/`, named `model-comparison-<date>`, in JSON, shaped like `baseline-2026-09-29.json`. It holds the reference and candidate configurations, versions, documents per run, the per-run totals of all six runs, each side's spread per metric, each run's gate result, cost and wall time, the sources (CI run ids and local run labels), and a verdict field. It's assembled from the six reports. Nothing reads it at run time.
- **Verdict rule:** any hard-gate breach, labelling failure or error in any run disqualifies the candidate, except for errors that were only `ProviderUnavailable`. A run with only those is re-run once and noted. Thresholds are applied unchanged. Above the gate, the verdict is the maintainer's call on the side-by-side numbers.
- **Default switch (conditional):** `DEFAULT_MODEL` and `DEFAULT_EFFORT` in the labeller config change to the winner. The configuration test that pins the default changes with it; that's the decided value moving, not a test bent to fit. Nothing outside the code pins the model: the app's environment has only the two keys, and neither the workflows, the Dockerfile nor the scripts set `CVR_LABEL_*`. ADR-0011 records the decision. `eval/thresholds.yaml` keeps its numbers.
- **Stopping the app properly:** the deploy job's always-run close step closes ingress and then deactivates the active revision. `demo.sh up` activates the latest revision before opening ingress. `demo.sh down` deactivates the revision after closing ingress and checks that no replica is running. Revisions are named at run time, never hard-coded, because every deploy creates a new one. Every `az` call keeps the existing `--output none` or narrow `--query` discipline, so no identifier reaches public logs. ADR-0010 gets an amendment, not a rewrite.
- **Tickets** (written by `/to-tickets`, each sized for one sub-agent):
  1. Price Haiku 5.5, and write the run instructions. Sub-agent.
  2. The Haiku runs. The maintainer does these; there's no code.
  3. The comparison record and the verdict. Sub-agent, blocked by 2.
  4. Make the winner the default, with ADR-0011 and the docs. Sub-agent, only if 3 passes.
  5. Stopping the app properly. Sub-agent, independent, can start now.

  If Haiku fails widely, a Sonnet ticket follows, covering its price, runs and record. Everything ships in one pull request.
- **Done:** the winner, or "Opus remains", is recorded. The fix is merged. The deploy after the merge finished with zero running replicas. The release note and CLAUDE.md status are updated. Phase 2 starts if a cheaper model became the default.

## Testing Decisions

- A good test observes behaviour through the highest seam that already exists: the cost a `LabelRun` reports, the configuration the labeller is built from, the steps a workflow job runs, and the commands a script issues. It never tests how they're implemented.
- **The eval gate is the comparison's test.** No unit test calls a model, and none is added. The three Haiku runs and the merge's live eval are the evidence.
- **Pricing:** extend the existing price-table test. Haiku is in the table, `estimate_cost` gives the expected dollars for a million tokens each way, and the check date isn't empty.
- **Default switch:** the existing configuration test that asserts the default model is updated to the winner. Add an assertion for the default effort if one is missing.
- **Stopping the app properly:** extend the existing static checks in `tests/ci/`. The workflow test pins that the deploy job's close step runs after the smoke test under the existing always-once-logged-in condition, and that it deactivates the revision after closing ingress. The deploy-scripts test pins that `up` activates before opening ingress, that `down` deactivates after closing ingress and checks replicas, and that neither leaks an identifier. Prior art: `tests/ci/test_workflow.py` and `tests/ci/test_deploy_scripts.py`, which already pin the ingress open/close shape the same way.
- **Live proof of the fix:** after the merge, the deploy run finishes and the app's replica list is empty. That check is recorded in the ticket. It isn't automated, because it needs Azure credentials.
- **Comparison record:** no test. It's a dated record of evidence, like the baseline file. Its numbers are checked against the six reports when it's assembled, and the ticket says so.

## Out of Scope

- Any change to the pipeline, the verifier, the metrics, the golden set or the template.
- Any prompt or schema change, unless the maintainer decides on one after a narrow failure.
- More Opus runs.
- Lowering, raising or re-deriving any threshold, and any new **Baseline**.
- Models from other providers. That's Phase 2, which uses the same **Model comparison** method.
- Batch API pricing, prompt caching and other cost-reduction techniques.
- A CI input or workflow for choosing the model.
- A nightly auto-off job, IP restrictions or a front door for the app. How demos open the app is still to be revisited when a later phase plans them.
- Effort sweeps (for example Haiku at `medium`, `xhigh` or `max`), unless a failure leads the maintainer to ask for one.

## Further Notes

- The Opus artifacts expire around 2026-12-31 to 2027-01-04. Ticket 3 must run before then. Once the record is committed, nothing else depends on the artifacts.
- The Haiku prices in this session came from third-party write-ups ($0.10 in and $0.50 out per million tokens below 100K). Ticket 1 must replace them with Anthropic's own figures.
- If Haiku becomes the default, each future live eval costs cents, not $3.30. That changes the cost note in the cost-conscious merge habit, and CLAUDE.md's "a full uncached run is about $3.3" must be updated.
- The app is stopped right now only because its revision was deactivated by hand. Any merge to `main` that deploys before ticket 5 is merged will start the leak again. This pull request must contain ticket 5.
