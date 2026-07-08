---
name: flush
description: End-of-session project handoff. Use when the session is ending, context may be lost, work needs to continue on another machine, or the user asks to save current project state. Decide what current progress, context, and project memory must be written into the repo; update the right project files; commit and push so the repo is enough to resume from.
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
---

# /flush - End-of-session handoff

The user is saying: this session is going down; preserve the useful project state, commit it, and push it so the next session or another machine can resume from the repo alone.

Principle: the repo is durable. Agent-private memory, transcripts, and scratch context are temporary. Do not dump the transcript; extract only the state a future contributor needs.

This skill is a handoff, not a cache deletion routine. Do not wipe agent memory, transcripts, or local caches unless the user explicitly asks for that separate cleanup.

**Cost discipline — read this first.** You are invoked at end-of-session, when the context window is already large and every tool call re-sends all of it. Keep the run cheap:

- **Orient in one shot.** Use the single batched command in step 1 instead of many separate git calls.
- **Never re-read the full `git diff`.** You already know what changed this session — you did the work. `git diff --stat` (filenames + line counts) is enough to jog and confirm. Read a hunk only for a specific file whose change you genuinely can't recall.
- **Read only the file you will edit.** Don't open every candidate state doc to "have a look" — the step-1 listing tells you which exist; open the one you're writing to (Edit needs a prior Read), not the rest.
- **Batch git writes.** Stage and commit in one call; then push.

Flow: orient -> decide what matters -> update the repo -> commit/push -> report the handoff.

## 1. Orient

Run one batched command to gather everything at once (each sub-command already matches this skill's allow-list, so it stays auto-approved):

```
git rev-parse --show-toplevel 2>/dev/null; echo '--- status'; git status --short; echo '--- diffstat'; git diff --stat; echo '--- branch'; git branch --show-current; echo '--- remote'; git remote -v; echo '--- docs'; ls -d AGENTS.md CLAUDE.md PROGRESS.md STATUS.md TODO.md NOTES.md README.md docs 2>/dev/null
```

From that single output you have: repo root (empty => not a repo, ask before `git init`), the dirty/untracked set, what changed and by how much, the current branch, whether a remote exists, and which state docs already exist. Treat dirty files as possible in-flight work, not noise to overwrite. Only if a specific change is unclear from the diffstat, read that one file's hunk.

## 2. Decide What To Preserve

Use judgment. Preserve what helps someone resume; skip ceremonial edits. Draw the content from what you did this session — not from re-reading the codebase.

Write down project-scoped state such as:

- Current goal, completed work, in-flight work, blockers, and the next useful step.
- Decisions, constraints, conventions, architecture notes, and commands that matter later.
- Test/build/verification results and known failures.
- Files touched or important uncommitted changes, when that context is not obvious from the diff.
- Open questions, follow-ups, and owner/action context.
- Project-specific memory from the running agent that is not already in the repo.

Do not write user-personal or global facts into the repo unless the user explicitly says they belong there. If there is no meaningful new project state and no relevant working-tree change, say so and skip the commit.

## 3. Update The Right Files

Prefer existing project files over new files. Create a new state file only when there is useful state and no existing place for it. Open only the file you're editing.

Common routing:

- `AGENTS.md` or equivalent: durable project conventions and how to work in the repo.
- `PROGRESS.md`, `STATUS.md`, or `NOTES.md`: current handoff state, recent progress, decisions, and blockers.
- `TODO.md` or issue tracker references: open actions and unresolved questions.
- `README.md`: user-facing usage, install, or project description updates.
- `docs/` or ADRs: design rationale future contributors need.

Keep the handoff concise, dated when useful, and AI-agnostic. Preserve unrelated sections. Do not create a progress file just to say nothing happened.

## 4. Commit And Push

Invoking `/flush` authorizes committing and pushing the state needed for handoff.

1. If the directory is not a git repo, ask before `git init`.
1. Stage only files that should travel to the next machine. Do not use `git add -A` blindly. From the step-1 status you already know which files are unrelated work, secrets, generated artifacts, local config, or cache/output dirs — leave those unstaged and mention them in the final report; do not open them just to inspect.
1. Do not delete, clean, stash, reset, reformat, or otherwise tidy unrelated files unless the user explicitly asks for that separate cleanup.
1. Stage and commit in one batched call, e.g. `git add <paths> && git commit -m "docs: record handoff state"`. If both product changes and handoff docs exist, decide whether one commit or separate commits is clearer. Use a direct message such as `docs: record handoff state`, `checkpoint: save current project state`, or a project-specific summary.
1. Push:
   - If a remote exists, run `git push`. If upstream is missing, push with `-u origin <branch>`.
   - If no remote exists, ask before `gh repo create <name> --source=. --push`, including whether it should be private or public.
   - If auth fails, report the error and stop trying to fix credentials.

Push failures do not erase the handoff work; report what remains local.

## 5. Final Report

Tell the user:

- Which files were updated and why.
- What was committed.
- Whether push succeeded or why it did not.
- Any remaining uncommitted changes.
- The shortest path for the next session: which file to read first and what the next action is.
