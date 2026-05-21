---
name: sync
description: Push local commits to the remote when it's safe to do so. Use when the user says "sync this repo", "/sync", "push my changes", or wants a quick check of git sync state. Lightweight counterpart to /flush — does not decide what to preserve, does not write docs, does not commit. Only pushes already-committed work, fast-forwards when the remote is ahead, and warns about uncommitted/untracked files. If the current directory is a parent of multiple git repos (e.g. a workspace folder), runs the same sync on each child repo and reports per repo.
user-invocable: true
allowed-tools:
  - Bash(pwd)
  - Bash(ls *)
  - Bash(git rev-parse *)
  - Bash(git status *)
  - Bash(git branch *)
  - Bash(git remote *)
  - Bash(git fetch *)
  - Bash(git rev-list *)
  - Bash(git push)
  - Bash(git push *)
  - Bash(git pull --ff-only*)
  - Bash(git init)
  - Bash(gh repo create *)
---

# /sync - Push local commits when it's safe

The user is saying: move my already-committed work between local and the remote, and tell me anything that isn't ready to travel.

Principle: sync only moves committed history. It never commits, never resolves divergence, never touches uncommitted work, and never tries to fix auth. If a step needs judgment, stop and report.

This is the lightweight counterpart to `/flush`. Use `/flush` when the agent should decide what state matters and write it into the repo. Use `/sync` when the user has already committed what they want and just wants the remote to catch up.

Flow: detect repo (single or workspace-of-repos) -> for each repo, gather state -> act on the (ahead, behind, dirty) tuple -> report.

## 1. Detect Repo

1. Run `git rev-parse --show-toplevel` in the current directory.
1. **If it succeeds:** the current directory is inside a git repo. Run steps 2–5 once for that repo.
1. **If it fails:** the current directory is not itself a git repo. Check whether it's a workspace folder containing repo subfolders:
   - List immediate child directories and treat each one as a candidate repo if `<child>/.git` exists (a directory for normal repos, a file for submodules/worktrees). Skip hidden dirs and obvious non-project directories (`node_modules`, `venv`, `.venv`, `__pycache__`, `dist`, `build`, `target`).
   - **If one or more child repos are found:** enter workspace mode. List the discovered repos to the user, then run steps 2–5 inside each one (use `cd <child> && git ...` or `git -C <child> ...`). Produce a per-repo report and a short aggregate summary at the end (X synced, Y already up to date, Z had warnings, W skipped).
   - **If no child repos are found:** tell the user the current directory is not a git repo and not a workspace of repos. Ask whether to run `git init` here (and optionally `gh repo create` after, asking public vs private). Whatever they answer, exit — a freshly initialized repo has no commits or remote state to sync; the user can run `/sync` again later.

Do not recurse past immediate children by default. Nested repos (submodules inside a project, vendored trees) should be synced from their own parent or explicitly, not as a side effect of `/sync` at the workspace root. If the user wants deeper recursion, they can ask.

## 2. Gather State

1. `git fetch --quiet` so remote-tracking refs are current. If the fetch fails (no remote, auth error), record the error and continue with the local-only picture; do not retry credentials.
1. `git status --short` and split the output into untracked vs modified/staged paths.
1. `git rev-parse --abbrev-ref HEAD` for the current branch.
1. Check whether an upstream exists with `git rev-parse --abbrev-ref @{u}` (it can fail; that's fine).
1. If an upstream exists, get the counts with `git rev-list --left-right --count HEAD...@{u}` — the left number is local-ahead, the right is local-behind.

## 3. Act On The (Ahead, Behind, Dirty) Tuple

Pick exactly one branch:

- **No upstream configured.** If a remote (`origin`) exists, push with `git push -u origin <branch>`. If no remote exists, report "no remote configured" and stop — `/sync` does not create remotes on its own (offer `gh repo create` only on initial `git init`, step 1).
- **Up to date (0 ahead, 0 behind).** Nothing to push or pull. If the tree is dirty, add the warning from step 4. Done.
- **Ahead only (N ahead, 0 behind).** Run `git push`. If the tree is dirty, follow with the warning from step 4 so the user knows the dirty files were not synced. Done.
- **Behind only (0 ahead, N behind), clean tree.** Run `git pull --ff-only`. Report what came down. Done.
- **Behind only (0 ahead, N behind), dirty tree.** Do not pull. A fast-forward can still surprise the user when there are uncommitted local changes. Report the situation and suggest the user stash or finish the in-flight work, then re-run `/sync`.
- **Diverged (N ahead, M behind).** Report both counts and stop. `/sync` does not merge, rebase, or force-push. The user resolves this manually.

If a push or pull fails (auth, hook rejection, non-fast-forward), report the exact error and stop. Do not retry, do not adjust credentials, do not switch transports.

## 4. Dirty-Tree Warning

When the working tree has untracked or uncommitted files, emit a warning that:

1. Lists the affected paths (cap at the first ~10 and append `... and K more` if longer).
1. Separates untracked from modified/staged for clarity.
1. States explicitly: these files were not synced. Suggest `/flush` (if the user wants the agent to decide what to record and commit) or a manual commit (if the user already knows what should travel).

The warning is informational; it does not block a push that was otherwise safe.

## 5. Final Report

Tell the user, in this order:

1. Branch and upstream, with the post-action ahead/behind counts.
1. What `/sync` actually did: pushed, fast-forwarded, or nothing.
1. The dirty-tree warning, if any.
1. A single "what to do next" line only when action is required (commit, pull manually, set an upstream, configure a remote, resolve divergence). When state is clean and synced, omit this line.

In workspace mode, emit one such block per child repo (prefixed with the repo's folder name) and finish with a one-line aggregate: `N repos: A pushed, B fast-forwarded, C already in sync, D with warnings, E stopped (diverged/auth/etc)`.

## What `/sync` Does Not Do

- Never runs `git add`, `git commit`, `git stash`, `git reset`, `git rebase`, `git merge`, or any force-push.
- Never wipes caches, transcripts, or agent memory.
- Never edits credential helpers or retries auth on its own.
- Does not replace `/flush`. Pair them: `/flush` records project state and commits; `/sync` pushes the result.
