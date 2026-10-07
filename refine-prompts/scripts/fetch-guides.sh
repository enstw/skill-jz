#!/usr/bin/env bash
# Fetch Anthropic's prompting guides as Markdown for refine-prompts.
#
#   fetch-guides.sh [--model <model-id>] [out_dir]
#
# Always fetches the general guide (claude-prompting-best-practices.md).
# With --model, also fetches that model's own guide (prompting-claude-<slug>.md)
# and, when that guide's intro links an earlier model guide it builds on, that
# one too (one hop only). Model guides are discovered through llms.txt, never
# guessed: a model with no guide in the index gets the general guide alone.
#
# Output (stdout), one line per file, then the out_dir:
#   GUIDE <role> <url> sha256:<12 hex> <bytes> <local path>
#   NO_MODEL_GUIDE <model-id> available: <slugs...>
#   OUT_DIR <dir>
# The same GUIDE lines plus a fetched-at stamp are written to <out_dir>/MANIFEST.
# Exit: 0 ok, 2 usage, 3 fetch/validation failure (nothing partial left behind).
set -euo pipefail

BASE=https://platform.claude.com/docs/en/build-with-claude/prompt-engineering
INDEX=https://platform.claude.com/llms.txt
GENERAL="$BASE/claude-prompting-best-practices.md"

model=""
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    --model) model="${2:-}"; [ -n "$model" ] || { echo "usage: $0 [--model <id>] [out_dir]" >&2; exit 2; }; shift 2 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) out="$1"; shift ;;
  esac
done
[ -n "$out" ] || out="$(mktemp -d "${TMPDIR:-/tmp}/refine-prompts.XXXXXX")"
mkdir -p "$out"

sha12() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -c1-12; }

manifest="$out/MANIFEST.tmp"
: > "$manifest"

# fetch <role> <url>: download atomically, require a Markdown page with a title.
fetch() {
  local role="$1" url="$2" dest="$out/${2##*/}" tmp ctype
  tmp="$dest.part"
  ctype=$(curl -fsSL --retry 3 --retry-delay 2 -o "$tmp" -w '%{content_type}' "$url") \
    || { rm -f "$tmp"; echo "FETCH_FAIL $url" >&2; exit 3; }
  case "$ctype" in text/markdown*|text/plain*) ;; *) rm -f "$tmp"; echo "FETCH_FAIL $url (content-type $ctype)" >&2; exit 3 ;; esac
  head -5 "$tmp" | grep -q '^title: ' || { rm -f "$tmp"; echo "FETCH_FAIL $url (no title frontmatter)" >&2; exit 3; }
  mv "$tmp" "$dest"
  local line="GUIDE $role $url sha256:$(sha12 "$dest") $(wc -c < "$dest" | tr -d ' ') $dest"
  echo "$line"; echo "$line" >> "$manifest"
}

fetch general "$GENERAL"

if [ -n "$model" ]; then
  # claude-opus-5-5 -> opus-5-5; claude-haiku-4-5-20251001 -> haiku-4-5
  slug=$(printf '%s' "$model" | sed -E 's/^claude-//; s/-[0-9]{8}$//')
  index=$(curl -fsSL --retry 3 "$INDEX") || { echo "FETCH_FAIL $INDEX" >&2; exit 3; }
  guides=$(printf '%s\n' "$index" | grep -oE "$BASE/prompting-claude-[a-z0-9-]+\.md" | sort -u)
  url="$BASE/prompting-claude-$slug.md"
  if printf '%s\n' "$guides" | grep -qxF "$url"; then
    fetch model "$url"
    # Predecessor: another model guide linked before the first section heading.
    prev=$(awk '/^## /{exit} {print}' "$out/prompting-claude-$slug.md" \
      | grep -oE 'prompting-claude-[a-z0-9-]+' | grep -vxF "prompting-claude-$slug" | sort -u | head -1 || true)
    if [ -n "$prev" ] && printf '%s\n' "$guides" | grep -qxF "$BASE/$prev.md"; then
      fetch predecessor "$BASE/$prev.md"
    fi
  else
    echo "NO_MODEL_GUIDE $model available: $(printf '%s\n' "$guides" | sed -E 's#.*/prompting-claude-##; s#\.md$##' | tr '\n' ' ')"
  fi
fi

{ echo "fetched-at $(date -u +%Y-%m-%dT%H:%M:%SZ)"; cat "$manifest"; } > "$out/MANIFEST"
rm -f "$manifest"
echo "OUT_DIR $out"
