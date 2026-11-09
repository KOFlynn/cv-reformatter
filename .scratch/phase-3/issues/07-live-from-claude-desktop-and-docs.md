# 07: Live from Claude Desktop, and the docs

**What to build:** the brief's Phase 3 exit criteria: `reformat_cv` working from Claude Desktop and documented in the README. The maintainer makes the live call, and the docs and status are brought up to date.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] The README has a Phase 3 section covering what the tool does and the Claude Desktop config snippet with no secret. It names the config's location for both the standard install and the Microsoft Store package, and gives `uv run --env-file .env` with `--directory`. It covers the Workspace and the output naming, and explains why stdio, why the result has no text and why there is no `list_templates`
- [ ] Maintainer: `c04__single-column.docx` copied into the Workspace and reformatted from Claude Desktop. The Tool result, the run id and the trace are noted on this ticket, and the output is opened in Word
- [ ] A screenshot or GIF of that call is in the README
- [ ] CLAUDE.md's status, package list, layout and commands, `docs/development.md` and brief §10's Phase 3 boxes are updated
- [ ] A release note in this feature's folder; Phase 3 merged in one PR, with its eval report on the PR

## Live proof steps

For the maintainer, Windows and Git Bash, from `C:\Git\cv-reformatter` on the Phase 3 branch (boxes 2 and 3; the README's Phase 3 section has a TODO comment where the screenshot goes).

1. `uv sync`, then `mkdir -p ~/cvr-workspace && cp fixtures/generated/c04__single-column.docx ~/cvr-workspace/`.
2. Write `C:\Git\cv-reformatter\.env` (gitignored; never commit or paste it): `ANTHROPIC_API_KEY=<key>`, `CVR_MCP_ROOT='<the Windows path of ~/cvr-workspace, e.g. C:\Users\<you>\cvr-workspace>'` (single-quoted: unquoted, uv reads the backslashes as escapes and loads none of the file), and optionally `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` (so the call is traced).
3. Add to `claude_desktop_config.json` (keep any other servers; backslashes doubled):
   ```json
   {"mcpServers": {"cv-reformatter": {"command": "uv", "args": ["run", "--directory", "C:\\Git\\cv-reformatter", "--env-file", ".env", "python", "-m", "cvr.mcp"]}}}
   ```
   If Claude Desktop cannot start `uv`, use the full path from `where uv` as `command`.
4. The file is `%APPDATA%\Claude\claude_desktop_config.json` (standard install) or, for the Microsoft Store package on this machine (found 2026-11-09), `%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude_desktop_config.json` (its logs in `logs\` beside it). Edit it with Claude Desktop quit.
5. Quit Claude Desktop from the system tray (not just the window), start it again, and check `cv-reformatter` shows under Settings, Developer and `reformat_cv` appears in the tools list. If the server fails to start, read the MCP log in that `logs` folder (`mcp-server-cv-reformatter.log` or `mcp.log`); a `Failed to parse environment file` warning means an unquoted Windows path in `.env`; the log's last line `cvr.mcp: ...` with exit status 2 means the Workspace or `CVR_RETRY_MAX` is wrong.
6. In a new chat type: `Use reformat_cv to reformat c04__single-column.docx.` and approve the tool call. One real model call, about $0.07.
7. Note on this ticket: the Tool result as shown (fields only, no CV text), the run id, the Langfuse trace link (trace id = run id, tags `env=local`, `surface=mcp`, Environment `local`), and that `c04__single-column-reformatted-<run id[:8]>.docx` in the Workspace opened in Word (with the appendix banner if `unplaced` is not 0).
8. Screenshot or screen-record the chat with the tool call expanded (no key, nothing personal in the path). Save as `docs/images/mcp-reformat-cv.png` (or `.gif`), then replace the TODO comment and the "pending" line in the README's Phase 3 section with `![reformat_cv from Claude Desktop](docs/images/mcp-reformat-cv.png)` and a caption with the run id.
9. Tick boxes 2 and 3 only once that evidence is on the ticket.
