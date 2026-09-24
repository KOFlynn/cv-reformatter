# 08: README as ADR

**What to build:** The README a visitor reads first when the repo goes public, written as the architecture decision record the brief's §12 asks for, while the reasoning from the design sessions is fresh. Nine sections, one per §12 item, each a short paragraph stating the decision, the alternative rejected and the consequence, linking the ADR file that holds the detail: (1) the LLM labels and code transforms (ADR-0001, 0007, 0009); (2) a generated golden set (ADR-0002); (3) .docx only (ADR-0003); (4) review by exception via the appendix, no HITL, and why a runs endpoint would be half a review queue (ADR-0004, 0009); (5) provider chosen by eval results, which Phase 2 will fill in with numbers; (6) no scoring, filtering or matching, keeping it out of EU AI Act Annex III (ADR-0005); (7) Container Apps scaled to zero, OIDC for CI, managed identity at runtime, written now as the plan and confirmed by ticket 14 (ADR-0010 when it lands); (8) why no RAG (ADR-0005); (9) what changes at scale: PDF input, multiple templates, a review queue, data residency and a DPA, infrastructure as code, ACR with managed identity. Above the nine: what the project is, what it evidences, and the one-paragraph pipeline with the diagram. Below: how to run it, how the eval gate works, what the demo PR shows. Revised at the end of the phase in ticket 16 once every number exists.

**Blocked by:** 07 (The real labeller)

**Status:** done

- [x] README opens with what this is, what it is not (no real users, no real CVs), and the design invariant in one sentence
- [x] Nine §12 sections present, each linking at least one ADR file; items 7 and 5 say explicitly what is still to come and which ticket brings it
- [x] The pipeline diagram from `CLAUDE.md` reproduced with the node names matching the packages
- [x] Commands section matches `docs/development.md` and the real `python -m` entry points
- [x] The eval section explains hard gates versus thresholds and links the thresholds file and the baseline location (even if the baseline does not yet exist, the path is stated)
- [x] No real names, contact details, or employer references; no claims about numbers not yet measured

## Comments

### 2026-09-24: built, in review (branch `phase-1/08-readme-as-adr`)

**What was built.** `README.md`, at the repo root, not existing before this ticket.
Opening section: what the project is (with the brief's origin story in one short
paragraph), what it is not (portfolio demo, no real users, no real CVs, but deployed so
a real gate blocks a real deploy), the invariant in one sentence, and a "what this
evidences" table drawn from brief §1 (gap, closed-by, phase — no measured numbers, just
the mapping). Then the brief's pipeline diagram, reproduced verbatim from `CLAUDE.md`,
with a one-paragraph walk through `parse` → `label` → `verify` → `transform` → `render`
that names which packages exist today (`parse`, `label`, `verify`, `transform`) and
which don't yet (`render` ticket 05, the pipeline function ticket 06, `api` ticket 11,
`graph`/`mcp` Phase 2/3). Nine `## Decisions` subsections, one per brief §12 item, each a
short paragraph naming the decision, the alternative rejected and the consequence, and
linking at least one ADR under `docs/adr/`. Then `## Running it` (the `docs/development.md`
commands, plus an explicit statement that no single command runs the pipeline
end-to-end yet), `## The eval gate` (hard gates vs. thresholds, `eval/thresholds.yaml`
and `eval/baseline-YYYY-MM-DD.json` named as paths that don't exist yet, tickets 09/10
named as what creates them) and `## The demo PR` (what `demo/degraded-prompt`, ticket
15, will show once it exists).

**Decisions beyond the ticket text.**

