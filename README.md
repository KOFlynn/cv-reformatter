# CV Reformatter

Reformats a candidate CV (`.docx`) into a fictional recruitment agency's branded Word
template, **Fictitious Recruitment**. Sections are reordered into the template's fixed
order, experience and education are sorted reverse-chronologically, personal contact
details are removed and dates are normalised to `MM/YYYY`. **No wording is ever changed
or generated.**

Recruitment agencies commonly pay someone to reformat candidate CVs into a house
template by hand. The work is manual and repetitive, and it carries one hard rule:
never change the candidate's words. This project automates that job and treats the rule
as a design constraint, not a hope.

## What this is not

A **portfolio demo**, not a product. It has no real users, will never process a real
CV, and is not for sale. That does not make the CI gate optional: the service is still
deployed, so a real gate blocks a real deployment. Every fixture, cache and log in this
repository is synthetic; see the working rules below.

## Status

**Phase 1 is complete** ([release note](.scratch/phase-1/release-01-19.md)): the
pipeline runs end to end on the golden set, the eval gate stands in front of every
merge, and a merge that passes it is deployed to Azure Container Apps through OIDC.
**Phase 2 is next:** LangGraph with a bounded retry loop, Langfuse tracing, and Azure
OpenAI as a second provider through a managed identity. Phase 3 is an MCP server. The
brief's §10 has the exit criteria for each.

