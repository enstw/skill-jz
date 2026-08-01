#!/usr/bin/env bash
# gen-image.sh — draw ONE designed image by asking Claude Code's stock
# canvas-design skill to author an HTML composition, then rasterizing it via
# the browser-cdp skill's shot.sh.
#
# Usage:   gen-image.sh "<brief | src.html>" "<output_path.png>" ["<size hint>"]
# Success: prints  IMAGE_OK <abs_path>   and exits 0
# Failure: prints  IMAGE_FAIL <reason>   and exits non-zero (2/3/4/5/124)
#
# Same name, args, and IMAGE_OK/IMAGE_FAIL contract as genimage-img2 and
# genimage-nb — the third interchangeable single-image primitive.
# Arg 3 tolerates the siblings' freeform size hint: the first WxH token in it
# wins; no WxH token -> 1920x1080. If the first argument is an existing .html
# file, the script skips Claude and just re-renders that source.
#
# Env overrides:
#   GENCANVAS_TIMEOUT     wall-clock seconds for the Claude authoring run
#                         (default: GENIMAGE_TIMEOUT, then 600)
#   GENCANVAS_CLAUDE_BIN  Claude Code binary (default: claude)
#   GENCANVAS_SHOT        browser-cdp shot.sh path override

set -uo pipefail

fail() {
  rc="$1"; shift
  echo "IMAGE_FAIL $*"
  exit "$rc"
}

INPUT="${1:-}"
OUT="${2:-}"
# Arg 3 is hint-tolerant for sibling interchangeability: use its first WxH
# token; a hint with none ("landscape 16:9, high detail") falls back to
# 1920x1080, which is 16:9 anyway.
SIZE=$(printf '%s' "${3:-}" | grep -oE '[0-9]{2,5}x[0-9]{2,5}' | head -1)
[ -n "$SIZE" ] || SIZE="1920x1080"
TIMEOUT_SECS="${GENCANVAS_TIMEOUT:-${GENIMAGE_TIMEOUT:-600}}"
CLAUDE_BIN="${GENCANVAS_CLAUDE_BIN:-${CLAUDE_BIN:-claude}}"

[ -n "$INPUT" ] && [ -n "$OUT" ] || fail 2 'usage: gen-image.sh "<brief | src.html>" <output.png> [size hint]'

mkdir -p "$(dirname "$OUT")" 2>/dev/null || true
OUT_DIR="$(cd "$(dirname "$OUT")" 2>/dev/null && pwd)" || fail 2 "cannot create output directory: $(dirname "$OUT")"
ABS_OUT="$OUT_DIR/$(basename "$OUT")"
HTML_OUT="${ABS_OUT%.*}.html"
WORK_DIR="$(dirname "$HTML_OUT")"

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
SHOT="${GENCANVAS_SHOT:-}"
if [ -z "$SHOT" ]; then
  for candidate in \
    "$HOME/.claude/skills/browser-cdp/scripts/shot.sh" \
    "$HOME/.codex/skills/browser-cdp/scripts/shot.sh" \
    "$SELF_DIR/../browser-cdp/scripts/shot.sh" \
    "$HOME/.claude/skills/browser-screenshot/scripts/shot.sh" \
    "$HOME/.codex/skills/browser-screenshot/scripts/shot.sh" \
    "$SELF_DIR/../browser-screenshot/scripts/shot.sh"; do
    [ -x "$candidate" ] && { SHOT="$candidate"; break; }
  done
fi
[ -x "$SHOT" ] || fail 3 "browser-cdp skill missing — set GENCANVAS_SHOT or link browser-cdp so scripts/shot.sh is executable"

_TO=$(command -v gtimeout 2>/dev/null || command -v timeout 2>/dev/null || echo "")
run_with_timeout() {
  if [ -n "$_TO" ]; then "$_TO" "$TIMEOUT_SECS" "$@"; else "$@"; fi
}

