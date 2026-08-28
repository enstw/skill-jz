---
name: flush
description: End-of-session project handoff and agent-memory drain. Use when the session is ending, context may be lost, work continues on another machine, or the user says "save project state", "clear memory", or "memory doesn't cross machines". Writes the state a future contributor needs — from this session and from the agent's machine-local memory store — into the repo, commits and pushes, then empties the memory store.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(pwd)
  - Bash(date)
  - Bash(git rev-parse --show-toplevel)
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git ls-files *)
  - Bash(git branch *)
  - Bash(git remote *)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git push)
  - Bash(git push *)
  - Bash(git init)
  - Bash(gh repo create *)
  - Bash(ls *)
  - Bash(find *)
  - Bash(grep *)
  - Bash(rm *)
---

# /flush - End-of-session handoff

The user is saying: this session is going down; put whatever the next session or machine needs into the repo, commit, push, and leave nothing behind that only this machine can see.

Principle: the repo is the only durable store. The agent's memory store, transcripts, and scratch context are machine-local and temporary. Flush means what it means for a buffer: write out, then empty. Do not dump the transcript — extract only the state a future contributor needs.

Cost: you run at end-of-session, when the context is already large and every tool call re-sends it. Orient with the single batched command below, and never re-read the full `git diff` — you did the work, `--stat` is enough to confirm. Open only the files you will edit.

Flow: orient -> collect (session state + memory entries) -> write -> commit/push -> clear memory -> report. A memory-only request ("clear my memory") is the same flow with an empty session-state half.

## 1. Orient

One batched command (every sub-command matches this skill's allow-list):

```
git rev-parse --show-toplevel 2>/dev/null; echo '--- status'; git status --short; echo '--- diffstat'; git diff --stat; echo '--- branch'; git branch --show-current; echo '--- remote'; git remote -v; echo '--- docs'; ls -d AGENTS.md CLAUDE.md PROGRESS.md STATUS.md TODO.md NOTES.md README.md docs 2>/dev/null; echo '--- memory'; ls <memory-dir> 2>/dev/null
```

`<memory-dir>` is the persistent per-project memory store your runner announces in its context (for file-based memory: an index file plus one file per entry). From this one output you have: repo root (empty => not a repo; ask before `git init`), the dirty/untracked set, what changed and by how much, branch, remote, which state docs exist, and how many memory entries there are. Treat dirty files as possible in-flight work, not noise.

## 2. Collect

Two sources feed the same triage. Use judgment: preserve what helps someone resume, skip ceremonial edits.

**From this session** — draw on what you did, not on re-reading the codebase: current goal, completed / in-flight work, blockers, the next useful step; decisions, constraints, conventions, commands that matter later; test/build results and known failures; important uncommitted changes when the diff alone doesn't explain them; open questions and follow-ups.

**From the memory store** — normally empty, since durable facts are supposed to go into repo files in the first place; a non-empty store means some runner wrote memory automatically or an older machine left residue. Either way, drain it: read the index and every entry body once (the index line is a summary; the body carries the why), then place each entry:

- **Project-scoped** (conventions, constraints, decisions, in-flight state): goes into the repo in step 3. Convert relative dates to absolute; compress the wording but keep the why — a rule without its reason gets deleted by the next refactor.
- **Already in the repo** or derivable from code/git history: drop; note where it already lives.
- **Stale or wrong** — names a file, flag, branch, or fact that no longer exists (verify before concluding): drop; note why.
- **User-personal or cross-project**: never into the project repo. If the runner's context names a home for such facts (a personal context file, a global rules file), write it there. Otherwise leave the entry in memory and list it in the report — do not block the handoff on a question.

If both sources are empty and the working tree has no relevant change, say so and stop; do not create files or commits to record that nothing happened.

## 3. Write

Prefer existing project files; create a new one only when useful state has no existing home. Match each file's language, tone, and list conventions; preserve unrelated sections; keep it concise, dated when useful, and AI-agnostic.

- `AGENTS.md` or equivalent: durable conventions and how to work in the repo.
- `PROGRESS.md`, `STATUS.md`, or `NOTES.md`: current handoff state, recent progress, decisions, blockers.
- `TODO.md` or issue tracker references: open actions and unresolved questions.
- `README.md`: user-facing usage, install, or description updates.
- `docs/` or ADRs: design rationale future contributors need.

## 4. Commit And Push

Invoking `/flush` authorizes committing and pushing the handoff.

1. Not a git repo: ask before `git init`. Until a commit exists somewhere durable, step 5 does not run.
1. Stage only what should travel. No blind `git add -A`: the step-1 status already shows which files are unrelated work, secrets, generated artifacts, or local config — leave those unstaged and mention them in the report. Do not clean, stash, reset, or tidy unrelated files.
1. Stage and commit in one call, e.g. `git add <paths> && git commit -m "docs: record handoff state"`. Split into two commits only when product changes and handoff docs are clearer apart.
1. Push. Missing upstream: `git push -u origin <branch>`. No remote: ask before `gh repo create <name> --source=. --push`, including private vs public. Auth failure: report it and stop — do not try to fix credentials.

A push failure does not undo the handoff; report what remains local.

## 5. Clear The Memory Store

Gate: the step-4 commit exists locally. That is the durability bar — committed content survives a memory wipe even if the push is still pending.

1. Delete the entry files that were migrated or dropped in step 2.
1. Rewrite the index to its empty header, or to only the entries that remain.
1. Entries left in place on purpose (personal/cross-project with no home) stay untouched.

Hard guard: the only files this skill ever deletes are entry files inside the memory store. Never `rm` outside that directory; never delete the index — rewrite it.

## 6. Report

- Files updated and why; what was committed; whether the push succeeded.
- Each memory entry's disposition (target file, or why dropped, or left in place and why), and confirmation the store is now empty.
- Anything left uncommitted on purpose.
- The shortest path for the next session: which file to read first and what the next action is.
