# 09: Eval runner and report

**What to build:** The gate gets a number. `python -m cvr.eval.run [--layout X] [--candidate cNN] [--no-cache]` takes every generated document (or the filtered subset), runs `reformat` with the real labeller, walks the output through the adapter, applies every metric, and writes `eval/report.json` (gitignored) and `eval/report.md`, exiting non-zero on any hard-gate breach or missed threshold from `eval/thresholds.yaml` (the file may hold placeholder thresholds until ticket 10 sets them; hard gates apply regardless). Live LLM calls go through a gitignored local response cache keyed `(model, prompt hash, schema hash, source sha256)`, so local iteration is free after the first run and CI is never theatre. Bounded async concurrency (about four) with retry-and-backoff on rate-limit responses from the first version. Report order: per-metric totals; per layout; per tag; per candidate; then `LabellerConfig`, prompt and schema label and hash, tokens, cost, wall time, cache hits. The runner is tested with the oracle labeller over a subset for shape and exit code, and run for real once locally to produce the first report, whose markdown goes in the PR description.

**Blocked by:** 06 (Pipeline function), 07 (The real labeller)

**Status:** in-review

- [x] `cvr.eval.run` module and `__main__` entry; the `eval/` directory holds only `thresholds.yaml`, the gitignored report and (later) the dated baseline
- [x] Cache: second run with identical key makes zero LLM calls; `--no-cache` bypasses it; the cache directory is gitignored and excluded from the image
- [x] Concurrency bounded; a 429 is retried with exponential backoff and jitter, and the report counts retries
- [x] `report.json` schema: totals, per layout, per tag, per candidate, config, versions (label and hash), tokens, cost, wall time; `report.md` renders the same with the totals table first
- [x] With the oracle labeller over four documents: exit code 0, every breakdown present; with an oracle that omits a leaf and a placement threshold of 100: exit code 1 and the summary names the failing metric and candidate
- [x] Hard gates (added, dropped, provenance, PII, image, ordering, structural leaves) fail the run irrespective of thresholds; `punctuation_fidelity` fails the run only when `hard: true`
- [ ] First real run over all 48 documents completed locally; the markdown summary and cost pasted into the PR description
- [x] `thresholds.yaml` committed with placeholders and a comment pointing at ticket 10

## Comments

### 2026-09-24: built, in review (branch `phase-1/09-eval-runner-and-report`)

**What was built.** `src/cvr/eval/run/`, a package so that `python -m cvr.eval.run` runs its `__main__.py`:
- `documents`: `Document`, `document`, `generated_stems`, and `select` for `--layout`/`--candidate` (both repeatable). A filter value matching nothing is an error, not an empty run that passes.
- `score`: every metric over one real run, moved out of `tests/pipeline/pipeline_support.py` as ticket 06 intended. `pipeline_support` now re-exports it. `Scores` also carries the appendix and source-content token counts.
- `cache`: `ResponseCache`, `CachedLabeller`, `cache_key`, `LabellerIdentity`.
- `runner`: `run_documents`, with bounded concurrency and retry.
- `thresholds`: `load_thresholds` over `eval/thresholds.yaml`.
- `report`: `Totals`, `gate`, `Report`, which renders both the JSON and the markdown.

`main(argv, labeller=...)` is the command line. The tests pass the oracle in place of the real labeller; everything else runs as CI will run it. `eval/thresholds.yaml` is committed with placeholders (placement minimum 0, appendix maximum 100, punctuation soft) and a comment pointing at ticket 10. PyYAML was added through `uv add --dev`.

**The first real run over all 48 documents is still pending.** It needs `ANTHROPIC_API_KEY`, which the build environment did not have, so no live call was made and no report or cost exists yet. The checkbox stays unticked. To produce the first report, the maintainer runs this with the key set:

```
uv run python -m cvr.eval.run
```

That makes 48 live calls at the default `claude-opus-5-5`, effort `medium`, and fills `.cache/eval-responses/`. Then paste `eval/report.md` (it includes the cost) into the PR description.

**Decisions beyond the ticket text.**

