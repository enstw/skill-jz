---
name: slash-command-autonomous
description: >-
  Run a slash command that only exists inside an agent CLI's interactive TUI — e.g. Claude
  Code's `/artifacts` to list, copy, rename, pin, or delete published artifacts — when you are
  running headlessly and have no tool or flag for it. Launch a second, nested agent CLI inside a
  detached tmux session and drive its TUI by sending literal keystrokes and reading the pane back.
  Use this ONLY for an action the user has already authorized that simply lacks a headless path —
  never to get around a refusal, a permission prompt, or a missing capability, and never as a
  reason to reverse-engineer a service's private endpoints or lift its credentials. Description-triggered.
allowed-tools:
  - Bash(tmux *)
  - Bash(command -v *)
  - Bash(sleep *)
---

# slash-command-autonomous — drive an interactive-only slash command headlessly

Some capabilities live **only** inside an agent CLI's interactive terminal UI — reachable by
typing a slash command at the prompt, with no headless flag, no API, and no tool exposed to an
agent running non-interactively. Claude Code's `/artifacts` (manage your published artifacts:
list / copy URL / rename / pin / delete) is the worked example.

When you hit one of these headless, the wrong moves are: (a) giving up and telling the user "you'll
have to do it in the app," when the user has asked you to do it; or (b) trying to reach the
capability some other way — reverse-engineering the service's private HTTP endpoints, scraping a
session token, replaying cookies. Do neither. The sanctioned route is to **become an interactive
user of the CLI**: launch a *second* copy of the agent CLI inside a detached `tmux` session, and
drive its TUI the way a human would — literal keystrokes in, pane text out.

## Scope — read this before you start

This technique removes a *mechanical* barrier (no headless entry point), not a *policy* one. So:

- **Only for actions the user has already authorized in this session** and that merely lack a
  non-interactive path. The characterization to hold onto: *pre-authorized actions the agent just
  does.*
- **Never** to route around a refusal, a safety gate, a per-action confirmation the user hasn't
  given, or a capability that's absent *by design*. If the action would need the user's explicit
  go were a tool available for it, it still needs that go here — the tmux wrapper changes nothing
  about authorization.
- **Never** pair this with, or fall back to, reverse-engineering the service's endpoints or lifting
  account credentials. Those remain off-limits regardless of how convenient this makes them look.
- Prefer a real tool or flag if one exists. This is the fallback for when none does.

## Method

Concrete keys/labels below are Claude Code's `/artifacts` as of this writing; the *shape* —
detached session, literal send-keys, capture-pane, confirm-before-destructive, kill on exit —
is general to any TUI agent CLI. Re-read the live footer rather than trusting these labels.

### 1. Launch the nested CLI detached

```sh
tmux new-session -d -s slashcmd 'claude'      # start the agent CLI inside a detached session
sleep 3                                         # let the TUI paint
tmux capture-pane -p -t slashcmd | tail -30    # confirm it's at the prompt
```

Use a named session (`-s slashcmd`) so you can address and, crucially, **kill** it later.

### 2. Open the slash command

Send the command as **literal** text (`-l`), then submit. Two quirks bite here:

- **Send literally.** `tmux send-keys -l` sends the characters verbatim; without `-l`, tmux
  interprets tokens like `Enter`/`Space` as key names mid-string and mangles the input.
- **Autocomplete eats the first Enter.** Typing `/artifacts` pops the slash-command autocomplete
  menu, which swallows the next `Enter` as "accept highlighted entry" instead of "submit." Press
  **Escape** to dismiss the menu, *then* `Enter` to run the command.

```sh
tmux send-keys -t slashcmd -l '/artifacts'
tmux send-keys -t slashcmd Escape             # dismiss the autocomplete menu
tmux send-keys -t slashcmd Enter              # now the command actually submits
sleep 2
tmux capture-pane -p -t slashcmd | tail -40
```

### 3. Read the pane, act on what's actually there

**`capture-pane` is your only feedback loop — use it between every step.** Keystrokes land
intermittently (in practice roughly every other one registers), so never fire a blind sequence.
After each `send-keys`, capture and confirm the TUI moved to the expected state before the next
key. If it didn't advance, re-send that one key; don't pile on more.

The `/artifacts` list is a keyboard-driven picker. Read its footer for the live keymap — observed:

```
Enter to attach · c to copy url · Ctrl+R to rename · d to delete · p to pin · / to search · r to refresh
```

Navigate with arrow keys, select the target row (match on the title/date shown in the pane), and
trigger the action key from the footer:

```sh
tmux send-keys -t slashcmd Down               # move the selection; capture-pane to confirm each move
tmux capture-pane -p -t slashcmd | tail -40
```

### 4. Destructive actions: confirm the target, then confirm the prompt

For a delete (or any irreversible action), **verify from the captured pane that the highlighted row
is the intended one** before pressing the action key — you're driving blind except for what
capture-pane shows, and the list order can shift on refresh. Then the action key usually raises its
own confirm prompt:

```sh
tmux send-keys -t slashcmd d                  # 'delete' — raises a confirm prompt
tmux capture-pane -p -t slashcmd | tail -20   # READ IT: is this the row you meant? what does it ask?
tmux send-keys -t slashcmd y                  # confirm only after the pane confirms the target
sleep 2
tmux capture-pane -p -t slashcmd | tail -40   # verify: "deleted", and the list count dropped
```

Report the before/after you actually saw in the pane (e.g. "list went from 2 to 1, footer showed
'Artifact deleted'"), not just that you sent the keys.

### 5. Always clean up

The nested CLI is a real, running agent session. Leaving it resident wastes resources and leaves a
loose interactive agent around. Kill it when done — including on any error path:

```sh
tmux kill-session -t slashcmd
tmux ls 2>/dev/null | grep -q slashcmd && echo "STILL RUNNING" || echo "cleaned up"
```

If you bail out midway, kill the session before reporting back.

## Checklist

- Authorized, mechanical-only barrier — not a policy gate, not a substitute for a needed go-ahead.
- Named detached session so it can be killed.
- `send-keys -l` for literal text; Escape before Enter to beat autocomplete.
- `capture-pane` after every keystroke — keys land intermittently; never fire blind.
- Confirm the highlighted target from the pane before any destructive key.
- Report the observed before/after state, not just the keys sent.
- `kill-session` on every exit path, and verify it's gone.