author_with_claude() {
  command -v "$CLAUDE_BIN" >/dev/null 2>&1 || [ -x "$CLAUDE_BIN" ] || \
    fail 3 "claude CLI not found — install Claude Code or set GENCANVAS_CLAUDE_BIN"

  [ -f "$HOME/.claude/skills/canvas-design/SKILL.md" ] || \
    fail 4 "Claude canvas-design skill missing — install/link the stock skill at ~/.claude/skills/canvas-design"

  _LOG=$(mktemp "${TMPDIR:-/tmp}/gencanvas-XXXXXX.log")
  _PROMPT_FILE=$(mktemp "${TMPDIR:-/tmp}/gencanvas-XXXXXX.prompt")
  # Heredoc deliberately NOT nested in $() — old bash (macOS 3.2) mis-parses
  # quotes inside $(cat <<EOF). The prompt is fed to claude -p via stdin.
  cat > "$_PROMPT_FILE" <<EOF
Use the canvas-design skill (if the Skill tool is unavailable, Read
~/.claude/skills/canvas-design/SKILL.md and follow it) to create one polished
static design from this brief — but express the final canvas as HTML/CSS/SVG
instead of the skill's usual PNG/PDF; this wrapper rasterizes the HTML for you
afterwards.

Brief:
$INPUT

Hard requirements for this wrapper:
- Write exactly one self-contained HTML file to this absolute path:
  $HTML_OUT
- The canvas must be exactly $SIZE. Use one fixed-size stage, body margin 0,
  and overflow hidden so the page renders without scrollbars.
- HTML/CSS/SVG only; no network resources.
- Fonts: @font-face the canvas-design skill's bundled fonts by ABSOLUTE path,
  e.g. src: url('file://$HOME/.claude/skills/canvas-design/canvas-fonts/<Name>.ttf')
  — the rasterizer allows cross-directory file access — or use system fonts.
  For CJK text use a system CJK font (e.g. "PingFang TC" on macOS) unless the
  brief names a font file.
- Keep text sparse and exact. Preserve any user-requested in-image text
  verbatim, including language and punctuation.
- The design-philosophy .md the skill produces may sit beside the HTML; create
  no other files. Do not rasterize a PNG/PDF yourself, open a browser, or take
  screenshots. Once the HTML — including the skill's refinement pass — is
  final, stop.
- Print the final absolute HTML path on its own line prefixed exactly with
  "HTML_PATH:".
EOF

  (cd "$WORK_DIR" && run_with_timeout "$CLAUDE_BIN" -p \
    --permission-mode acceptEdits \
    --allowedTools "Skill,Read,Write,Edit" \
    --add-dir "$WORK_DIR" \
    --no-session-persistence \
    < "$_PROMPT_FILE" > "$_LOG" 2>&1)
  RC=$?
  rm -f "$_PROMPT_FILE"

  PARSED=$(grep -aEo 'HTML_PATH:[[:space:]]*[^[:space:]].*' "$_LOG" | tail -1 | sed -E 's/^HTML_PATH:[[:space:]]*//')
  if [ -n "$PARSED" ] && [ -f "$PARSED" ] && [ "$PARSED" != "$HTML_OUT" ]; then
    cp -f "$PARSED" "$HTML_OUT" 2>/dev/null || true
  fi

  # On failure: tail to stderr, keep the full log on disk, IMAGE_FAIL names it.
  if [ "$RC" = "124" ] && [ -s "$HTML_OUT" ]; then
    echo "WARN claude hit ${TIMEOUT_SECS}s after authoring HTML; continuing with $HTML_OUT" >&2
  elif [ "$RC" = "124" ]; then
    tail -8 "$_LOG" | sed 's/^/  claude| /' >&2
    echo "IMAGE_FAIL claude stalled past ${TIMEOUT_SECS}s while authoring HTML (full log: $_LOG)"
    exit 124
  elif [ "$RC" -ne 0 ] && [ -s "$HTML_OUT" ]; then
    echo "WARN claude exited $RC after authoring HTML; continuing with $HTML_OUT" >&2
  elif [ "$RC" -ne 0 ]; then
    tail -10 "$_LOG" | sed 's/^/  claude| /' >&2
    echo "IMAGE_FAIL claude exited $RC before authoring HTML (full log: $_LOG)"
    exit 5
  fi

  if [ ! -s "$HTML_OUT" ]; then
    tail -10 "$_LOG" | sed 's/^/  claude| /' >&2
    echo "IMAGE_FAIL claude did not author HTML at $HTML_OUT (full log: $_LOG)"
    exit 5
  fi
  rm -f "$_LOG"
}

case "$INPUT" in
  *.html|*.htm)
    [ -f "$INPUT" ] || fail 2 "source HTML not found: $INPUT"
    SRC="$INPUT"
    ;;
  *)
    author_with_claude
    SRC="$HTML_OUT"
    ;;
esac

"$SHOT" "$SRC" --size "$SIZE" --out "$ABS_OUT" >&2
RC=$?

if [ "$RC" -ne 0 ] || [ ! -s "$ABS_OUT" ]; then
  echo "IMAGE_FAIL rasterize failed (shot.sh exit $RC) — check the HTML opens cleanly in a browser and see shot.sh output above"
  rm -f "$ABS_OUT"; exit 5
fi

file "$ABS_OUT" 2>/dev/null | grep -q "PNG image data" || \
  fail 5 "output is not a PNG — shot.sh produced something unexpected at $ABS_OUT"

echo "IMAGE_OK $ABS_OUT"
