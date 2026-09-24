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
of orchestration, not of code. Today, `parse`, `label`, `verify` and `transform` exist
as packages under `src/cvr/`; `render`, the pipeline function that wires all five nodes
together, and the `api`/`graph`/`mcp` wrappers do not exist yet (tickets 05, 06, 11
respectively; `graph` and `mcp` are Phase 2 and 3).

## Decisions

Nine decisions, one per §12 of the brief, each linking the ADR that holds the detail.
Written early, while the reasoning from the design sessions is fresh; see ticket 16 for
the end-of-phase revision once every number below exists.

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
**Still to come:** only Anthropic is wired up today (`cvr.label`); Azure OpenAI arrives
as a second provider in Phase 2, through a managed identity rather than a stored key,
and the comparison and the choice are recorded in the ADR that follows it once real
numbers exist. Phase 2 has not yet been broken into tickets, so there is no ticket
number to link yet. What already exists to make that comparison mechanical — the chat
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

**Still to come.** The plan: Azure Container Apps on the consumption plan, scaled to
zero when idle; GitHub Actions authenticates to Azure via an OIDC federated credential,
so no Azure secret is ever stored in GitHub; and, in Phase 2, the running service
reaches the LLM through a managed identity rather than a key. The alternative rejected
by this plan is a stored Azure service-principal secret in GitHub and an always-on
plan, neither of which the free-grant budget or the "no secret in GitHub" evidence goal
would survive. Provisioning, the `deploy` job and the ADR that records the resource
names and the federated credential's subject all land in ticket 14, which writes
ADR-0010; that file does not exist yet, so it is not linked here until it does. This
section is updated from plan to fact when ticket 14 lands.

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
half of this — infrastructure as code, a container registry with managed-identity
pull — is recorded as part of ADR-0010, written in ticket 14; that ADR does not exist
yet, so it is referenced here as forthcoming rather than linked. The `.docx`-only and
review-by-exception halves are already recorded: [ADR-0003](docs/adr/0003-docx-only.md),
[ADR-0004](docs/adr/0004-review-by-exception.md).

## Running it

```
uv sync                                 # install, using the Python 3.12 pinned in .python-version
uv run pytest -q                        # unit tests
uv run ruff check .                     # lint
uv run ruff format --check .            # format check
uv run python -m cvr.golden.generate    # regenerate fixtures/generated/ after a Candidate or Layout change
uv run python -m cvr.template.build     # rebuild templates/fictitious_recruitment.docx after a build.py change
```

The fuller command reference — dependency management, running one test directory,
useful `pytest` flags — is [`docs/development.md`](docs/development.md); CI
(`.github/workflows/ci.yml`) runs exactly the sync, lint, format-check and test steps
above on every push and pull request.

There is no single command yet that runs a CV through the whole pipeline: the function
that wires `parse` → `label` → `verify` → `transform` → `render` together
(`reformat(source_bytes, labeller) -> (output_bytes, Run)`) is ticket 06, `render`
itself is ticket 05, the FastAPI service is ticket 11, and the Dockerfile is ticket 12.
Until then, `parse`, `verify`, `transform` and the real `label` node can each be
exercised directly through their own package and its tests.

## The eval gate

`src/cvr/eval/` already holds nine metrics as pure functions with sorted findings:
`added_tokens`, `dropped_tokens`, `provenance_violations`, `pii_leak`, `image_leak` and
`ordering_report` are **hard gates** — they must come back exactly zero (or, for
ordering, exactly correct) or CI fails regardless of any threshold.
`placement_accuracy` and `appendix_rate` are **thresholds**: a minimum and a maximum set
from evidence rather than picked in advance. `punctuation_fidelity` starts as a reported
metric and is promoted to a hard gate only once three baseline runs come back clean on
it, so the promotion is earned rather than assumed.

Thresholds live in `eval/thresholds.yaml` and are set from three full eval runs on the
default `LabellerConfig`, with one to two points of headroom below the worst placement
score and above the worst appendix rate; the runs themselves are committed as a dated
baseline at `eval/baseline-YYYY-MM-DD.json`. **Neither file exists yet.** The runner
that produces them (`python -m cvr.eval.run`, writing `eval/report.json` and
`eval/report.md`) is ticket 09; the baseline run and the thresholds themselves are
ticket 10. This section is updated with the real thresholds and a link to the baseline
file once ticket 10 lands.

## The demo PR

The headline moment of the demo: a branch (`demo/degraded-prompt`, ticket 15) that
deletes the verbatim-quote rule from the labelling prompt and nothing else, opened as a
permanently-open draft pull request labelled `demo`. Because `provenance_violations` is
a hard gate, that one-line prompt change is expected to turn the `eval` job red —
`check` stays green, `deploy` never runs, and branch protection makes the PR
mechanically impossible to merge. **Not yet built:** the branch, the PR and the three
`--no-cache` runs that prove the failure before the demo relies on it are ticket 15,
which itself is blocked on provisioning and deployment (ticket 14). A reviewer looking
at this repository today should start with `docs/project-brief.md` §11 for the intended
demo script, and with the decisions above for the reasoning; once ticket 15 lands, this
section links the PR directly and names the CI run and the provenance-violation count to
look at first.
