#!/usr/bin/env bash
# browser-screenshot — hardened headless screenshot / DOM dump of any URL or local HTML file.
#
# Brave/Chrome 149+ removed the one-shot `--headless --screenshot` / `--dump-dom` capture
# flags (they now render but write nothing), so this drives a headless instance over the
# DevTools Protocol instead: launch ONE browser with --remote-debugging-port for the whole
# batch, then capture each page with a tiny Bun CDP client (scripts/cdp-shot.mjs).
#
# Failure modes it still defends against:
#   1. Cold profile / slow startup -> wait on the /json/version endpoint with curl --retry
#      (no fixed sleep); reuse ONE profile so later runs are warm.
#   2. A wedged browser never returning -> every CDP call is wrapped in GNU `timeout`.
#   3. Stale Singleton lock from a killed run -> deleted before launch; the browser is reaped
#      on exit by its unique --remote-debugging-port.
# Reliability extras: empty capture retried ONCE; the GNU `timeout` guard auto-scales with
# --settle; concurrent invocations serialize on a portable mkdir-lock (macOS has no flock).
#
# Usage:
#   shot.sh <url|file> [<url|file>...]     screenshot each -> /tmp/shot-<n>.png (or --out)
#   shot.sh --dump <url|file>              print the loaded DOM to stdout (read synchronous data-*)
# Flags:  --out <path>   --size WxH (1920x1080)   --settle <ms> (2500)   --guard <sec> (auto)
# Env:    BROWSER_BIN  BUN_BIN  SHOT_PROFILE  SHOT_PORT
set -u
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
CDP="$SELF_DIR/cdp-shot.mjs"

usage() {
  cat >&2 <<'EOF'
browser-screenshot — hardened headless screenshot / DOM dump (DevTools Protocol).
  shot.sh <url|file> [<url|file>...]   screenshot each -> /tmp/shot-<n>.png (or --out)
  shot.sh --dump <url|file>            print the loaded DOM to stdout (read synchronous data-*)
Flags: --out <path>   --size WxH (1920x1080)   --settle <ms> (2500)   --guard <sec> (auto from settle)
Env:   BROWSER_BIN  BUN_BIN  SHOT_PROFILE  SHOT_PORT
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

# --- Bun runs the CDP client (native WebSocket + fetch, no deps) ---
BUN="${BUN_BIN:-}"; [ -n "$BUN" ] || BUN="$(command -v bun || true)"; [ -n "$BUN" ] || BUN="$HOME/.bun/bin/bun"
[ -x "$BUN" ] || command -v "$BUN" >/dev/null 2>&1 || { echo "shot: bun required for CDP capture (https://bun.sh)" >&2; exit 2; }
[ -f "$CDP" ] || { echo "shot: missing CDP client at $CDP" >&2; exit 2; }

# --- GNU timeout is the per-call hard backstop ---
TIMEOUT="$(command -v gtimeout || command -v timeout || true)"
[ -n "$TIMEOUT" ] || { echo "shot: GNU timeout required (brew install coreutils)" >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo "shot: curl required" >&2; exit 2; }

PROFILE="${SHOT_PROFILE:-/tmp/browser-shot-profile}"
PORT="${SHOT_PORT:-9333}"
SIZE="1920x1080"; SETTLE=2500; GUARD=""; MODE=shot; OUT=""
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dump)    MODE=dump ;;
    --out)     OUT="${2:?--out needs a path}"; shift ;;
    --size)    SIZE="${2:?--size needs WxH}"; shift ;;
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
W="${SIZE%x*}"; H="${SIZE#*x}"

# --guard auto-scales with --settle (CDP per-call = load wait + settle + capture)
[ -n "$GUARD" ] || GUARD=$(( (SETTLE + 999) / 1000 + 8 ))

# --- serialize concurrent invocations (portable mkdir-lock; macOS has no flock) ---
LOCK="$PROFILE.lock"
ltries=0
while ! mkdir "$LOCK" 2>/dev/null; do
  if [ -f "$LOCK/pid" ]; then
    lpid="$(cat "$LOCK/pid" 2>/dev/null)"
    if [ -n "$lpid" ] && ! kill -0 "$lpid" 2>/dev/null; then rm -rf "$LOCK" 2>/dev/null; continue; fi
  fi
  ltries=$((ltries + 1))
  [ "$ltries" -gt 300 ] && { echo "shot: profile lock busy ($LOCK)" >&2; exit 3; }
  sleep 0.2
done
echo $$ > "$LOCK/pid"

to_url() {
  case "$1" in
    http://*|https://*|file://*|about:*|data:*) printf '%s' "$1" ;;
    /*) printf 'file://%s' "$1" ;;
    *)  printf 'file://%s/%s' "$PWD" "$1" ;;
  esac
}

# --- launch ONE headless browser with remote debugging for the whole batch ---
PFLAG="remote-debugging-port=$PORT"
pkill -9 -f "$PFLAG --user-data-dir=$PROFILE" 2>/dev/null
rm -f "$PROFILE"/Singleton* 2>/dev/null
"$BROWSER" --headless=new --disable-gpu --no-first-run --user-data-dir="$PROFILE" \
  --remote-debugging-port="$PORT" --remote-allow-origins='*' --allow-file-access-from-files \
  about:blank >/dev/null 2>&1 &
BRAVE_PID=$!
cleanup() { kill "$BRAVE_PID" 2>/dev/null; pkill -9 -f "$PFLAG --user-data-dir=$PROFILE" 2>/dev/null; rm -rf "$LOCK" 2>/dev/null; }
trap cleanup EXIT INT TERM

# wait for the DevTools endpoint (no fixed sleep; covers a cold profile)
curl -s --retry 40 --retry-delay 1 --retry-connrefused "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 \
  || { echo "shot: devtools endpoint never came up on :$PORT" >&2; exit 4; }

cap() { "$TIMEOUT" -k 2 "$GUARD" "$BUN" "$CDP" "http://127.0.0.1:$PORT" "$1" "$2" "$3" "$SETTLE" "$W" "$H"; }

i=0; rc_all=0
for a in "${args[@]}"; do
  url="$(to_url "$a")"
  if [ "$MODE" = dump ]; then
    dom="$(cap dump "$url" "" 2>/dev/null)"
    [ -n "$dom" ] || dom="$(cap dump "$url" "" 2>/dev/null)"        # retry once
    if [ -n "$dom" ]; then printf '%s\n' "$dom"; else echo "shot: empty DOM for $a" >&2; rc_all=1; fi
  else
    if   [ -n "$OUT" ] && [ ${#args[@]} -eq 1 ]; then out="$OUT"
    elif [ -n "$OUT" ]; then out="${OUT%.*}-$i.${OUT##*.}"
    else out="/tmp/shot-$i.png"; fi
    cap shot "$url" "$out" >/dev/null 2>&1
    [ -s "$out" ] || cap shot "$url" "$out" >/dev/null 2>&1         # retry once
    if [ -s "$out" ]; then echo "$a  ->  $out  ($(wc -c <"$out" | tr -d ' ') bytes)"
    else echo "$a  ->  FAILED (empty / no file)"; rc_all=1; fi
  fi
  i=$((i+1))
done
exit $rc_all
