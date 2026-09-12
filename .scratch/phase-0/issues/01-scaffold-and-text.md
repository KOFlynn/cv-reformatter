# 01: Scaffold, CI, and canonicalise/tokenise

**What to build:** A `uv`-managed Python 3.12 project on a `main` branch with lint and unit tests running green in GitHub Actions, and the one text module every later slice imports: `canonicalise` (NFC → explicit confusable table → whitespace collapse → trim) and `tokenise` (canonicalise → split → strip punctuation from token edges only → drop empties). After this ticket a developer can clone, `uv sync`, and run tests; and `tokenise("Software Engineer, Acme Ltd, 2019 - 2022")` returns `Software Engineer Acme Ltd 2019 2022` with `C++`, `O'Flynn`, `node.js`, `2019-2022` left intact.

Housekeeping comes first: rename `master` to `main` locally and on GitHub; commit the pending project instructions, agent docs, glossary, ADRs and `.scratch/` as the first commit on `main`; then branch.

**Blocked by:** None (can start immediately)

**Status:** in-review

- [x] Default branch is `main` locally and on GitHub; the pending docs are its first commit
- [x] `pyproject.toml` via `uv`: runtime deps pydantic, python-docx, docxtpl, lxml; dev deps pytest, ruff; `requires-python >= 3.12`; `.python-version` pins 3.12
- [x] `cvr` package exists with empty `text`, `models`, `eval`, `golden` homes so the dependency direction (eval → text/models, golden → text/models, never sideways) is visible
- [x] ruff (defaults + import sorting) and pytest configured; both pass locally
- [x] One GitHub Actions workflow runs sync, lint, tests on push and pull request; green on this PR
- [x] The generated eval report path is gitignored
- [x] `cvr.text` exposes the confusable table as data, `canonicalise`, `tokenise`; standard library only
- [x] Tests: one case per confusable-table row; edge stripping examples; lone bullet glyphs vanish; case and typos untouched; `½` and `™` are not rewritten (NFC-not-NFKC guard)
- [x] Project instructions no longer say "nothing is built yet" and list the real commands

## Comments

**2026-09-12 (Claude Code):** Implemented on branch `phase-0/01-scaffold-and-text`, PR #1 (https://github.com/KOFlynn/cv-reformatter/pull/1), CI green. Default branch switched to `main` on GitHub; `origin/master` is not yet deleted (needs `git push origin --delete master`). Two-axis review found no hard violations; follow-ups applied in 4eab39d (ADR-0007 records the "punctuation = Unicode P*, not symbols" choice; `py.typed` dropped). CI also runs `ruff format --check` and syncs with `--locked`, which the ticket did not ask for; both are easy to drop if unwanted.
