#!/bin/sh
# Lease-based keep-awake for Claude Code.
# Called from UserPromptSubmit / PreToolUse / PostToolUse hooks: each call
# restarts a bounded sleep inhibitor, so the machine stays awake until
# LEASE seconds past the last agent activity (subagent tool calls fire the
# same hooks), then the inhibition self-expires — no unbounded residents.
# Long background commands are not covered by the lease — they carry their
# own inhibitor wrapper around the command, since their waits can outlive it.
LEASE="${CLAUDE_KEEPAWAKE_LEASE:-720}"
case "$(uname -s)" in
Darwin)
  pkill -f "^caffeinate -is -t " 2>/dev/null
  nohup caffeinate -is -t "$LEASE" >/dev/null 2>&1 &
  ;;
Linux)
  # headless / no systemd session: no-op, servers don't idle-sleep anyway
  command -v systemd-inhibit >/dev/null 2>&1 || exit 0
  pkill -f "systemd-inhibit.*claude-keepawake" 2>/dev/null
  nohup systemd-inhibit --what=idle:sleep --why=claude-keepawake \
    sleep "$LEASE" >/dev/null 2>&1 &
  ;;
esac
exit 0
