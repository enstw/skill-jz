---
name: clear-memory
description: Migrate the agent's persistent per-project memory into the repo's own files, then clear the memory store. Use when the user says "clear memory", "memory doesn't cross machines", wants session memory moved into repo files, or wants an empty memory store without losing what it knows. Every memory entry either lands in an appropriate repo file, is dropped as duplicate/stale with a note, or is surfaced to the user when it doesn't belong in this repo; memory is deleted only after the migrated content is committed. The explicit memory-cleanup counterpart to /flush, which never wipes memory on its own.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(pwd)
  - Bash(date)
  - Bash(ls *)
  - Bash(find *)
  - Bash(grep *)
  - Bash(rm *)
  - Bash(git rev-parse *)
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git branch *)
  - Bash(git remote *)
  - Bash(git fetch *)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git push)
  - Bash(git push *)
---

# /clear-memory - Migrate agent memory into the repo, then clear it

The user is saying: my agent's session memory is machine-local and does not travel; move anything worth keeping into the repo's own files, then empty the memory so the repo is the single durable source of truth.

Principle: the repo is durable and portable; agent memory is machine-local and agent-private. Every memory entry must end up in exactly one of three places — written into an appropriate repo file, dropped with a stated reason (duplicate or stale), or surfaced to the user when it does not belong in this repo. Nothing is deleted silently, and memory is cleared only after the migrated content is committed.

This is the separate cleanup routine that `/flush` explicitly refuses to perform. Pair them: `/flush` records session state into the repo without touching memory; `/clear-memory` drains the memory store itself.

Hard guard: the only files this skill ever deletes are entry files inside the memory store. Never run `rm` outside the memory directory, and never delete the store's index file — rewrite it to its empty header instead.

Flow: locate the store -> read every entry -> triage and migrate -> verify -> commit/push -> clear -> report.

## 1. Locate The Memory Store

Find the persistent per-project memory location your runner announces in its context (for file-based memory: an index file plus one file per memory). If the store does not exist or the index lists no entries, report "memory is already empty" and stop — do not create files or commits to record that nothing happened.

If the current directory is not a git repo, stop and ask where the memory content should go: there is no durable destination to migrate into, and clearing without migrating would lose it.

## 2. Read Every Entry

Read the index AND each entry file in full. The index line is a one-sentence summary; the entry body carries the why and how-to-apply details that must not be lost in migration. Do not migrate from index lines alone.

## 3. Triage And Migrate

Classify each entry and act:

- **Project-scoped** (working conventions, constraints, workflow rules, decisions, in-flight state): migrate into the repo's appropriate *existing* file. Durable working rules go to `AGENTS.md` or its equivalent conventions section; in-flight/handoff state goes to `PROGRESS.md`, `STATUS.md`, or `TODO.md`; design rationale goes to `docs/` or ADRs. Create a new file only when useful content has no existing home. Match the target file's language, tone, and list conventions; convert relative dates to absolute; compress the wording but keep the why — a rule without its reason gets deleted by the next refactor.
- **Already recorded in the repo** or derivable from code/git history: drop it; note the existing location in the report.
- **Stale or wrong** — names a file, flag, branch, or fact that no longer exists (verify before concluding): drop it; note why.
- **User-personal or cross-project**: it does not belong in a project repo. Ask the user where it should live (a dotfiles/notes repo, keep in memory, or delete). Do not decide this one silently, and do not write personal facts into the project repo.

## 4. Verify The Migration

For each migrated entry, confirm the fact actually landed in the target file (re-read the section or grep for its key phrase). A migration you cannot point to in the repo did not happen — that entry is not eligible for clearing.

## 5. Commit And Push

Invoking `/clear-memory` authorizes committing the migrated docs. Follow the target repo's own documented workflow: if it mandates local gates, checks, or a PR flow before landing changes, honor that; otherwise stage only the files this migration touched and commit directly with a message like `docs: migrate agent session memory into repo`. Push if a remote exists; a push failure does not undo the migration — report what remains local.

The durability bar for clearing is a local commit: content that is committed survives the machine's memory being wiped even if the push is pending.

## 6. Clear The Store

Only after the commit exists:

1. Delete the entry files whose content was migrated or explicitly dropped.
1. Rewrite the index to its empty header.
1. Entries still awaiting a user decision (the personal/cross-project ones) stay in memory untouched — clearing them without an answer would destroy the only copy.

## 7. Final Report

Tell the user:

- Each memory entry and its disposition: the repo file and section it moved to, or why it was dropped, or what question is pending.
- What was committed, and whether the push succeeded.
- Confirmation that the memory store is now empty (or which entries remain and why).
