#!/usr/bin/env bash
# gen-image.sh — generate exactly ONE gpt-image-2 image via the Codex CLI's
# built-in imagegen skill, and save it to a target path.
#
# Usage:   gen-image.sh "<prompt>" "<output_path.png>" ["<size/aspect hint>"]
# Success: prints  IMAGE_OK <abs_path>   and exits 0
# Failure: prints  IMAGE_FAIL <reason>   and exits non-zero (2/3/4/5/124)
#
# This is the single-image primitive shared by the /img2 and /deck-img2 skills.
# It mirrors how the gstack /codex skill drives codex: a binary+auth gate, a
# gtimeout/timeout wrapper, `codex exec` with stdin closed, and a parseable
# stdout contract (IMAGE_PATH:). Generation runs server-side under codex's
# ChatGPT-subscription auth, so no OPENAI_API_KEY is required.
#
# Env overrides:
#   IMG2_TIMEOUT   wall-clock seconds before the run is killed (default 600)

set -uo pipefail

PROMPT="${1:-}"
OUT="${2:-}"
SIZE_HINT="${3:-landscape 16:9 aspect ratio, high detail}"
TIMEOUT_SECS="${IMG2_TIMEOUT:-600}"

[ -n "$PROMPT" ] || { echo "IMAGE_FAIL usage: gen-image.sh <prompt> <output.png> [size hint]"; exit 2; }
[ -n "$OUT" ]    || { echo "IMAGE_FAIL usage: gen-image.sh <prompt> <output.png> [size hint]"; exit 2; }

# --- pre-flight gate (binary + auth), same shape as the codex skill ----------
command -v codex >/dev/null 2>&1 || {
  echo "IMAGE_FAIL codex CLI not found — install: pnpm add -g @openai/codex, then run: codex login"; exit 3; }
[ -f "${CODEX_HOME:-$HOME/.codex}/auth.json" ] || [ -n "${OPENAI_API_KEY:-}" ] || [ -n "${CODEX_API_KEY:-}" ] || {
  echo "IMAGE_FAIL codex not authenticated — run: codex login (a ChatGPT account is enough)"; exit 4; }

mkdir -p "$(dirname "$OUT")" 2>/dev/null || true

# --- timeout wrapper: prefer gtimeout (brew coreutils on macOS), then timeout -
_TO=$(command -v gtimeout 2>/dev/null || command -v timeout 2>/dev/null || echo "")
_run() { if [ -n "$_TO" ]; then "$_TO" "$TIMEOUT_SECS" "$@"; else "$@"; fi; }

_LOG=$(mktemp "${TMPDIR:-/tmp}/img2-XXXXXX.log")
_MARK=$(mktemp "${TMPDIR:-/tmp}/img2-mark-XXXXXX")   # mtime fence for the fallback search

_PROMPT="Use your built-in generateimage (imagegen) skill to generate exactly ONE image and nothing else.
Image description: ${PROMPT}
Style / format: ${SIZE_HINT}.
Save the resulting PNG to the path '${OUT}' (relative to the current working directory; create parent folders if needed; overwrite if it already exists).
Do not generate more than one image. Do not ask questions.
When done, print the final saved path on its own line prefixed exactly with 'IMAGE_PATH:'."

# -s workspace-write is required so codex may write the PNG into the repo;
# --skip-git-repo-check lets it run in non-git / untrusted output dirs;
# stdin is closed (< /dev/null) to avoid the stdin deadlock in some CLI builds.
_run codex exec -s workspace-write --skip-git-repo-check "$_PROMPT" < /dev/null > "$_LOG" 2>&1
RC=$?

if [ "$RC" = "124" ]; then
  echo "IMAGE_FAIL codex stalled past ${TIMEOUT_SECS}s — re-run or simplify the prompt (check ~/.codex/logs/)"
  tail -5 "$_LOG" | sed 's/^/  codex| /' >&2
  rm -f "$_LOG" "$_MARK"; exit 124
fi

# --- resolve the produced file ----------------------------------------------
PARSED=$(grep -aEo 'IMAGE_PATH:[[:space:]]*[^[:space:]].*' "$_LOG" | tail -1 | sed -E 's/^IMAGE_PATH:[[:space:]]*//')
SRC=""
if   [ -f "$OUT" ]; then SRC="$OUT"
elif [ -n "$PARSED" ] && [ -f "$PARSED" ]; then SRC="$PARSED"
elif [ -d "$HOME/.codex/generated_images" ]; then
  # last resort: a png codex dropped into its own folder during this run
  SRC=$(find "$HOME/.codex/generated_images" -type f -name '*.png' -newer "$_MARK" 2>/dev/null | head -1)
fi

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "IMAGE_FAIL no image produced — last codex output below:"
  tail -8 "$_LOG" | sed 's/^/  codex| /' >&2
  rm -f "$_LOG" "$_MARK"; exit 5
fi

[ "$SRC" != "$OUT" ] && cp -f "$SRC" "$OUT"

ABS=$(cd "$(dirname "$OUT")" && printf '%s/%s' "$(pwd)" "$(basename "$OUT")")
rm -f "$_LOG" "$_MARK"
echo "IMAGE_OK $ABS"
