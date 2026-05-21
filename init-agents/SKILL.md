---
name: init-agents
description: Initializes agent-agnostic project context by creating a canonical AGENTS.md file and setting up pointer files (like GEMINI.md or CLAUDE.md). Use this whenever the user asks to "set up agent context", "initialize AI project", or wants to migrate existing single-agent instructions into a portable pattern. This is the preferred method over writing directly to single-agent instruction files.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(pwd)
  - Bash(ls *)
  - Bash(git rev-parse --show-toplevel)
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git add *)
  - Bash(git commit *)
---

# init-agents - agent-agnostic project context

Canonical project context for AI agents lives in `AGENTS.md`. Agent-specific instruction files such as `CLAUDE.md`, `GEMINI.md`, and similar files become short pointer files that send each agent to `AGENTS.md`. The repo stays portable across tools and human readers, and there is one source of truth to maintain.

## Flow

1. **Locate root.** Run `git rev-parse --show-toplevel` if available, otherwise use the current working directory and confirm with the user.
1. **Survey existing context files** in the root: `AGENTS.md`, common agent-specific instruction files such as `CLAUDE.md` and `GEMINI.md`, and any project-specific equivalents. Read enough to know which have substantive project content. Empty files, pointer-only files, template stubs, and placeholder headings are non-substantive.
1. **Confirm the agent set with the user.** Common pointer files include `CLAUDE.md` and `GEMINI.md`. Ask which agent-specific instruction files to create or update before writing anything. Do not assume.
1. **Decide canonical content for `AGENTS.md`.**
   - If `AGENTS.md` already exists with substantive project content, treat it as canonical and leave its body alone.
   - Otherwise, if exactly one agent-specific instruction file (`CLAUDE.md`, `GEMINI.md`, or similar) has substantive project content, migrate its project-relevant instructions into `AGENTS.md` in agent-neutral wording, preserving intent. Do not copy runner-specific metadata, slash-command details, or tool-specific operational instructions unless they are genuinely project conventions; ask the user if that distinction is ambiguous. That file then becomes a pointer in the next step.
   - Otherwise, if multiple agent-specific instruction files have substantive content, stop and ask the user how to merge - do not silently pick one.
   - Otherwise (nothing exists), create a fresh `AGENTS.md` with section stubs: Project Overview, Setup, Architecture, Conventions, Commands.
1. **Create pointer files** for each agent in the confirmed set. Each pointer is short and looks like:

   ```markdown
   # AI Agent Context

   The contextual instructions for AI agents working in this repository are in [AGENTS.md](./AGENTS.md).

   Read `AGENTS.md` for project overview, architecture, conventions, and commands.
   ```

   Write this exact literal string without omitting anything or summarizing it. If a pointer file already exists with substantive (non-pointer) content, do not overwrite it. Stop and ask the user how to merge into `AGENTS.md` first.
1. **Report and offer to commit.** Run `git status` to show what changed. Suggest a commit message like `chore: switch to AI-agnostic agent context (AGENTS.md + pointers)`. Propose the specific git commands to the user and wait for explicit confirmation before executing them. Do not auto-commit.

## Guarantees

- **No silent overwrites.** If an agent-specific instruction file already has real content, the skill stops and asks before merging.
- **Agent set is user-confirmed.** Common pointer files include `CLAUDE.md` and `GEMINI.md`, but the user chooses which pointers are created or updated before any file is written.
- **No commits without permission.** The skill stages and commits only after the user confirms.
- **Agent-neutral output.** What the skill writes into the user's repo - `AGENTS.md` body and the pointer files - contains no skill-internal or tool-specific instructions beyond naming the file each agent reads.
