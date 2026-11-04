# 07: Live from Claude Desktop, and the docs

**What to build:** the brief's Phase 3 exit criteria: `reformat_cv` working from Claude Desktop and documented in the README. The maintainer makes the live call, and the docs and status are brought up to date.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] The README has a Phase 3 section covering what the tool does and the Claude Desktop config snippet with no secret. It names the config's location for both the standard install and the Microsoft Store package, and gives `uv run --env-file .env` with `--directory`. It covers the Workspace and the output naming, and explains why stdio, why the result has no text and why there is no `list_templates`
- [ ] Maintainer: `c04__single-column.docx` copied into the Workspace and reformatted from Claude Desktop. The Tool result, the run id and the trace are noted on this ticket, and the output is opened in Word
- [ ] A screenshot or GIF of that call is in the README
- [ ] CLAUDE.md's status, package list, layout and commands, `docs/development.md` and brief §10's Phase 3 boxes are updated
- [ ] A release note in this feature's folder; Phase 3 merged in one PR, with its eval report on the PR
