# CV Reformatter — Build Spec

**Owner:** Kieran O'Flynn
**Spec date:** 11 September 2026
**Status:** Phase 0 (spec, template, golden set). Nothing built yet.

---

## 1. What this is, and why it exists

A **portfolio demo** built to support AI engineering and AI architecture job applications. It is not a product. It will never have real users, never process real CVs, and never be sold. It **is** deployed, so the CI eval gate blocks a real deployment.

**The job it does:** a candidate CV (.docx) goes in. The same content comes out in a fictional recruitment agency's branded Word template, **Fictitious Recruitment**. Sections are reordered, experience and education are sorted in reverse chronological order, personal contact details are removed and dates are normalised. **Nothing is reworded.** Every word in the output traces to the source CV or to the template's own fixed text.

**Origin story (for the README):** recruitment agencies commonly pay someone to reformat candidate CVs into a standard branded template by hand. The work is manual and repetitive, and it has a hard correctness rule: never change the candidate's words.

**Framing:** not an impressive AI thing. An unimpressive AI thing done impressively. The paved road is the product: tests, an eval gate, containerisation, CI/CD, deployment, tracing, and a written decision record.

### What it must evidence

Each piece of the build exists to close a named gap seen across AI engineering JDs. Do not add pieces that are not on this list.

| Gap | Closed by | Phase |
|---|---|---|
| Agentic framework, hands-on | LangGraph workflow with a bounded retry loop | 2 |
| MCP server built from scratch | MCP server exposing `reformat_cv` | 3 |
| Docker | Dockerfile, image deployed to Azure Container Apps | 1 |
| Eval and observability tooling | Golden-set eval gate in CI, Langfuse tracing | 1, 2 |
| OAuth 2.0 / OIDC, Entra ID | GitHub Actions to Azure via OIDC federated credential; managed identity from Container Apps to Azure OpenAI | 1, 2 |
| Vector DB / RAG | **Not covered, deliberately.** See section 3 | — |

---

## 2. Design principle: the LLM labels, code transforms

**This is the decision the whole design hangs on.**

The LLM never writes output text. It only says *which piece of source text belongs in which field.* Everything else is deterministic code: removals, date normalisation, ordering and rendering.

Mechanism:

1. The parser breaks the source document into numbered **blocks** (paragraphs, table cells, text box paragraphs, header and footer paragraphs), each with a stable `block_id`.
2. The LLM returns assignments of the form `{field, block_id, quote}`, where `quote` is text copied from that block.
3. The verifier checks that each `quote` is an exact substring of its block (after whitespace normalisation). **The output always uses the located source slice, never the LLM's string.** A quote that doesn't match is rejected.
4. Rejected or unassigned source text is retried (Phase 2) and then sent to the review appendix.

Result: **added text is impossible by construction** rather than something tested for after the fact. The eval still checks it, as a guard against bugs in the code.

---

## 3. Scope

### In

- .docx input only
- One output template: Fictitious Recruitment
- Synthetic CVs generated from fixtures (section 7)
- FastAPI service, Docker, GitHub Actions, Azure Container Apps
- Two LLM providers, Anthropic and Azure OpenAI, compared by the eval
- LangGraph orchestration, Langfuse tracing, MCP server (Phases 2 and 3)

### Out, and why

| Out | Reason |
|---|---|
| PDF input | Roughly doubles parsing work. Possible later phase |
| Real CVs or any real personal data | Demo only. Synthetic data keeps the repo public-safe |
| Candidate scoring, ranking, filtering, matching or search | Would make it a high-risk AI system under **EU AI Act Annex III, point 4** ("analyse and filter job applications, and to evaluate candidates"). Staying out is a stated design decision for the ADR. It is also why gap 6 (RAG) is not closed here: the obvious RAG feature is candidate search |
| Generated summaries, rewording, spelling or grammar fixes | Breaks the core invariant |
| Review UI or interactive human-in-the-loop | Review is **by exception**, via the appendix. Describe it that way, never as HITL |
| Multiple templates or template editor | Not needed to evidence anything |
| Anything from or resembling Kieran's employer's data, code or systems | Hard rule |

---

## 4. Output template: Fictitious Recruitment

### Section order

