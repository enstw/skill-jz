---
name: flush
description: End-of-session project handoff and agent-memory drain. Use when the session is ending, context may be lost, work needs to continue on another machine, the user asks to save current project state, or the user says "clear memory" / "memory doesn't cross machines" / wants session memory moved into repo files. Decide what current progress, context, and project memory must be written into the repo; migrate every entry of the agent's machine-local memory store into repo files (mandatory — memory does not travel between machines) and clear the store only after the migrated content is committed; update the right project files; commit and push so the repo is enough to resume from.
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

The user is saying: this session is going down; preserve the useful project state, commit it, and push it so the next session or another machine can resume from the repo alone.

Principle: the repo is durable. Agent-private memory, transcripts, and scratch context are machine-local and temporary. Do not dump the transcript; extract only the state a future contributor needs.

**Memory drain is mandatory.** The agent's persistent per-project memory store lives on this machine only — it does not sync, so anything left in it is invisible to the next machine or agent. Flushing means what it means for a buffer: write it out, then empty it. Every memory entry must be migrated into a repo file, dropped with a stated reason, or surfaced to the user (step 3). Only transcripts and local caches stay untouched — this skill never deletes anything outside the memory store.

**Cost discipline — read this first.** You are invoked at end-of-session, when the context window is already large and every tool call re-sends all of it. Keep the run cheap:

- **Orient in one shot.** Use the single batched command in step 1 instead of many separate git calls.
- **Never re-read the full `git diff`.** You already know what changed this session — you did the work. `git diff --stat` (filenames + line counts) is enough to jog and confirm. Read a hunk only for a specific file whose change you genuinely can't recall.
- **Read only the file you will edit.** Don't open every candidate state doc to "have a look" — the step-1 listing tells you which exist; open the one you're writing to (Edit needs a prior Read), not the rest.
- **Read each memory entry exactly once.** Entries are short; the index line alone is not enough to migrate faithfully, but there is no reason to open an entry twice.
- **Batch git writes.** Stage and commit in one call; then push.

Flow: orient -> decide what matters -> drain memory -> update the repo -> commit/push -> clear memory -> report the handoff.

The same flow serves a memory-only request ("clear my memory"): steps 2 and 4 then have little or nothing to add, and the run is just drain -> commit -> clear -> report.

## 1. Orient

