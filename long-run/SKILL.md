---
name: long-run
description: >-
  Work autonomously through a project's work queue until it is finished or
  genuinely blocked, instead of stopping at every milestone. Use when the user
  says "long run", "keep going until done", "close the remaining tickets",
  "don't stop", "stop for reason only", "長跑", "做完再停", "有問題自己決定" —
  or when you are about to end a turn with "want me to continue?", "shall I
  keep going or pause?", or "this is a good boundary" while the goal is known
  and unblocked items remain. Defines the only legitimate stop reasons, how to
  skip past a blocked item, how to settle choice points without asking (Jev via
  jev-decide when available), and a checkpoint-not-pause rhythm. Ships a Stop
  hook that refuses an end-of-turn without a valid stop code.
---

# long-run — work the queue until it is done or genuinely blocked

Agents given a goal and a ticket list still stop early, and the stop always *sounds* reasonable. Observed in one session that had "long run, stop for reason only" in writing:

- a milestone landed, the agent wrote a summary, and the summary read like an ending;
- "this is a good boundary for fresh context" — context anxiety, while compaction handles long sessions;
- "want me to place the authorized order?" — permission already granted hours earlier;
- one path blocked (a VM needing a GUI click) halted the run while other items were unblocked;
- "the rest is incremental" — the agent re-scoped the goal on its own.

Instructions alone did not prevent any of these. This skill therefore has two layers: a **contract** (below, runner-neutral) and an **enforcement adapter** that makes ending a turn cost something (see *Enforcement*).

## Start of a run

