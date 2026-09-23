---
name: init-machine
description: >-
  Set up Claude Code's global environment on a machine (macOS or Ubuntu) from
  the canonical copies bundled here — lease-based keep-awake hooks,
  cross-platform notification chimes, and the long-run stop guard. Use when the user says "set up this
  machine", "初始化這台機器", asks for the keep-awake or sound hooks — or
  whenever you notice this machine's ~/.claude is missing them (no
  keepawake/chime hooks in settings.json); that absence means an uninitialized
  machine, so offer to run this skill. (An empty auto-memory is NOT the
  signal — the user's standing rules keep memory empty on purpose.)
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# init-machine — Claude Code global environment

Replicates one user-level Claude Code environment across machines. The files bundled in this skill are **canonical**; whatever sits in `~/.claude` on any machine is a replica. Unlike the rest of this collection, this skill is Claude-Code-specific by nature — its entire subject is the runner's global config.

## What gets installed

| Bundled file | Target | Purpose |
|---|---|---|
| `hooks/keepawake.sh` | `~/.claude/hooks/keepawake.sh` | Lease-based sleep inhibition while the agent works |
| `hooks/chime.sh` | `~/.claude/hooks/chime.sh` | Stop / Notification sounds, platform-appropriate player |
| `../long-run/hooks/long-run-guard.sh` (sibling skill) | `~/.claude/hooks/long-run-guard.sh` | Refuses a premature end-of-turn during a long run; inert elsewhere |
| — (settings fragment below) | `~/.claude/settings.json` | Wires the hooks into Claude Code events |

**Out of scope:** the global `~/.claude/CLAUDE.md` standing-rules file travels through the user's own note-sync channel, not this skill. Don't create or edit it here.

How the pieces behave:

- **keepawake.sh** — every hook firing restarts a bounded inhibitor (`caffeinate -is -t` on macOS, `systemd-inhibit … sleep` on Linux), so the machine stays awake until `CLAUDE_KEEPAWAKE_LEASE` seconds (default 720) past the last agent activity, then the inhibition self-expires. Idle at the prompt → machine may sleep. No unbounded resident processes. Headless Linux without `systemd-inhibit` → silent no-op.
- **long-run-guard.sh** — the Stop-hook adapter of the `long-run` skill (canon lives there, not here). Does nothing unless the project root holds a fresh `.long-run` flag; then an end-of-turn without a valid `LONG-RUN STOP: <code>` line is refused so the agent continues. Needs `jq`; without it the guard fails open (never blocks).
- **chime.sh** — takes `stop` or `notify`; prefers the user's own `~/.claude/sounds/<event>.wav`, falls back to a stock system sound (`afplay` on macOS, `paplay` on Linux, silent no-op when neither applies).

## Flow

1. **Survey.** Read `~/.claude/settings.json` and any existing `~/.claude/hooks/*.sh`. Note what already matches the bundled canon and what differs.
1. **Install hooks.** `mkdir -p ~/.claude/hooks`, copy the three scripts there (two bundled, one from the sibling `long-run` skill — resolve this skill's real path first, since installs are symlinks), `chmod +x`. Check `command -v jq`; if missing, tell the user the long-run guard stays inert until it's installed. If a target exists with **different** content, show the diff and confirm before overwriting — the local copy may carry a fix that belongs upstream in this skill instead.
1. **Merge settings.** Ensure `~/.claude/settings.json` contains the six hook wirings below. **Merge, never clobber**: preserve every other key (`model`, `permissions`, other hooks, …) and don't duplicate an entry that already exists. Create the file with just `{"hooks": …}` if it's missing.

   ```json
   "hooks": {
     "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/keepawake.sh\""}]}],
     "PreToolUse":       [{"hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/keepawake.sh\""}]}],
     "PostToolUse":      [{"hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/keepawake.sh\""}]}],
     "Stop":             [{"hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/chime.sh\" stop"}]},
                        {"hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/long-run-guard.sh\""}]}],
     "Notification":     [{"hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/chime.sh\" notify"}]}]
   }
   ```

   Keep the `"$HOME/…"` quoted form — hook commands run through a shell, and the expansion is what makes the same settings file portable across `/Users/<u>` and `/home/<u>`.
1. **Personal sounds (optional).** `~/.claude/sounds/stop.wav` / `notify.wav` override the system sounds. They are personal files and intentionally **not** bundled in this public repo; the user copies them over from another machine if wanted. Without them the system fallbacks are used — nothing to fix.
1. **Verify.** Hooks hot-reload — no Claude Code restart needed.
   - Fire once: `sh -c '"$HOME/.claude/hooks/keepawake.sh"'`, then check the inhibitor exists — macOS `pgrep -fl "caffeinate -is -t"`, Linux `pgrep -af "systemd-inhibit.*claude-keepawake"` (on headless Linux, absence is correct).
   - Lease expiry: `CLAUDE_KEEPAWAKE_LEASE=5 sh -c '…keepawake.sh'`, confirm the process is gone a few seconds later.
   - Long-run guard: in a scratch git repo, `echo goal > .long-run`, then pipe `{"cwd":"<repo>","session_id":"t","last_assistant_message":"done"}` into the script — it must print a `"decision": "block"` object; with `"last_assistant_message":"LONG-RUN STOP: queue-empty"` it must print nothing and delete the flag. Without a flag it must print nothing.
   - Chime: `sh -c '"$HOME/.claude/hooks/chime.sh" stop'` — the user should hear it (skip on headless).
1. **Report.** What was installed vs already current, any diffs the user resolved, and the verification results.

## Guarantees

- **No silent overwrites.** A differing hook script is shown and confirmed before being replaced.
- **settings.json is merged, never replaced.** Unrelated keys and hooks survive untouched.
- **Idle machines may sleep.** The keep-awake mechanism is a bounded lease tied to agent activity, not a resident inhibitor.
- **Nothing leaves the machine.** The skill writes only under `~/.claude`; no commits, no network.

## Divergence rule

If a machine's local copy turns out to be *better* than the bundle (a fix, a new platform branch), the fix belongs here first: update this skill's bundled file, push, then re-run init-machine on the other machines. Canon lives in the repo, not in `~/.claude`.
