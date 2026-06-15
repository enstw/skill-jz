#!/usr/bin/env bash
# browser-screenshot — hardened headless screenshot / DOM dump of any URL or local HTML file.
#
# A naive `--headless --screenshot` on a Chromium-family browser hangs or writes nothing.
# This wrapper defends against three independent failure modes:
#   1. A fresh --user-data-dir is "cold" and a cold headless browser can stall through
#      first-run profile setup.  -> reuse ONE persistent profile; only the first call is cold.
#   2. --headless=new does not reliably self-exit; the capture is written, then it idles.
#      -> wrap every call in GNU `timeout` as an OS-level hard kill (the capture lands first).
#   3. A killed run leaves Singleton{Lock,Socket,Cookie} that stall the next run.
#      -> delete them before each launch (safe: runs are sequential and we reap the profile after).
#
# Reliability extras so it is deterministic even unattended:
#   * empty capture is retried ONCE (the shared profile is warm by then);
#   * the GNU `timeout` guard auto-scales with --settle, so a longer settle never out-runs the
#     hard kill (the old footgun: raise --settle, forget --guard, get a silent empty file);
#   * concurrent invocations SERIALIZE on a portable mkdir-lock (no flock dependency — macOS
#     has none) instead of corrupting the one shared profile; a crashed run's lock self-clears.
#
# Usage:
#   shot.sh <url|file> [<url|file>...]     screenshot each -> /tmp/shot-<n>.png (or --out)
#   shot.sh --dump <url|file>              print the loaded DOM to stdout (read synchronous data-*)
# Flags:  --out <path>   --size WxH (1920x1080)   --settle <ms> (2500)   --guard <sec> (auto)
# Env:    BROWSER_BIN (override browser path)      SHOT_PROFILE (override profile dir)
# Note:   one shared profile; concurrent calls serialize automatically (lock).
set -u

usage() {
  cat >&2 <<'EOF'
browser-screenshot — hardened headless screenshot / DOM dump.
  shot.sh <url|file> [<url|file>...]   screenshot each -> /tmp/shot-<n>.png (or --out)
  shot.sh --dump <url|file>            print the loaded DOM to stdout (read synchronous data-*)
Flags: --out <path>   --size WxH (1920x1080)   --settle <ms> (2500)   --guard <sec> (auto from settle)
Env:   BROWSER_BIN (browser path)   SHOT_PROFILE (profile dir)
EOF
}

# --- discover a headless browser (Brave preferred; Chrome/Chromium fall-backs) ---
BROWSER="${BROWSER_BIN:-}"
if [ -z "$BROWSER" ]; then
  for c in \
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "$(command -v brave-browser 2>/dev/null)" \
    "$(command -v chromium 2>/dev/null)" "$(command -v google-chrome 2>/dev/null)"; do
    [ -n "$c" ] && [ -x "$c" ] && { BROWSER="$c"; break; }
  done
fi
[ -n "$BROWSER" ] || { echo "shot: no headless browser found; set BROWSER_BIN" >&2; exit 2; }

# --- GNU timeout is the hard backstop (the browser's own --timeout won't kill a stall) ---
TIMEOUT="$(command -v gtimeout || command -v timeout || true)"
[ -n "$TIMEOUT" ] || { echo "shot: GNU timeout required (brew install coreutils)" >&2; exit 2; }

PROFILE="${SHOT_PROFILE:-/tmp/browser-shot-profile}"
SIZE="1920,1080"; SETTLE=2500; GUARD=""; MODE=shot; OUT=""
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dump)    MODE=dump ;;
    --out)     OUT="${2:?--out needs a path}"; shift ;;
    --size)    SIZE="${2/x/,}"; shift ;;
    --settle)  SETTLE="${2:?--settle needs ms}"; shift ;;
    --guard)   GUARD="${2:?--guard needs seconds}"; shift ;;
    -h|--help) usage; exit 0 ;;
    --)        shift; while [ $# -gt 0 ]; do args+=("$1"); shift; done; break ;;
    -*)        echo "shot: unknown flag $1" >&2; usage; exit 2 ;;
    *)         args+=("$1") ;;
  esac
  shift
