#!/usr/bin/env bash
# gen-image.sh — generate exactly ONE nano-banana image via the agy
# (Antigravity / Gemini) CLI's built-in generate_image tool, and save it to a
# target path.
#
# Usage:   gen-image.sh "<prompt>" "<output_path.png>" ["<size/aspect hint>"]
# Success: prints  IMAGE_OK <abs_path>   and exits 0
# Failure: prints  IMAGE_FAIL <reason>   and exits non-zero (2/3/4/5/124)
#
# Same CLI contract as genimage-img2/gen-image.sh — the per-slide primitive that
# /deck-image loops over; the two scripts are drop-in interchangeable.
#
# Empirical facts this script is built on (agy 1.0.13, probed 2026-07-02):
#   - `agy -p` runs the agent non-interactively; generate_image itself needs
#     no permission approval.
#   - The agent's working directory is agy's OWN scratch
#     (~/.gemini/antigravity-cli/scratch/), NOT the caller's cwd — relative
#     save paths are useless, so we hand it an ABSOLUTE target (cp/mkdir are
#     on the user's agy permission allow-list).
#   - The tool's raw artifact is a JPEG in
#     ~/.gemini/antigravity-cli/brain/<conversation-id>/ — the mtime-fenced
#     fallback search below finds it if the copy was refused.
#   - A lingering agy child can hold stdout open after the main process
#     exits — NEVER pipe agy's output; redirect to a file.
#
# Env overrides:
#   IMGNB_TIMEOUT   wall-clock seconds before the run is killed
#                   (default: GENIMAGE_TIMEOUT, then 600)

set -uo pipefail

PROMPT="${1:-}"
OUT="${2:-}"
SIZE_HINT="${3:-landscape 16:9 aspect ratio, high detail}"
TIMEOUT_SECS="${IMGNB_TIMEOUT:-${GENIMAGE_TIMEOUT:-600}}"

[ -n "$PROMPT" ] || { echo "IMAGE_FAIL usage: gen-image.sh <prompt> <output.png> [size hint]"; exit 2; }
[ -n "$OUT" ]    || { echo "IMAGE_FAIL usage: gen-image.sh <prompt> <output.png> [size hint]"; exit 2; }

AGY_HOME="$HOME/.gemini/antigravity-cli"

# --- pre-flight gate (binary + auth), same shape as genimage-img2 ---------------------
command -v agy >/dev/null 2>&1 || {
  echo "IMAGE_FAIL agy CLI not found — install the Antigravity CLI first"; exit 3; }
[ -f "$AGY_HOME/antigravity-oauth-token" ] || {
  echo "IMAGE_FAIL agy not authenticated — run agy once interactively and log in"; exit 4; }

mkdir -p "$(dirname "$OUT")" 2>/dev/null || true
ABS_OUT=$(cd "$(dirname "$OUT")" && printf '%s/%s' "$(pwd)" "$(basename "$OUT")")

# --- timeout wrapper: prefer gtimeout (brew coreutils on macOS), then timeout -
_TO=$(command -v gtimeout 2>/dev/null || command -v timeout 2>/dev/null || echo "")
_run() { if [ -n "$_TO" ]; then "$_TO" "$TIMEOUT_SECS" "$@"; else "$@"; fi; }

_LOG=$(mktemp "${TMPDIR:-/tmp}/genimage-nb-XXXXXX.log")
_MARK=$(mktemp "${TMPDIR:-/tmp}/genimage-nb-mark-XXXXXX")   # mtime fence for the fallback search

_PROMPT="Use your generate_image tool to generate exactly ONE image and nothing else.
Image description: ${PROMPT}
Style / format: ${SIZE_HINT}.
Then copy the generated image file to the EXACT absolute path '${ABS_OUT}' with cp (create parent directories with mkdir -p first if needed; overwrite if it exists; do not convert or edit the image).
Do not generate more than one image. Do not ask questions.
When done, print the final absolute saved path on its own line prefixed exactly with 'IMAGE_PATH:'."

# stdout goes to a FILE, never a pipe (see header). stdin closed.
_run agy -p "$_PROMPT" < /dev/null > "$_LOG" 2>&1
RC=$?

# On failure: tail to stderr, keep the full log on disk, IMAGE_FAIL names it.
if [ "$RC" = "124" ]; then
  tail -5 "$_LOG" | sed 's/^/  agy| /' >&2
  echo "IMAGE_FAIL agy stalled past ${TIMEOUT_SECS}s — re-run or simplify the prompt (full log: $_LOG)"
  rm -f "$_MARK"; exit 124
fi

# --- resolve the produced file ------------------------------------------------
# Preference: the requested OUT (the agent's cp normally lands it there) →
# the IMAGE_PATH: line if it names a real file → newest image dropped in agy's
# scratch/brain dirs since the fence (both mtime-newer than $_MARK).
PARSED=$(grep -aEo 'IMAGE_PATH:[[:space:]]*[^[:space:]].*' "$_LOG" | tail -1 | sed -E 's/^IMAGE_PATH:[[:space:]]*//')
SRC=""
if   [ -f "$ABS_OUT" ] && [ "$ABS_OUT" -nt "$_MARK" ]; then SRC="$ABS_OUT"
elif [ -n "$PARSED" ] && [ -f "$PARSED" ]; then SRC="$PARSED"
elif [ -n "$PARSED" ] && [ -f "$AGY_HOME/scratch/$PARSED" ]; then SRC="$AGY_HOME/scratch/$PARSED"
else
  SRC=$(find "$AGY_HOME/scratch" "$AGY_HOME/brain" -type f \
          \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) \
          -newer "$_MARK" -print0 2>/dev/null | xargs -0 ls -td 2>/dev/null | head -1)
fi

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  tail -8 "$_LOG" | sed 's/^/  agy| /' >&2
  echo "IMAGE_FAIL no image produced (full log: $_LOG)"
  rm -f "$_MARK"; exit 5
fi

[ "$SRC" != "$ABS_OUT" ] && cp -f "$SRC" "$ABS_OUT"

# --- deliver a real PNG at OUT (the raw artifact is often JPEG) ---------------
if ! file "$ABS_OUT" 2>/dev/null | grep -q "PNG image data"; then
  if command -v sips >/dev/null 2>&1; then
    _TMP_PNG="${ABS_OUT%.png}.imgnb-tmp.png"
    if sips -s format png "$ABS_OUT" --out "$_TMP_PNG" >/dev/null 2>&1; then
      mv -f "$_TMP_PNG" "$ABS_OUT"
    else
      rm -f "$_TMP_PNG"
    fi
  fi
fi

rm -f "$_LOG" "$_MARK"
echo "IMAGE_OK $ABS_OUT"
