#!/usr/bin/env bash
# render.sh — rasterize ONE hand-authored HTML composition to a PNG via the
# browser-screenshot skill. This is the mechanical half of /genimage-canvas; the
# creative half is the agent authoring the HTML following the canvas-design
# skill's design-philosophy method (see SKILL.md).
#
# Usage:   render.sh <src.html> <output_path.png> ["WxH" (default 1920x1080)]
# Success: prints  IMAGE_OK <abs_path>   and exits 0
# Failure: prints  IMAGE_FAIL <reason>   and exits non-zero (2/3/5)
#
# Same IMAGE_OK/IMAGE_FAIL contract as genimage-img2/gen-image.sh and genimage-nb/gen-image.sh
# — the third interchangeable per-slide primitive for /deck-image. The input
# differs by nature: a drawn composition starts from an HTML file the agent
# authored, not from a prompt.
#
# Dependency gates:
#   browser-screenshot  HARD — nothing to rasterize with without it.
#   canvas-design       SOFT (stderr warning) — the authoring philosophy; a
#                       missing copy can't stop an already-authored HTML from
#                       rendering, but the warning flags that the composition
#                       was likely authored without the method.

set -uo pipefail

SRC="${1:-}"
OUT="${2:-}"
SIZE="${3:-1920x1080}"

[ -n "$SRC" ] && [ -n "$OUT" ] || {
  echo "IMAGE_FAIL usage: render.sh <src.html> <output.png> [WxH]"; exit 2; }
[ -f "$SRC" ] || { echo "IMAGE_FAIL source HTML not found: $SRC"; exit 2; }

SHOT="$HOME/.claude/skills/browser-screenshot/scripts/shot.sh"
[ -x "$SHOT" ] || {
  echo "IMAGE_FAIL browser-screenshot skill missing — install/link it at ~/.claude/skills/browser-screenshot (its scripts/shot.sh does the rasterizing)"; exit 3; }

[ -f "$HOME/.claude/skills/canvas-design/SKILL.md" ] || \
  echo "WARN canvas-design skill missing — /genimage-canvas compositions should follow its design-philosophy method; install: copy skills/canvas-design/ from https://github.com/anthropics/skills into ~/.claude/skills/" >&2

mkdir -p "$(dirname "$OUT")" 2>/dev/null || true

"$SHOT" "$SRC" --size "$SIZE" --out "$OUT" >&2
RC=$?

if [ "$RC" -ne 0 ] || [ ! -s "$OUT" ]; then
  echo "IMAGE_FAIL rasterize failed (shot.sh exit $RC) — check the HTML opens cleanly in a browser and see the shot.sh output above"
  rm -f "$OUT"; exit 5
fi

file "$OUT" 2>/dev/null | grep -q "PNG image data" || {
  echo "IMAGE_FAIL output is not a PNG — shot.sh produced something unexpected at $OUT"; exit 5; }

ABS=$(cd "$(dirname "$OUT")" && printf '%s/%s' "$(pwd)" "$(basename "$OUT")")
echo "IMAGE_OK $ABS"