| # | Section | Content |
|---|---|---|
| 1 | Header | Agency branding plus the candidate's **full name** |
| 2 | Profile | Verbatim if the source has one. **Omitted if it doesn't. Never generated** |
| 3 | Key skills | Verbatim, as a list |
| 4 | Education | Reverse chronological. Institution, qualification, dates, and any detail lines verbatim |
| 5 | Experience | Reverse chronological. Each role has job title, employer, location, dates and verbatim bullets |
| 6 | Certifications | Verbatim |
| 7 | Additional information | Known minor categories: languages, interests, volunteering, publications, awards |
| 8 | Footer | "References available on request" (the template's fixed text) |
| 9 | **Review appendix** | Only present if something was not placed. See below |

### Removal rules

Each removal has a named rule ID, and every removal is logged.

| Rule ID | Removes |
|---|---|
| `RM_PHONE` | Phone numbers |
| `RM_EMAIL` | Email addresses |
| `RM_ADDRESS` | Home or postal address |
| `RM_URL` | LinkedIn and personal URLs |
| `RM_PHOTO` | Images in the source |
| `RM_DOB` | Date of birth or age |
| `RM_PERSONAL` | Nationality, marital status |
| `RM_REFEREE` | Referee names and contact details |
| `RM_HEADING` | The source's own section headings (the template supplies its own) |

Removal is defence in depth: the LLM labels these spans, and a deterministic regex backstop catches emails, phone numbers and URLs whatever the LLM did.

### Never changed

Spelling, capitalisation, punctuation, wording and bullet text. **Typos stay in.** Bullet glyphs and whitespace may be normalised.

### Dates

Code normalises dates to **MM/YYYY**.

- Current role (`Present`, `Current`, `to date`, `now`) becomes `Present`
- Year only (`2019`) stays `2019`. **Never invent a month**
- Unparseable dates (`Summer 2020`) stay verbatim and sort by year where one can be extracted
- Accept common source formats: `Jan 2020`, `January 2020`, `01/2020`, `1/2020`, `2020-01`, `Jan '20`

### Ordering

Experience and education sort by end date descending, with `Present` first, then by start date descending. Undated entries go last, in source order.

### Review appendix

If any source text is not placed after verification (and retries, from Phase 2), the document gets a final section headed by a **large, bold, red banner**:

> **TEXT NOT PLACED — NEEDS HUMAN REVIEW**

The unplaced text follows verbatim, in source order. **The job always completes.** Nothing hangs or waits for a person.

---

## 5. Data model (outline)

Pydantic v2. Treat this as a starting point, not a final schema.

```
SourceBlock      block_id, text, location (body|table|textbox|header|footer), order
Assignment       field, block_id, quote            # LLM output
Span             block_id, start, end, text        # verified slice of source

ReformattedCV
  name: Span
  profile: list[Span]            # empty if absent
  skills: list[Span]
  education: list[EducationEntry]
  experience: list[ExperienceEntry]
  certifications: list[Span]
  additional: list[Span]
  removed: list[Removal]         # span + rule_id
  unplaced: list[Span]           # goes to review appendix

ExperienceEntry  title, employer, location?, start?, end?, bullets: list[Span]
EducationEntry   institution, qualification, start?, end?, details: list[Span]
DateValue        raw: Span, month?: int, year?: int, is_present: bool
```

---

## 6. Architecture

```
.docx ──► parse ──► label (LLM) ──► verify ──┬──► transform ──► render ──► .docx
                                   ▲         │   (remove, dates,  (docxtpl)
                                   └─ retry ◄┘    sort)
                                  (≤ N, Phase 2)   unplaced ──► appendix
```

| Component | Responsibility | Notes |
|---|---|---|
| `parse` | .docx to ordered `SourceBlock`s | python-docx covers paragraphs, tables, headers and footers. **Text boxes need raw XML** (`w:txbxContent` via lxml), because python-docx doesn't expose them. Keep reading order stable |
| `label` | Blocks to `Assignment`s | Provider-agnostic, through LangChain chat model interfaces with structured output. Model and provider set by env var. Prompt and schema version recorded on every run |
| `verify` | Assignments to verified `Span`s, and unplaced text | Exact-substring check, coverage check (every source character is assigned, removed or unplaced) |
| `transform` | Removal rules, regex PII backstop, date normalisation, ordering | Pure functions, fully unit tested, no LLM |
| `render` | Fills `templates/fictitious_recruitment.docx` via docxtpl | The template is a real Word file with Jinja tags. It includes the appendix block with the red banner |
| `graph` | LangGraph state machine for the above | Phase 2. Phase 1 is a plain function pipeline with the same node boundaries, so the swap is mechanical |
| `api` | FastAPI: `POST /reformat` (upload .docx, return .docx), `GET /health` | Structured JSON logging. Returns a run ID that matches the trace |
| `mcp` | MCP server exposing `reformat_cv` (and `list_templates`) | Phase 3. A thin wrapper over the same pipeline. Demo it from Claude Desktop |

---

## 7. Golden set: generated, not downloaded

**The fixture JSON is the expected answer.** That makes the golden set cheap to produce and exact.

1. **Candidates:** 10–15 fictional people in `fixtures/candidates/*.json`, matching the `ReformattedCV` shape plus the PII fields that must be removed. An LLM may help draft them, but they are reviewed and committed as static fixtures. No real people.
2. **Layouts:** 3–4 generator scripts in `fixtures/layouts/` render each candidate into a messy source .docx:
   - single column, conventional
   - two column via a table
   - contact block and skills in **text boxes**
   - contact details in the **header or footer**, and education at the bottom
3. **Traps to include across the set:** typos that must survive; mixed date formats (section 4); year-only and unparseable dates; experience out of chronological order; unusual sections (volunteering, publications); a source with no profile; PII in odd places (in a footer, inside a bullet); and one or two deliberately unplaceable fragments to exercise the appendix.
4. Generated source .docx files are committed, so eval runs are reproducible without rerunning the generator.

Result: roughly 40–60 source documents with exact expected output.

---

## 8. Eval and the gate

`eval/run_eval.py` runs the pipeline over the golden set and writes `eval/report.json` plus a markdown summary, with each metric broken down per layout and per provider.

| Metric | How | Gate |
|---|---|---|
| **Added text** | Output tokens minus template text, minus normalised dates mapped back to their source, must be a sub-multiset of source tokens | **= 0, hard** |
| **Unaccounted dropped text** | Source tokens not found in the output, the removal log or the appendix | **= 0, hard** |
| **PII leak** | Fixture PII values (exact and normalised, e.g. phone without spaces) must not appear anywhere in the output | **= 0, hard** |
| **Placement accuracy** | Field-level match of structured output against fixture JSON, whitespace-normalised | ≥ threshold, set after the first baseline run |
| **Ordering** | Experience and education order match the rule | **100%** |
| **Appendix rate** | Appendix tokens as a share of source content tokens | ≤ threshold, set after baseline |

Thresholds live in `eval/thresholds.yaml`. **CI fails, and deployment is blocked, if any hard gate is breached or any threshold is missed.**

**Provider comparison:** the eval runs against both Anthropic and Azure OpenAI (Phase 2 onwards). The ADR records which provider was chosen and the numbers behind the choice.

**Cost control:** the LLM eval runs on pull requests and on main, not on every push. Unit tests run on every push.

---

## 9. CI/CD and deployment

**GitHub Actions**

| Trigger | Jobs |
|---|---|
| Every push | lint (ruff), unit tests (pytest) |
| Pull request to main | lint, unit tests, **eval gate** |
| Merge to main | lint, unit tests, eval gate, build image, push to registry, deploy to Azure Container Apps |

- **GitHub to Azure uses an OIDC federated credential** (`azure/login`). No Azure secret is stored in GitHub.
- LLM keys are stored as GitHub secrets for the eval, and as Container Apps secrets for runtime.
- **Phase 2:** Container Apps reaches Azure OpenAI with a **managed identity**, so there is no key for that path.

**Azure Container Apps:** consumption plan, min replicas 0 (scale to zero), health probe on `/health`, structured logs to Log Analytics, config through environment variables. The target is to stay inside the free monthly grant. Kill anything that starts costing money.

**The demo PR:** keep a branch that deliberately degrades the prompt. Opening a PR from it must turn CI red and block the deploy. This is the headline moment of the demo.

---

## 10. Phases and exit criteria

Every phase ends in a shippable state. **Phase 1 alone is valid standalone evidence.** If later phases stall, stop at Phase 1 rather than let scope creep block everything.

### Phase 0: spec, template, golden set
- [ ] `templates/fictitious_recruitment.docx` designed in Word, with docxtpl tags and the appendix block
- [ ] 10–15 candidate fixtures
- [ ] 3–4 layout generators; source .docx files generated and committed
- [ ] Eval metric functions written and unit tested against hand-made cases (no LLM yet)

### Phase 1: end-to-end lifecycle
- [ ] parse, label (single pass, Anthropic), verify, transform, render, working on the golden set
- [ ] Unit tests for parse, verify, transform and render
- [ ] Eval gate running in GitHub Actions, thresholds set from the baseline
- [ ] Dockerfile; image runs locally under Docker Desktop
- [ ] Deployed to Azure Container Apps through Actions with OIDC
- [ ] README written as an ADR (section 12)
- [ ] Demo PR proven to block a deploy

### Phase 2: agentic workflow, observability, second provider
- [ ] Pipeline moved onto LangGraph, with a retry loop for rejected or unplaced spans (max N, default 2) before the appendix
- [ ] Langfuse tracing on every run, with the run ID linked from API logs
- [ ] Azure OpenAI added as a second provider through managed identity
- [ ] Eval report compares providers; choice recorded in the ADR

### Phase 3: MCP
- [ ] MCP server exposing `reformat_cv`, working from Claude Desktop
- [ ] Documented in the README

---

## 11. Interview demo (about 10 minutes)

1. The problem and the invariant: never change the candidate's words
2. Live: upload a messy CV to the deployed endpoint and get the branded .docx back
3. The appendix case: a CV with an unplaceable fragment, and the red banner
4. The trace: every step, with the LLM's labels and the verifier's rejections
5. The eval report: hard gates at zero, placement accuracy by layout and by provider
6. **The demo PR: the degraded prompt turns CI red and the deploy is blocked**
7. The ADR: the key decisions and what would change at scale

---

## 12. ADR: decisions to record in the README

1. The LLM labels and code transforms, so added text is impossible by construction
2. A generated golden set instead of downloaded CVs: exact ground truth, clean licensing, no real people
3. .docx only for the first build
4. Review by exception via the appendix; no interactive HITL, and why
5. Provider chosen by eval results, not by preference
6. No scoring, filtering or matching, which keeps it out of EU AI Act Annex III high-risk
7. Container Apps scaled to zero; OIDC for CI; managed identity at runtime
8. Why no RAG: nothing in the problem needs it, and the obvious feature would breach decision 6
9. What changes at scale: PDF input, multiple templates, a review queue, data residency and a DPA for real CVs

---

## 13. Working rules for Claude Code in this repo

- **Never let an LLM produce output text.** Any change that routes LLM-generated strings into the rendered document is a defect.
- Keep `transform`, `verify` and eval metrics as pure functions with unit tests. No LLM calls in unit tests.
- **Synthetic data only.** Never add real CVs, real names or real contact details.
- Do not add features outside section 3. If something seems necessary, stop and ask.
- Any change to the prompt, schema or model must be followed by an eval run, and the report diff shown.
- Small, reviewable commits. Explain the reasoning in PR descriptions, because they are part of the evidence.
- Keep the Phase 1 pipeline's node boundaries identical to the LangGraph nodes planned for Phase 2.

### Environment

- Kieran's machine: Windows 11, Docker Desktop with WSL2. Local Python is 3.14. **Pin the container and CI to Python 3.12** unless every dependency is confirmed on a newer version.
- Dependency management with `uv` (proposed; change if preferred).

### Suggested layout

```
cv-reformatter/
  SPEC.md
  CLAUDE.md                  # can simply contain: @SPEC.md
  README.md                  # written as the ADR
  src/cvr/{parse,label,verify,transform,render,graph,api,mcp}/
  templates/fictitious_recruitment.docx
  fixtures/candidates/*.json
  fixtures/layouts/*.py
  fixtures/generated/*.docx
  eval/{run_eval.py,thresholds.yaml,report.json}
  tests/
  Dockerfile
  .github/workflows/ci.yml
```

---

## 14. Open items

| # | Item | Default until decided |
|---|---|---|
| 1 | Keep **Additional information** (section 7) for known minor categories, or send everything that isn't a core section to the appendix? | Keep it. Otherwise nearly every CV gets a red banner and the appendix stops meaning anything |
| 2 | Placement and appendix thresholds | Set from the Phase 1 baseline |
| 3 | Final golden-set size | 12 candidates × 4 layouts |
| 4 | Retry count N | 2 |
| 5 | Container registry: GHCR or ACR | GHCR (free) |
| 6 | Langfuse: cloud free tier or self-hosted | Cloud free tier, if its terms still allow this use |
| 7 | Entra-protected endpoint via Container Apps built-in auth | Only if it fits naturally. Don't force it |
