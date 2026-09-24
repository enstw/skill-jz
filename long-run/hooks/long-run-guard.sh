#!/bin/sh
# Claude Code Stop-hook adapter for the long-run skill.
# While a long run is active (a fresh `.long-run` flag at the project root), an
# end-of-turn is refused unless the final message carries a valid stop line:
#   LONG-RUN STOP: <queue-empty|needs-human|needs-authorization|user-request>
# Refusal = a "block" decision on stdout (both the top-level and the
# hookSpecificOutput form, so either reader accepts it); the agent then continues.
#
# Fail-open by design: no flag, stale flag, no jq, unreadable transcript → allow the
# stop. A guard that wedges a session is worse than one that misses a stop.
# Brakes:
#   LONG_RUN_MAX_IDLE   (3)  refusals in a row with no new tool call → allow; the
#                            agent is talking, not working.
#   LONG_RUN_MAX_BLOCKS (40) refusals in total for this session → allow; a hard
#                            cost ceiling for a run that keeps circling.
ttl=${LONG_RUN_TTL:-43200}      # seconds a flag stays live after its last touch (12 h)
max_idle=${LONG_RUN_MAX_IDLE:-3}
max_blocks=${LONG_RUN_MAX_BLOCKS:-40}

command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
sid=$(printf '%s' "$input" | jq -r '.session_id // "unknown"')
tx=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
[ -n "$cwd" ] || exit 0

# The flag lives at the project root: the git top level, else cwd itself.
root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$cwd")
flag="$root/.long-run"
[ -f "$flag" ] || exit 0

now=$(date +%s)
mtime=$(stat -f %m "$flag" 2>/dev/null || stat -c %Y "$flag" 2>/dev/null || echo 0)
[ $((now - mtime)) -le "$ttl" ] || exit 0   # stale flag from an abandoned run

# Final assistant text: the hook field is authoritative; the transcript (which may lag
# and whose line shape has varied: .message.content vs .content) is only a fallback.
msg=$(printf '%s' "$input" | jq -r '.last_assistant_message // empty')
if [ -z "$msg" ] && [ -r "$tx" ]; then
  msg=$(tail -n 400 "$tx" | jq -c 'select(.type=="assistant") | (.message.content // .content)[]? | select(.type=="text") | .text' 2>/dev/null | tail -n 1 | jq -r . 2>/dev/null)
fi

state_dir="${TMPDIR:-/tmp}/long-run-guard"
state="$state_dir/$sid"
code=$(printf '%s\n' "$msg" | sed -n 's/^[*_`> ]*LONG-RUN STOP:[*_` ]*\([a-z-]*\).*/\1/p' | tail -n 1)
case "$code" in
queue-empty|user-request)
  rm -f "$flag" "$state"; exit 0 ;;          # the run is over
needs-human|needs-authorization)
  rm -f "$state"; touch "$flag"; exit 0 ;;   # parked; the run resumes on the user's answer
esac

# No valid stop line: refuse, unless a brake trips.
tools=0
[ -r "$tx" ] && tools=$(grep -c "\"type\":\"tool_use\"" "$tx" 2>/dev/null) || tools=${tools:-0}
last_tools=-1; idle=0; total=0
[ -r "$state" ] && read -r last_tools idle total < "$state"
if [ "$tools" = "$last_tools" ]; then idle=$((idle + 1)); else idle=1; fi
total=$((total + 1))
if [ "$idle" -gt "$max_idle" ] || [ "$total" -gt "$max_blocks" ]; then
  rm -f "$state"; exit 0
fi
mkdir -p "$state_dir" && printf '%s %s %s\n' "$tools" "$idle" "$total" > "$state"
touch "$flag"

goal=$(head -c 400 "$flag" | tr '\n' ' ')
bad=""
[ -n "$code" ] && bad=" \"$code\" is not a valid stop code."
reason="Long run active ($flag: $goal).$bad Do not end the turn: take the topmost unblocked item in the work queue and continue. A milestone, a summary, a context worry, 'the rest is incremental', or a question you could answer from the queue/AGENTS.md/prior authorization is not a stop reason. Blocked item → record the blocker, move to the next item. Stop ONLY with a stop report ending in one line: 'LONG-RUN STOP: queue-empty' (every item done or blocked with a named blocker), 'needs-human' (every remaining item needs a human's hands or knowledge), 'needs-authorization' (every remaining item needs an unauthorized irreversible action), or 'user-request' (the user asked to pause/stop)."
jq -n --arg r "$reason" '{decision: "block", reason: $r, hookSpecificOutput: {hookEventName: "Stop", decision: "block", reason: $r}}'
