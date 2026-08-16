#!/bin/sh
# Cross-platform chime for Claude Code hooks. Usage: chime.sh <stop|notify>
# Plays the user's own sound ($HOME/.claude/sounds/<event>.wav) when present,
# else a stock system sound; silent no-op when no player exists (headless).
ev="$1"
case "$ev" in stop|notify) ;; *) exit 0 ;; esac
if [ "$(uname -s)" = Darwin ]; then
  play=afplay
  case "$ev" in
  stop)   sys=/System/Library/Sounds/Glass.aiff ;;
  notify) sys=/System/Library/Sounds/Submarine.aiff ;;
  esac
else
  command -v paplay >/dev/null 2>&1 || exit 0
  play=paplay
  case "$ev" in
  stop)   sys=/usr/share/sounds/freedesktop/stereo/complete.oga ;;
  notify) sys=/usr/share/sounds/freedesktop/stereo/message.oga ;;
  esac
fi
for snd in "$HOME/.claude/sounds/$ev.wav" "$sys"; do
  [ -f "$snd" ] && { "$play" "$snd" 2>/dev/null; break; }
done
exit 0
