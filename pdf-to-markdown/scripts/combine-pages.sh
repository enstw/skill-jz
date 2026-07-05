#!/usr/bin/env bash
# Combine per-page markdown files in <dir>/<name>/ into <dir>/<name>.md.
# Usage: scripts/combine-pages.sh "<name>" [dir]
# <name> is the PDF stem (without .pdf) or citation key — the same
# <name> used for <dir>/<name>/pNNNN.md and the target <dir>/<name>.md.
# [dir] defaults to "workspace".

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "usage: $0 <name> [dir]" >&2
    exit 2
fi

name="$1"
dir="${2:-workspace}"
src_dir="$dir/$name"
out_file="$dir/$name.md"

if [[ ! -d "$src_dir" ]]; then
    echo "error: $src_dir does not exist" >&2
    exit 1
fi

shopt -s nullglob
pages=("$src_dir"/p*.md)
if [[ ${#pages[@]} -eq 0 ]]; then
    echo "error: no p*.md files in $src_dir" >&2
    exit 1
fi

# Lexical sort works because page files are zero-padded (p0001.md, p0099.md, ...).
IFS=$'\n' sorted=($(printf '%s\n' "${pages[@]}" | sort))
unset IFS

# Concatenate with a blank line between pages.
{
    first=1
    for f in "${sorted[@]}"; do
        if [[ $first -eq 0 ]]; then echo; fi
        cat "$f"
        first=0
    done
} > "$out_file"

echo "wrote $out_file (${#sorted[@]} pages)"

# Clean up the per-page directory now that it's aggregated.
rm -r "$src_dir"
echo "removed $src_dir"
