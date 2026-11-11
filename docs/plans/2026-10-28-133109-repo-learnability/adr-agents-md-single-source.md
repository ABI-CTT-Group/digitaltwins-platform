# Keep agent instructions in AGENTS.md, with one-line pointer files for other tools

- **Date:** 2026-10-28
- **Status:** Accepted

## Context

The team works on this repo with Claude Code, Codex, Gemini CLI and Antigravity, GitHub Copilot and Cursor. Each tool looks for its instructions in a different file:

- Codex and Cursor read `AGENTS.md`.
- Claude Code reads `CLAUDE.md`.
- Gemini CLI reads `GEMINI.md`, and Antigravity reads `.agents/rules/`.
- Copilot reads `.github/copilot-instructions.md`.

Until now only `AGENTS.md` and `.agents/rules/main.md` existed, and `AGENTS.md` covered process rules only. We are adding a repo map, commands, safety rules and cross-service couplings, so the content now matters, and copies would drift apart. A stale safety rule in one tool's file is worse than none.

## Alternatives Considered

### Option A: A full instructions file per tool
- Pros:
  - Each file can use its tool's own features and wording.
- Cons:
  - Four or more copies to keep in step. They will drift, and nothing would catch it.

### Option B: Symlink `CLAUDE.md` and the others to `AGENTS.md`
- Pros:
  - One copy of the content.
- Cons:
  - Symlinks check out as plain text files on Windows unless `core.symlinks` is on, and we ship a Windows/WSL demo guide.
  - Copilot's file lives in `.github/`, so a symlink there needs a relative target, and tool support for symlinked instruction files is uneven.

### Option C: `AGENTS.md` as the single source, with one-line pointer files
- `CLAUDE.md`, `GEMINI.md` and `.agents/rules/main.md` hold only `@AGENTS.md`, which those tools expand as an import.
- `.github/copilot-instructions.md` holds a one-line link to `AGENTS.md`, because Copilot has no import syntax.
- Services with their own rules (api, builder, portal, airflow) get a nested `AGENTS.md`, plus a `CLAUDE.md` pointer beside it.
- Pros:
  - One place to edit per scope.
  - Plain files that work on every OS.
  - Easy to check automatically.
- Cons:
  - Copilot relies on the agent following the link.
  - Tool-specific tips have to live in `AGENTS.md` too.

## Decision

Option C. `util/check_docs.py` (run by `make docs-check` and the CI `docs` job) enforces it:

- A pointer file may hold only its pointer, apart from headings and frontmatter.
- Every `CLAUDE.md` and `GEMINI.md` must have an `AGENTS.md` beside it.

Nested `AGENTS.md` files add only what's specific to their service and never repeat the root file.

## Consequences

- To change agent behaviour, edit an `AGENTS.md`. A change made in a pointer file fails `make docs-check`.
- A tool-specific tip goes in `AGENTS.md` under a heading that names the tool.
- Adding support for another tool means adding one more pointer file and teaching the checker its name.
- Copilot gets the instructions only if it follows the link. If that proves unreliable, the fallback is generating its file from `AGENTS.md`, not hand-editing it.