Run one batched command to gather everything at once (each sub-command already matches this skill's allow-list, so it stays auto-approved):

```
git rev-parse --show-toplevel 2>/dev/null; echo '--- status'; git status --short; echo '--- diffstat'; git diff --stat; echo '--- branch'; git branch --show-current; echo '--- remote'; git remote -v; echo '--- docs'; ls -d AGENTS.md CLAUDE.md PROGRESS.md STATUS.md TODO.md NOTES.md README.md docs 2>/dev/null
```

From that single output you have: repo root (empty => not a repo, ask before `git init`), the dirty/untracked set, what changed and by how much, the current branch, whether a remote exists, and which state docs already exist. Treat dirty files as possible in-flight work, not noise to overwrite. Only if a specific change is unclear from the diffstat, read that one file's hunk.

Then locate the persistent per-project memory store your runner announces in its context (for file-based memory: an index file plus one file per entry) and list it in one call — e.g. `ls <memory-dir>` — so step 3 knows how many entries exist. An absent store or an index with no entries means step 3 is a no-op.

## 2. Decide What To Preserve

Use judgment. Preserve what helps someone resume; skip ceremonial edits. Draw the content from what you did this session — not from re-reading the codebase.

Write down project-scoped state such as:

- Current goal, completed work, in-flight work, blockers, and the next useful step.
- Decisions, constraints, conventions, architecture notes, and commands that matter later.
- Test/build/verification results and known failures.
- Files touched or important uncommitted changes, when that context is not obvious from the diff.
- Open questions, follow-ups, and owner/action context.

Do not write user-personal or global facts into the repo unless the user explicitly says they belong there. If there is no meaningful new project state, no relevant working-tree change, and no memory entries to drain, say so and skip the commit.

## 3. Drain Agent Memory

Not optional. Read the index and every entry file in full (the index line is a summary; the body carries the why and how-to-apply that must not be lost). Then classify each entry and act:

- **Project-scoped** (working conventions, constraints, workflow rules, decisions, in-flight state): migrate into the repo's appropriate *existing* file per the routing in step 4. Match the target file's language, tone, and list conventions; convert relative dates to absolute; compress the wording but keep the why — a rule without its reason gets deleted by the next refactor.
- **Already recorded in the repo** or derivable from code/git history: drop it; note the existing location in the report.
- **Stale or wrong** — names a file, flag, branch, or fact that no longer exists (verify before concluding): drop it; note why.
- **User-personal or cross-project**: it does not belong in a project repo. Ask the user where it should live (a dotfiles/notes repo, keep in memory, or delete). Do not decide this silently, and do not write personal facts into the project repo. These entries stay in memory untouched until answered.

After migrating, confirm each migrated fact actually landed in its target file (re-read the section or grep for its key phrase). A migration you cannot point to in the repo did not happen — that entry is not eligible for clearing in step 6.

If the memory store is absent or empty, say so in the report and move on; do not create files or commits to record that nothing happened.

## 4. Update The Right Files

Prefer existing project files over new files. Create a new state file only when there is useful state and no existing place for it. Open only the file you're editing.

Common routing:

- `AGENTS.md` or equivalent: durable project conventions and how to work in the repo.
- `PROGRESS.md`, `STATUS.md`, or `NOTES.md`: current handoff state, recent progress, decisions, and blockers.
- `TODO.md` or issue tracker references: open actions and unresolved questions.
- `README.md`: user-facing usage, install, or project description updates.
- `docs/` or ADRs: design rationale future contributors need.

Keep the handoff concise, dated when useful, and AI-agnostic. Preserve unrelated sections. Do not create a progress file just to say nothing happened.

## 5. Commit And Push

Invoking `/flush` authorizes committing and pushing the state needed for handoff.

1. If the directory is not a git repo, ask before `git init` — and do not clear memory (step 6) until there is a durable destination the migrated content has been committed to.
1. Stage only files that should travel to the next machine. Do not use `git add -A` blindly. From the step-1 status you already know which files are unrelated work, secrets, generated artifacts, local config, or cache/output dirs — leave those unstaged and mention them in the final report; do not open them just to inspect.
1. Do not delete, clean, stash, reset, reformat, or otherwise tidy unrelated files unless the user explicitly asks for that separate cleanup.
1. Stage and commit in one batched call, e.g. `git add <paths> && git commit -m "docs: record handoff state"`. If both product changes and handoff docs exist, decide whether one commit or separate commits is clearer. Use a direct message such as `docs: record handoff state`, `checkpoint: save current project state`, or a project-specific summary.
1. Push:
   - If a remote exists, run `git push`. If upstream is missing, push with `-u origin <branch>`.
   - If no remote exists, ask before `gh repo create <name> --source=. --push`, including whether it should be private or public.
   - If auth fails, report the error and stop trying to fix credentials.

Push failures do not erase the handoff work; report what remains local.

## 6. Clear The Memory Store

Only after the commit from step 5 exists (a local commit is the durability bar — committed content survives a memory wipe even if the push is still pending):

1. Delete the entry files whose content was migrated and verified, or explicitly dropped in step 3.
1. Rewrite the index to its empty header (or to only the surviving entries).
1. Entries still awaiting a user decision (the personal/cross-project ones) stay in memory untouched — clearing them without an answer would destroy the only copy.

Hard guard: the only files this skill ever deletes are entry files inside the memory store. Never run `rm` outside the memory directory, and never delete the store's index file — rewrite it instead.

## 7. Final Report

Tell the user:

- Which files were updated and why.
- Each memory entry and its disposition: the repo file and section it moved to, why it was dropped, or what question is pending — and confirmation the store is now empty (or which entries remain and why).
- What was committed.
- Whether push succeeded or why it did not.
- Any remaining uncommitted changes.
- The shortest path for the next session: which file to read first and what the next action is.