- **The cache key covers the whole `LabellerConfig`, not only the model.** A change to effort, temperature or any other knob counts as a model change under the eval-run rule, so it must miss the cache as well. The key is the sha256 of `{config, prompt hash, schema hash, source sha256}`. A hand-bumped version label with no content change leaves the key unchanged. The cache sits at `.cache/eval-responses/<key>.json` and `.cache/` is gitignored. There is no Dockerfile yet, so keeping it out of the image is carried to ticket 12: its `.dockerignore` must exclude `.cache/` (noted in `docs/development.md`).
- **`--no-cache` skips the lookup but still writes the fresh answer**, so the next cached run replays the latest. For ticket 10: to keep each baseline run replayable ("exits 0 on the cached best run"), give each run its own `--cache-dir`, for example `--no-cache --cache-dir .cache/baseline-1`. Then rerun the best with `--cache-dir` and no `--no-cache`.
- **A labelling failure is cached like any answer**, because it is what the model said. A provider error is never cached. A fully cached run needs no API key, because the chat model is built on the first miss.
- **What is retried.** The label node raises `ProviderUnavailable` for a 429, a 5xx, a timeout or a dropped connection, and only after the Anthropic client's own two retries. The runner catches that from `reformat` and retries the document up to 5 more times. The wait is 2s doubled per retry, capped at 60s, and scaled by jitter into its upper half. Only these outer retries are counted in the report: the client's inner retries are not visible to it, and the report says so. `LabellerMisconfigured` is not retried. Any other exception is a defect: the document is recorded as errored and its traceback printed. That fails the run under an `errors` hard gate, and the other documents' results are kept.
- **Only the labelling runs concurrently.** A stress loop over the runner tests turned up an intermittent "not a Word file" from `parse` in a worker thread. python-docx parses through one module-level lxml parser, and lxml parsers are not safe to share between threads. Parse, verify, transform, render and scoring now run under one lock, which each document releases only while its labeller is called. A test pins it: scoring never overlaps, labellers do. **This matters to ticket 11 as well.** A sync FastAPI endpoint runs `reformat` in a thread pool, so two concurrent requests can hit the same race.
- **The gate.** Hard gates are judged per document and name the documents that breach them. They are: errors, added, dropped, provenance, PII, image, ordering (`OrderingReport.correct`), and structural leaves (hits = actual = expected over name, title, employer, location, date, institution, qualification). Thresholds are judged on the run's totals, since ticket 10 sets them from whole runs, and a failure still names the candidates that fall short on their own.
  - `placement_accuracy.min` holds precision and recall of the tunable leaves separately, never their F1. That is one tally over profile, skills, bullets, details, certifications and additional, per `FieldType.structural`.
  - `appendix_rate.max` holds the token-weighted rate over the run: appendix tokens over source tokens less those the Run removed.
  - Both are percentages. `punctuation_fidelity` fails the run only when `hard: true`.
  - The loader requires exactly the three settings, so a misspelt key is an error rather than a gate left at its default.
  - Label failures are counted but are not a gate of their own. They always breach structural placement anyway.
- **`eval/report.md` is gitignored beside `report.json`.** It is regenerated on every run, so committing it would churn; ticket 10 commits the dated baseline, and ticket 13's CI job uploads both as artifacts. `eval/` holds only `thresholds.yaml` in the repo.
- **Report contents beyond the list.**
  - After the ticket's order (totals, per layout, per tag, per candidate, config, versions, tokens, cost, wall time), the JSON continues with the cache (on, reads, hits, live calls), retries, the thresholds in force, the gate (passed, and each failure's metric, detail, candidates and documents), and one detail block per document: every finding, per-field placement tallies, ordering, appendix, label failure reason, retries, cache hit and seconds.
  - Cost is given twice: what the labellings cost when they were made, and what this run spent (live calls only).
  - The markdown puts a one-line verdict under the title, then the totals table, then the other tables in the same order, then labeller and usage, then the gate.
- **Three extra flags:** `--thresholds`, `--out` and `--cache-dir`. The tests need them to run in isolation, and ticket 10 needs a cache per baseline run.
- **PyYAML is in the dev group.** `eval` is excluded from the runtime image, so the parser never needs to reach it. CI's plain `uv sync` installs dev.

**Code review (`code-review` skill, against `origin/release/phase-1-09-11`).**

Standards: no hard violations. Fixed:
- one `REPO_ROOT` in place of two walks up from the generator's directory;
- one `label_run_of` for the `last_run` convention, which had been duplicated;
- `CacheStats.record_hit`/`record_live_call`, whose old names read as queries;
- the unused `Scores.appendix_rate` removed;
- a misleading `_Entry` docstring;
- what this run spent is now a `Report` field, not a magic key stripped out of the cache dict;
- the retries line now says what it counts.

Left as judgement calls:
- `build_chat_model` is imported from `cvr.label.labeller`, where it is in `__all__`, rather than from the package;
- `Scores.hard_gates` (five metric gates, used by the pipeline tests) differs from the report's eight (plus errors, ordering and structural);
- `DocumentResult` is built in two branches;
- `Report.markdown` delegates to `_markdown`.

Spec: the partial retry count and the `--no-cache` semantics are recorded above. Pooling the tunable field types under one minimum follows story 54 ("placement minimum", singular) and is recorded above for ticket 10. The extra flags, the `errors` gate, the two cost figures, the per-document detail and the widened cache key are all recorded above as decisions. The live run and the image exclusion stay open as stated.

**Tests.** `tests/eval/run/`, 43 default tests plus 1 slow:
- the command end to end with the oracle over c04's four documents: exit 0 at the tightest thresholds with every breakdown, and the key order of `report.json` and `report.md`;
- an omitted bullet with `placement_accuracy.min: 100`: exit 1, and the summary line `placement_accuracy (tunable): recall … (c04)`;
- the same omission passing the placeholders;
- an unlocatable title failing `placement_accuracy (structural)` whatever the thresholds;
- a second command replaying the cache, and `--no-cache` bypassing it;
- the cache (zero labeller calls on a second run, replayed scores and `LabelRun`, the key moving with config, prompt, schema and source, failures cached, errors not);
- retry and backoff with a fake sleep, gave-up, misconfigured not retried, the concurrency bound, and labelling-only concurrency;
- the gate over synthetic totals (every hard gate irrespective of thresholds, punctuation only when hard, threshold arithmetic, order);
- the filters and the thresholds file.

The slow test runs the command over all 48 documents with the perfect oracle: exit 0, with the appendix maximum at 1% because c09 and c11 carry unplaceable fragments.

Totals: default suite 1067 passed, 1 skipped (the label spike, no key), about 27–30s on this machine, up from about 23s. Slow suite 817 passed, about 43s.