done
[ ${#args[@]} -gt 0 ] || { usage; exit 2; }

# --guard auto-scales with --settle so a longer capture delay never out-runs the hard kill
# (default settle 2500ms -> guard 6s, matching the original). WARMG covers the cold first run.
[ -n "$GUARD" ] || GUARD=$(( (SETTLE + 999) / 1000 + 3 ))
WARMG=$(( GUARD + 14 )); [ "$WARMG" -lt 20 ] && WARMG=20

# --- serialize concurrent invocations on the shared profile (portable; no flock dependency) ---
# mkdir is atomic on POSIX, so it is the lock primitive. A crashed holder's lock is reclaimed
# by checking its recorded PID with `kill -0`, so a stale lock never wedges the next run.
LOCK="$PROFILE.lock"
ltries=0
while ! mkdir "$LOCK" 2>/dev/null; do
  if [ -f "$LOCK/pid" ]; then
    lpid="$(cat "$LOCK/pid" 2>/dev/null)"
    if [ -n "$lpid" ] && ! kill -0 "$lpid" 2>/dev/null; then rm -rf "$LOCK" 2>/dev/null; continue; fi
  fi
  ltries=$((ltries + 1))
  [ "$ltries" -gt 300 ] && { echo "shot: profile lock busy ($LOCK) — another capture running?" >&2; exit 3; }
  sleep 0.2
done
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK" 2>/dev/null' EXIT INT TERM

to_url() {  # normalize one arg to a loadable URL
  case "$1" in
    http://*|https://*|file://*|about:*|data:*) printf '%s' "$1" ;;
    /*) printf 'file://%s' "$1" ;;
    *)  printf 'file://%s/%s' "$PWD" "$1" ;;
  esac
}

run() {  # $1 = GNU-timeout seconds; rest = extra browser args
  local g="$1"; shift
  rm -f "$PROFILE"/Singleton* 2>/dev/null              # clear stale lock from a prior killed run
  "$TIMEOUT" -k 2 "$g" "$BROWSER" --headless=new --disable-gpu --no-first-run \
    --user-data-dir="$PROFILE" --allow-file-access-from-files \
    --window-size="$SIZE" --hide-scrollbars --timeout="$SETTLE" "$@"
  local rc=$?
  pkill -9 -f "user-data-dir=$PROFILE" 2>/dev/null     # reap strays for THIS profile only
  return $rc
}

# warm the profile once (only the first call can be cold; the looser guard caps any stall)
[ -d "$PROFILE" ] || run "$WARMG" --screenshot=/tmp/.shot-warm.png "$(to_url "${args[0]}")" >/dev/null 2>&1

i=0; rc_all=0
for a in "${args[@]}"; do
  url="$(to_url "$a")"
  if [ "$MODE" = dump ]; then
    dom="$(run "$GUARD" --dump-dom "$url" 2>/dev/null)"
    [ -n "$dom" ] || dom="$(run "$GUARD" --dump-dom "$url" 2>/dev/null)"   # retry once (now warm)
    if [ -n "$dom" ]; then printf '%s\n' "$dom"; else echo "shot: empty DOM for $a" >&2; rc_all=1; fi
  else
    if   [ -n "$OUT" ] && [ ${#args[@]} -eq 1 ]; then out="$OUT"
    elif [ -n "$OUT" ]; then out="${OUT%.*}-$i.${OUT##*.}"
    else out="/tmp/shot-$i.png"; fi
    run "$GUARD" --screenshot="$out" "$url" >/dev/null 2>&1
    [ -s "$out" ] || run "$GUARD" --screenshot="$out" "$url" >/dev/null 2>&1   # retry once (now warm)
    if [ -s "$out" ]; then echo "$a  ->  $out  ($(wc -c <"$out" | tr -d ' ') bytes)"
    else echo "$a  ->  FAILED (empty / no file)"; rc_all=1; fi
  fi
  i=$((i+1))
done
exit $rc_all
