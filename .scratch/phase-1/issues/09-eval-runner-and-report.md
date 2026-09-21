# 09: Eval runner and report

**What to build:** The gate gets a number. `python -m cvr.eval.run [--layout X] [--candidate cNN] [--no-cache]` takes every generated document (or the filtered subset), runs `reformat` with the real labeller, walks the output through the adapter, applies every metric, and writes `eval/report.json` (gitignored) and `eval/report.md`, exiting non-zero on any hard-gate breach or missed threshold from `eval/thresholds.yaml` (the file may hold placeholder thresholds until ticket 10 sets them; hard gates apply regardless). Live LLM calls go through a gitignored local response cache keyed `(model, prompt hash, schema hash, source sha256)`, so local iteration is free after the first run and CI is never theatre. Bounded async concurrency (about four) with retry-and-backoff on rate-limit responses from the first version. Report order: per-metric totals; per layout; per tag; per candidate; then `LabellerConfig`, prompt and schema label and hash, tokens, cost, wall time, cache hits. The runner is tested with the oracle labeller over a subset for shape and exit code, and run for real once locally to produce the first report, whose markdown goes in the PR description.

**Blocked by:** 06 (Pipeline function), 07 (The real labeller)

**Status:** ready-for-agent

- [ ] `cvr.eval.run` module and `__main__` entry; the `eval/` directory holds only `thresholds.yaml`, the gitignored report and (later) the dated baseline
- [ ] Cache: second run with identical key makes zero LLM calls; `--no-cache` bypasses it; the cache directory is gitignored and excluded from the image
- [ ] Concurrency bounded; a 429 is retried with exponential backoff and jitter, and the report counts retries
- [ ] `report.json` schema: totals, per layout, per tag, per candidate, config, versions (label and hash), tokens, cost, wall time; `report.md` renders the same with the totals table first
- [ ] With the oracle labeller over four documents: exit code 0, every breakdown present; with an oracle that omits a leaf and a placement threshold of 100: exit code 1 and the summary names the failing metric and candidate
- [ ] Hard gates (added, dropped, provenance, PII, image, ordering, structural leaves) fail the run irrespective of thresholds; `punctuation_fidelity` fails the run only when `hard: true`
- [ ] First real run over all 48 documents completed locally; the markdown summary and cost pasted into the PR description
- [ ] `thresholds.yaml` committed with placeholders and a comment pointing at ticket 10
