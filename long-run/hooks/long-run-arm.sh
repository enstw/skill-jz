#!/bin/sh
# Claude Code UserPromptSubmit-hook adapter for the long-run skill.
# Arms a long run deterministically when the user's prompt asks for one, so the
# enforcement does not depend on the agent creating the flag against itself.
#   trigger: the prompt contains "long run" / "long-run" / "longrun" / "長跑"
#            (but not the idiom "in the long run")
#   effect:  writes `.long-run` at the project root (git top level, else cwd) with
#            the prompt as its goal text, keeps it out of version control via
#            .git/info/exclude, and injects one line of context telling the agent
#            the run is armed.
# Fail-open: no jq, no prompt, no trigger → does nothing, prints nothing.
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$prompt" ] && [ -n "$cwd" ] || exit 0

lower=$(printf '%s' "$prompt" | tr 'A-Z' 'a-z')
case "$lower" in
*"in the long run"*) exit 0 ;;
esac
case "$lower" in
*"long run"*|*"long-run"*|*"longrun"*|*"長跑"*) ;;
*) exit 0 ;;
esac

root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$cwd")
flag="$root/.long-run"
printf '%s\n' "$prompt" | head -c 2000 > "$flag"
if [ -d "$root/.git" ]; then
  ex="$root/.git/info/exclude"
  mkdir -p "$root/.git/info"
  grep -qx '.long-run' "$ex" 2>/dev/null || printf '.long-run\n' >> "$ex"
fi

ctx="Long run ARMED: $flag exists and the Stop guard will refuse an end-of-turn without a valid 'LONG-RUN STOP: <code>' line. Follow the long-run skill: find the goal, the work queue and standing authorizations in AGENTS.md, then work the topmost unblocked item and keep going."
jq -n --arg c "$ctx" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $c}}'