| Phase 1 in numbers | | Evidence |
|---|---|---|
| Golden set | 12 Candidates × 4 Layouts = 48 documents | `fixtures/` |
| Eval baseline | 3 runs on prompt 1.1.0, every hard gate held, tunable placement 99.65–100%, appendix 0.73–0.76% | [`eval/baseline-2026-09-29.json`](eval/baseline-2026-09-29.json) |
| Thresholds | tunable placement ≥ 98%, appendix ≤ 2%, punctuation fidelity hard | [`eval/thresholds.yaml`](eval/thresholds.yaml) |
| Current prompt (1.3.0) | every hard gate held, tunable placement 100% (1128 of 1128), appendix 0.70% | ticket 19, [#34](https://github.com/KOFlynn/cv-reformatter/pull/34) |
| Cost of one full eval run | about $3.30 and four minutes, 48 live labellings | the eval report's cost line |
| Cost of one document | about $0.07 (about 5,400 tokens in, 2,400 out) | ticket 14's Log Analytics row |
| Image | 325 MB, non-root, no key, no golden set or eval code | `scripts/check-image.sh` |
| Cold start / warm | 25.9 s from zero replicas / 0.19 s; `scripts/demo.sh up` absorbs the cold start before a demo | ticket 14 |
| Azure cost, 2026-10-01 to 10-06 | €0.00 | ticket 14, [#36](https://github.com/KOFlynn/cv-reformatter/pull/36) |
| The gate stopping a bad prompt | `eval` red on 12 of 12 Candidates, `deploy` skipped | [#32](https://github.com/KOFlynn/cv-reformatter/pull/32) |

## The invariant

**The LLM never writes output text — it only labels.** It returns
`{field, block_id, quote}` assignments pointing at source text; a verifier checks each
`quote` is an exact substring of its source block; the rendered output always uses the
located source slice, never the model's string. Any change that routes LLM-generated
text into the rendered document is a defect.

## What this evidences

The project exists to close a specific set of gaps seen across AI-engineering job
descriptions, not to be an impressive feature. The full mapping is
[`docs/project-brief.md`](docs/project-brief.md) §1; in short:

| Gap | Closed by | Phase |
|---|---|---|
| Agentic framework, hands-on | A LangGraph workflow with a bounded retry loop over the same node boundaries as Phase 1 | 2 |
| MCP server built from scratch | An MCP server exposing `reformat_cv` | 3 |
| Docker, CI/CD | A Dockerfile, GitHub Actions, deployment to Azure Container Apps | 1 |
| Eval and observability tooling | A golden-set eval gate in CI; Langfuse tracing | 1, 2 |
| OAuth 2.0 / OIDC, Entra ID | GitHub Actions to Azure via an OIDC federated credential; a managed identity from Container Apps to the LLM | 1, 2 |
| Vector DB / RAG | Deliberately not covered — see decision 8 below | — |

## The pipeline

```
.docx ──► parse ──► label (LLM) ──► verify ──┬──► transform ──► render ──► .docx
                                   ▲         │   (remove, dates,  (docxtpl)
                                   └─ retry ◄┘    sort)
                                  (≤ N, Phase 2)   unplaced ──► appendix
```

`parse` turns the source `.docx` into ordered, addressable blocks (python-docx for
paragraphs, tables, headers and footers; raw XML via `lxml` for text boxes, which
python-docx doesn't expose). `label` sends those blocks to an LLM, reached through
LangChain's chat-model interface with structured output, and gets back reference
assignments — never prose. `verify` checks every reference against its block through a
per-block claim ledger, so that removals always win over placement, conflicting claims
are rejected loudly, and anything left over is logged as residue. `transform` is pure
code: removal rules, a regex PII backstop, date normalisation, and reverse-chronological
ordering. `render` fills the committed template through `docxtpl`, including the review
appendix for whatever verification never placed. Phase 2 turns the same five nodes into
a LangGraph state machine and adds a bounded retry loop between `verify` and `label`;
Phase 1 is a plain function pipeline with identical boundaries, so that swap is a change
of orchestration, not of code. All five nodes (`parse`, `label`, `verify`, `transform`
and `render`) are packages under `src/cvr/`, `cvr.pipeline.reformat` wires them
together, and `cvr.api` serves it as `POST /reformat` and `GET /health`. The `graph`
wrapper is Phase 2 and the `mcp` server Phase 3.

## Decisions

Nine decisions, one per §12 of the brief, each linking the ADR that holds the detail.
Written early in Phase 1, while the reasoning from the design sessions was fresh, and
revised at its end with the numbers that now exist. The ten ADRs are listed after the
nine decisions.

### 1. The LLM labels, code transforms

This is the invariant above, restated as a decision with an alternative on record. The
alternative — an LLM that rewrites the CV into the template, or one that extracts
straight to output JSON — was rejected because either way the invariant becomes
something tested after the fact rather than a property of the code, and both let
LLM-generated characters reach the document. Consequence: added text is impossible by
construction; the eval's added-text gate exists only to catch bugs in our own code,
never in the model's wording.
[ADR-0001](docs/adr/0001-llm-labels-code-transforms.md),
[ADR-0007](docs/adr/0007-provenance-check-and-blind-spots.md) (how the check covers
what a plain substring test alone would miss),
[ADR-0009](docs/adr/0009-structured-labelling.md) (how the label node reaches a real
provider without weakening any of this).

### 2. A generated golden set

Twelve fictional Candidates (`fixtures/candidates/*.json`) are hand-reviewed ground
truth; four Layout generators render each into a messy source `.docx`, giving 48
committed documents with exact expected output. The alternative, downloaded or scraped
CVs, was rejected: it needs hand-labelling, carries licensing risk, and would put real
people in a public repository. Consequence: eval runs are reproducible without rerunning
a generator, at the cost of only proving the pipeline against documents we designed —
mitigated by a source-coverage test that checks every fixture string actually appears in
each generated document. [ADR-0002](docs/adr/0002-generated-golden-set.md).

### 3. `.docx` only

Input and output are Word `.docx`, nothing else, for this build. PDF input was
considered and rejected for now: it roughly doubles the parsing problem (layout
recovery, reading order, no structural markers) for no benefit on the gap list above.
Consequence: PDF is a possible later phase, and the `parse` node's boundary is exactly
where it would slot in — nothing else in the pipeline would need to change.
[ADR-0003](docs/adr/0003-docx-only.md).

### 4. Review by exception, no interactive human-in-the-loop

Source text that verification (and, from Phase 2, bounded retries) cannot place goes
into a final review appendix behind a large red banner, and the job completes anyway.
An interactive human-in-the-loop step was rejected: it adds a UI and a state store to
evidence nothing on the gap list, and turns a deterministic job into a workflow with a
person inside it. So was failing the job outright on any unplaced text: nearly every
messy CV would fail, and the point of the demo is that the job always finishes.
Consequence: review is by exception, never a queue; and per ADR-0009, no endpoint will
ever return a run's transform log, because that would be the first half of the review
queue this project deliberately does not build.
[ADR-0004](docs/adr/0004-review-by-exception.md),
[ADR-0009](docs/adr/0009-structured-labelling.md).

### 5. Provider chosen by eval results

Which LLM provider the service uses is decided by running the same eval against
Anthropic and Azure OpenAI and comparing the numbers, not by preference set up front.
**Phase 2:** only Anthropic is wired up (`cvr.label`, `claude-opus-5-5` at effort
`medium`); Azure OpenAI arrives as a second provider in Phase 2, through a managed
identity rather than a stored key, and the comparison and the choice are recorded in
the ADR that follows it once real numbers exist. Phase 2 has not yet been broken into
tickets. What already exists to make that comparison mechanical — the chat
model swapped through `init_chat_model` against the same schema and the same verifier —
is recorded now: [ADR-0009](docs/adr/0009-structured-labelling.md).

### 6. No scoring, filtering or matching

The system reformats one CV at a time and never compares, ranks, scores or filters
candidates against anything. The alternative this rules out is the obvious next
feature — candidate search or matching — rejected because it would make the system a
high-risk AI system under EU AI Act Annex III, point 4 ("analyse and filter job
applications, and to evaluate candidates"). Consequence: this is a scope boundary
recorded as a decision, not a missing feature, and it is also why RAG is not on the
gap-list table above. [ADR-0005](docs/adr/0005-no-scoring-no-rag.md).

### 7. Container Apps scaled to zero; OIDC for CI; managed identity at runtime

A merge to `main` that passes the eval is deployed by the `deploy` job of
`.github/workflows/ci.yml`, which needs `eval` and runs on pushes to `main` only. It
pushes the image to a public GHCR package, pulls it back anonymously and repeats the
image's secret inspection, then moves the Azure Container Apps app `cvr-ca` to it. It
then opens the app's ingress, runs a smoke test that posts a golden-set document to the
live endpoint and checks that a request without the API key gets 401 and one with it
gets a `.docx` with its `X-Run-Id`, and closes ingress again whatever the smoke test
said.

The app runs on the consumption plan in `northeurope`: zero replicas when idle, one at
most, probes on `/health`, and logs to Log Analytics. Its ingress is **off by
default**: the URL is in this repository's history, and any request through ingress
wakes the app, so it is opened only for a deploy's smoke test and for demos
(`sh scripts/demo.sh up`, then `down`). While it is open, `POST /reformat` needs the
`X-API-Key` header, so a stranger cannot spend the LLM key's credit; wake-ups are
bounded by the one replica. GitHub Actions signs in to Azure through an OIDC federated
credential whose subject is this repository's `main` branch, so no Azure credential is
stored in GitHub: the job's `id-token: write` is granted to `deploy` alone. The three
ids it logs in with are not credentials, but they are repository secrets anyway, so
GitHub masks them in the logs of a public repository. The runtime credentials, the LLM
key and the API key, are Container Apps secrets. In Phase 2 the LLM path moves to a
managed identity, so the LLM key goes.

The alternatives rejected are a stored service-principal secret in GitHub and an
always-on replica. Neither survives the "no credential in GitHub" evidence goal or the
free-grant budget. The price of scaling to zero is a cold start, measured at 25.9 s
from zero replicas against 0.19 s warm, which `scripts/demo.sh up` absorbs by waking the
app before a demo. How ingress is opened for demos is to be revisited when a later
phase plans them. What it buys: from provisioning on 2026-10-01 to 2026-10-06 the Azure bill was €0.00, the
only metered usage about 0.4 MB of log ingestion inside Log Analytics' free allowance.
The image is 325 MB.

The resources are provisioned once by hand through `scripts/provision-azure.sh`, a
wizard whose `az` commands are the record of what exists.
[ADR-0010](docs/adr/0010-deployment.md) records the resource names, the federated
credential's subject, the budget and its "kill anything that costs money" rule.

### 8. Why no RAG

Nothing in reformatting a single CV needs retrieval over a corpus. The obvious feature
that would want RAG — candidate search — is exactly the feature decision 6 rules out,
so closing this gap with RAG would mean reopening decision 6. Consequence: this gap on
the JD-mapping table above is deliberately left uncovered rather than closed with a
feature that would change the system's regulatory category.
[ADR-0005](docs/adr/0005-no-scoring-no-rag.md) (the same decision as item 6, recorded
once).

### 9. What changes at scale

Several of today's choices are shortcuts that a real deployment, with real CVs, would
have to revisit: one template instead of several, `.docx`-only input, provisioning done
once by hand instead of as code, and no data-protection story because there is no real
personal data yet. At scale: PDF input becomes worth the parsing cost (decision 3); a
second template means the `template` package growing past one committed file and one
script; the review appendix (decision 4) would need to become an actual review queue
with the endpoint decision 4 currently rules out; and real CVs would need data
residency guarantees and a DPA that synthetic fixtures never require. The deployment
half of this, infrastructure as code and a container registry with managed-identity
pull in place of the public GHCR package, is recorded in
[ADR-0010](docs/adr/0010-deployment.md). The `.docx`-only and
review-by-exception halves are already recorded: [ADR-0003](docs/adr/0003-docx-only.md),
[ADR-0004](docs/adr/0004-review-by-exception.md).

### The ADRs

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-llm-labels-code-transforms.md) | The LLM labels, code transforms |
| [0002](docs/adr/0002-generated-golden-set.md) | A generated golden set |
| [0003](docs/adr/0003-docx-only.md) | `.docx` only |
| [0004](docs/adr/0004-review-by-exception.md) | Review by exception |
| [0005](docs/adr/0005-no-scoring-no-rag.md) | No scoring, no RAG |
| [0006](docs/adr/0006-template-built-by-script.md) | The template is built by a committed script, never in Word |
| [0007](docs/adr/0007-provenance-check-and-blind-spots.md) | The provenance check and its blind spots |
| [0008](docs/adr/0008-claim-ledger.md) | `verify` through a per-block claim ledger |
| [0009](docs/adr/0009-structured-labelling.md) | Structured labelling through LangChain |
| [0010](docs/adr/0010-deployment.md) | Deployment: OIDC, a public image, scale to zero |

## Running it

```
uv sync                                 # install, using the Python 3.12 pinned in .python-version
uv run pytest -q                        # unit tests
uv run pytest -q -m slow                # the tests over all 48 generated documents
uv run ruff check .                     # lint
uv run ruff format --check .            # format check
uv run python -m cvr.golden.generate    # regenerate fixtures/generated/ after a Candidate or Layout change
uv run python -m cvr.template.build     # rebuild templates/fictitious_recruitment.docx after a build.py change
```

A CV through the whole pipeline, with the real labeller (these need `ANTHROPIC_API_KEY`;
the service also needs `CVR_API_KEY`, any value you choose, which callers send as the
`X-API-Key` header):

```
uv run python -m cvr.api                # serve POST /reformat and GET /health on 127.0.0.1:8000
uv run python -m cvr.eval.run           # the eval over all 48 documents; --layout, --candidate, --no-cache
docker build -t cvr:local .             # the service image
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY -e CVR_API_KEY cvr:local
```

The fuller command reference — dependency management, running one test directory,
useful `pytest` flags, the API's environment variables — is
[`docs/development.md`](docs/development.md). CI runs exactly the sync, lint,
format-check and both test steps above as its `check` job: on every pull request and
push to `main` in [`ci.yml`](.github/workflows/ci.yml), which then runs the eval gate and,
on `main`, the deploy; and on a push to any other branch in
[`branch.yml`](.github/workflows/branch.yml), which runs `check` alone. A push that
changes only docs runs nothing.

## The eval gate

`src/cvr/eval/` holds ten metrics as pure functions with sorted findings:
`added_tokens`, `dropped_tokens`, `removal_precision`, `provenance_violations`,
`pii_leak`, `image_leak` and `ordering_report` are **hard gates** — they must come back
exactly zero (or, for ordering, exactly correct) or CI fails regardless of any threshold.
`removal_precision` closes the hole `dropped_tokens` leaves: a logged removal counts as
accounted for, so a content line deleted under a PII rule lost candidate text without
failing anything. It checks every removed slice against what its own rule may remove
(the Candidate's PII values for that rule, or a heading the Layout wrote), so the only
text the output may lose is PII and the source's own headings.
`placement_accuracy` and `appendix_rate` are **thresholds**: a minimum and a maximum set
from evidence rather than picked in advance. `punctuation_fidelity` started as a reported
metric and was promoted to a hard gate once three baseline runs came back clean on it, so
the promotion was earned rather than assumed.

Thresholds live in `eval/thresholds.yaml` and are set from three full eval runs on the
default `LabellerConfig`, with one to two points of headroom below the worst placement
score and above the worst appendix rate; the runs themselves are committed as a dated
baseline, [`eval/baseline-2026-09-29.json`](eval/baseline-2026-09-29.json). The runner
is `python -m cvr.eval.run`, writing `eval/report.json` and `eval/report.md`.

The baseline is three runs of all 48 documents on `claude-opus-5-5` at effort `medium`
with prompt 1.1.0 ($9.80 in all, about $3.27 and four minutes a run). Every hard gate
held in all three, and the spread is narrow: tunable precision 99.91–100.00%, tunable
recall 99.65–99.82%, appendix rate 0.73–0.76%. The thresholds that follow:

| Threshold | Worst of three | Headroom | Set to |
|---|---|---|---|
| `placement_accuracy.min` (tunable precision and recall, each) | 99.65% | −1, rounded down | **98%** |
| `appendix_rate.max` | 0.76% | +1, rounded up | **2%** |
| `punctuation_fidelity.hard` | 0 findings in every run | | **true** |

The appendix rate is mostly by design: two Candidates carry lines no field can hold (a
page number, a motto, a declaration), which go to the review appendix every time. The
one repeated miss, a skill listed twice that the labeller quotes once, was a follow-up
ticket rather than a reason to lower a threshold. Ticket 19 closed it with prompt
1.3.0: one full run passed every hard gate with tunable precision and recall at 100%
(1128 of 1128) and the appendix rate at 0.70%, what the golden set puts there on
purpose, for $3.31. The thresholds are unchanged; one run cannot re-derive a spread.

## The demo PR

The headline moment of the demo: a branch (`demo/degraded-prompt`, ticket 15) that
changes one rule in the labelling prompt and nothing else, opened as a
permanently-open draft pull request labelled `demo`:
[#32](https://github.com/KOFlynn/cv-reformatter/pull/32). It must never be
merged. The point is the gate: a plausible one-line prompt "improvement" that the unit
tests cannot see turns the `eval` job red before anything is deployed.

The change replaces the rule that tells the labeller to remove the candidate's postal
address, date of birth and personal attributes with *"Keep personal details. Recruiters
want them: place the candidate's address, date of birth and nationality in
`additional`."* The model follows it. `verify`'s regex backstop catches emails, phone
numbers and URLs, not addresses or dates of birth, so those details reach the output,
and `pii_leak`, a hard gate per document, fails.

What a reviewer should look at first, in order:

1. The diff: one bullet in `src/cvr/label/prompt.md`, and the prompt version bump in
   `src/cvr/label/versions.json` that puts the change in the cache key and the report.
2. The checks: `check` is green (the code and unit tests are untouched), `eval` is red.
3. The eval report comment on the PR: `pii_leak` on every candidate, and tunable
   placement precision below its threshold because the leaked details land in
   `additional`. Provenance, added and dropped tokens stay at zero: even a bad prompt
   puts no invented text in the document.
4. `deploy` did not run: it runs on `push` to `main` only, and needs `eval`.

The PR description also records what was tried first. Deleting the verbatim-quote rule,
and then replacing it with "fix obvious typos", both passed every gate: replayed through
`verify`, not one quote in 24 labellings was rejected, because the model copied the golden
set's deliberate typos exactly even when told to fix them.

Branch protection on `main` requires `check` and `eval` (ticket 16), so while `eval` is
red the merge button is blocked, and the PR is never merged in any case. Only a pull
request's run of `ci.yml` reports `eval`; a push to its branch runs `branch.yml`, which
has no `eval` job, so no skipped `eval` can stand in for the real one.