1. **Find the goal and the queue.** The project's `AGENTS.md` should name both — look for a *Goal* section and a `Work queue:` line (a file such as `docs/tickets.md` / `TODO.md`, or an issue tracker). If it doesn't, use the obvious file (`TODO.md`, `docs/tickets.md`, open issues); if none exists, write the queue yourself from the goal into `TODO.md` before starting. Ask the user at most once, and only when the goal itself is unknown.
1. **Collect standing authorizations.** Read `AGENTS.md` and the conversation for pre-granted actions (e.g. "all live transactions on the test account are authorized", "you may power the VM on/off"). These are the answer to every "may I…?" you would otherwise ask. If the project has none recorded, record the ones the user gives now under an *Authorizations* heading in `AGENTS.md`.
1. **Arm the run.** If `.long-run` already exists at the project root (the arm hook wrote it from the user's prompt), it's armed. Otherwise write it: one or two lines naming the goal and the queue, kept out of version control via `.git/info/exclude` (don't edit the project's `.gitignore` for it). The enforcement adapter keys off this file.
1. **Pre-empt permission denials.** Read the project's `.claude/settings.json` `permissions.allow`; if the run will drive a tool that a sandbox or classifier has denied before (VM driver, file staging to a share, test runner), add those patterns now — see *Enforcement*.
1. **State the plan in two lines**: the goal, the topmost unblocked item. Then start — no confirmation question.

## The loop

1. **Take the topmost unblocked item.** "Next" always means that; its choice needs no permission.
1. **Do it, verify it** (tests, live check, whatever the project's done-definition is).
1. **Checkpoint, don't pause.** Commit, update the queue item's status, push if that is the project's convention. A milestone is a checkpoint, never a stopping point — write the summary into the queue/commit, not into a closing message.
1. **Repeat.**

### A choice point (two or more reasonable ways forward)

Settle it without the user:

- If the `jev-decide` skill and its credential are available, run it. **PROCEED → act.** **ESCALATE → park**: record the options and the trade-off on the queue item as *blocked: needs user decision*, and move to the next item.
- Otherwise decide yourself and write a one-line rationale on the queue item, so the user can overturn it later. Prefer the reversible option.

Only a decision that is irreversible *and* not covered by a standing authorization goes to the user — and even then, park it and continue elsewhere; batch it into the final stop report.

### A blocked item

Blocked means **skip, not stop**. Record the concrete blocker on the item ("VM start times out — needs someone to dismiss the UTM dialog", "needs a funded account to get a fill"), then take the next unblocked item. Before calling something blocked, check that the project's own problem-solving order (docs → existing captures/logs → analysis → live experiment, or whatever `AGENTS.md` prescribes) is exhausted. A tool the harness refuses (a permission classifier, a sandbox) is a blocker for *that action only*: name it once, don't reword and retry, move on.

Items that need a human are batched and done last, so one interruption covers them all.

## When stopping is legitimate

Stop only when one of these is true for **every** remaining item — not just the current one:

| Code | Meaning |
|---|---|
| `queue-empty` | Every item is done, or blocked with a named blocker. |
| `needs-human` | Every remaining item needs a human's hands or knowledge (a GUI dialog, a physical device, a fact only they know, an ESCALATEd decision). |
| `needs-authorization` | Every remaining item needs an irreversible or outward-facing action no standing authorization covers. |
| `user-request` | The user asked to pause or stop. |

**Not stop reasons:** a milestone; having written a summary; the session being long; "a good boundary for fresh context"; "the remaining work is incremental / lower value" (the user sets scope, not you); any question answerable from the queue, `AGENTS.md`, or an earlier authorization; one blocked item while others are unblocked; "want me to continue?".

### The stop report

End the final message with the report, and its **last line** exactly:

```
LONG-RUN STOP: <code>
```

The report lists: what was completed this run (with commit refs), each remaining item with its specific blocker, and — for `needs-human` / `needs-authorization` — the batched asks, each phrased so a one-word reply unblocks it. On `queue-empty` or `user-request`, delete `.long-run`. On `needs-human` / `needs-authorization`, keep it: the run resumes when the user answers.

A user message mid-run (a question, a correction) is answered and then the run continues — unless it asked to pause, in which case end with `LONG-RUN STOP: user-request`.

## Enforcement

The contract is runner-neutral; the adapters are not. Two Claude Code hooks in `hooks/`, installed once per machine by the `init-machine` skill, inert in every project without a `.long-run` flag:

- **`long-run-arm.sh`** (`UserPromptSubmit`) — when the prompt contains "long run" / "長跑" (not the idiom "in the long run"), it writes the `.long-run` flag itself, git-excludes it, and injects one line telling the agent the run is armed. Enforcement therefore never depends on the agent arming it against itself; the *Arm the run* step above is the fallback when the phrase wasn't used.
- **`long-run-guard.sh`** (`Stop`) — while a fresh `.long-run` exists, refuses an end-of-turn whose final message lacks a valid `LONG-RUN STOP:` line and re-injects the contract as the reason, so it survives compaction.

Safety valves in the guard:

- **Fail-open** — no `jq`, no flag, unreadable transcript → the stop is allowed.
- **Idle brake** — `LONG_RUN_MAX_IDLE` (default 3) refusals in a row with no new tool call → allowed; the agent is talking, not working.
- **Cost ceiling** — `LONG_RUN_MAX_BLOCKS` (default 40) refusals in total per session → allowed; a run that keeps circling has a hard end.
- **Staleness** — a flag untouched for `LONG_RUN_TTL` seconds (default 12 h) is ignored, so an abandoned run never traps a later session.
- `queue-empty` / `user-request` delete the flag. `user-request` is self-certified — the cheapest exit, kept on purpose so a run can always be ended.

**What the guard cannot fix: permission denials.** A sandbox/classifier refusal ends the action for that turn regardless of any hook, and a run that hits one every few minutes stalls no matter how good the contract is. The fix is upstream: put the project's known-safe command patterns (its VM driver, package manager, test runner, its staging directory) in `permissions.allow` of the project's tracked `.claude/settings.json`, so those commands never reach the classifier. Do this at the start of the first long run in a project, from the denials seen so far.

Other runners get the contract without the hooks until an adapter exists for them; where a runner can re-prompt on a timer, re-issuing "continue the long run" after each turn is the crude equivalent.