- **Item 5's "which ticket brings it" is answered as "Phase 2, not yet ticketed."** The
  ticket's own wording for item 5 ("provider chosen by eval results, which Phase 2 will
  fill in with numbers") gives a phase, not a ticket number, and Phase 2 has not been
  cut into tickets yet (only Phase 1's 01–16 exist under `.scratch/phase-1/issues/`), so
  there is nothing to link. I still linked ADR-0009 from item 5, since it's what makes
  the provider swap mechanical (`init_chat_model` against the same schema and verifier)
  even though the comparison itself hasn't run.
- **Item 9 also treated as partly forward-looking, against ADR-0010.** The ticket text
  only names items 5 and 7 as needing explicit "still to come" wording, but item 9
  ("what changes at scale") overlaps the deployment half of ADR-0010 (infrastructure as
  code, a managed-identity registry pull — see the spec's own ADR list, "0010:
  deployment: ... what changes at scale"), which doesn't exist yet either. I split item
  9: the `.docx`-only and review-by-exception halves link ADR-0003 and ADR-0004 (which
  exist), and the deployment half is named as forthcoming via ADR-0010/ticket 14,
  worded the same way as item 7 rather than linked.
- **Items 6 and 8 link the same ADR (0005) twice**, once per decision, since the brief's
  own §12 states them as two decisions ("no scoring... " and "why no RAG") but ADR-0005
  is one file that already makes both points together. Linking it twice, with a note on
  the second that it's the same file, seemed more honest than inventing two ADRs where
  the design record only wrote one.
- **No cost, latency or eval-score numbers anywhere**, per the ticket's hard constraint.
  ADR-0009 itself states the spec's estimated per-run cost ($7/$3); the README
  deliberately does not repeat that figure, since it was never measured against this
  build and the ticket bars "numbers not yet measured."
- **Verified every markdown link resolves** (`docs/adr/0001` through `0009` that are
  actually linked, `docs/development.md`, `docs/project-brief.md`) by listing every link
  target in the file and confirming each path exists; `ADR-0010`, `eval/thresholds.yaml`
  and `eval/baseline-YYYY-MM-DD.json` are named in plain text, not as markdown links,
  since none of the three exists yet.
- **Ran, but did not commit, a template rebuild.** `uv run python -m cvr.template.build`
  produces a `templates/fictitious_recruitment.docx` that differs byte-for-byte from the
  committed one on every run (`docx_text.all_text` output is identical; the bytes are
  not — python-docx appears to embed something non-deterministic, e.g. an RSID or
  timestamp). This matches `docs/development.md`'s own wording, which promises
  byte-stability for `cvr.golden.generate` only, not for `cvr.template.build` (whose
  entry only promises the *text and tags* match, which `tests/template/test_build.py`
  is what actually asserts). Confirmed `uv run python -m cvr.golden.generate` leaves
  `git status` clean, as documented, and reverted the template rebuild's binary diff
  with `git checkout -- templates/fictitious_recruitment.docx` rather than committing
  it, since this ticket doesn't touch `src/` or `templates/`.
- Ran `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, and the full
  `uv run pytest -q` (1677 passed, 1 skipped — the label spike, no `ANTHROPIC_API_KEY`
  in this environment) to confirm nothing in the repo regressed; none of these touch
  `README.md` since ruff doesn't lint markdown.
- Invoked the `code-review` skill against `main` (Standards and Spec sub-agents run in
  parallel).

**Code review findings and what was done.**

*Spec axis*: no missing or partial requirements, no scope creep beyond the ticket's own
"what it is / what it evidences / pipeline" prose requirement, no incorrect
implementations. One note, not a violation: item 5 names a phase ("Phase 2") rather
than a ticket number for "which ticket brings it", since Phase 2 has no tickets cut yet
and the ticket text itself only names a phase for item 5. Left as is.

*Standards axis*: no hard violations of `CLAUDE.md`, the ADRs' prose style or
`docs/development.md`'s command conventions — all links verified to resolve, `eval/*`
paths and ADR-0010 confirmed to still not exist and to be written as plain text, not
links. Three judgement-call smells raised, all fixed:
- **Duplicated prose**: the invariant was stated twice, near-verbatim, in `## The
  invariant` and in decision 1. Decision 1 now reads "This is the invariant above,
  restated as a decision with an alternative on record" instead of re-deriving the
  mechanism in the same words.
- **A "what this is not" section that pivoted to an affirmation mid-paragraph** ("It
  **is** deployed...") without a transition. Reworded to "That does not make the CI
  gate optional: the service is still deployed, so a real gate blocks a real
  deployment," so the sentence argues from the heading instead of against it.
- A borderline note on rhetorical phrasing ("rather than being a slide", "not a hope")
  sitting slightly softer than `CLAUDE.md`'s terse register, though the reviewer judged
  it within the ADRs' own house style. Left as is; the "slide" phrase was removed
  incidentally by the fix above, "not a hope" was kept.

Re-ran `uv run ruff format --check .` and `uv run pytest -q` after the edits: unchanged
(1677 passed, 1 skipped), since the edits are prose only.

PR: none yet; not opened per the task brief (the parent integrates this branch).



### 2026-09-24: maintainer review, on the release branch

- **Template builder byte-stability**: `CLAUDE.md` claimed both generators were byte-stable. Diffing a fresh build against the committed template showed every part inside identical and only the zip entry timestamps (the build time) different, so a rebuild on another day differs in bytes. `CLAUDE.md` now says so (commit `8d94428`); the builder itself is unchanged.
- **`render` counted as built** (commit `8225b6d`): the README was written alongside ticket 05 and listed `render` as future work; merged together, it exists.
- **Item 5 naming Phase 2, not a ticket**: accepted until Phase 2 is cut into tickets.

Release PR: #23.
