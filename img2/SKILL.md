---
name: img2
description: >
  Generate a single image with OpenAI gpt-image-2, driven through the Codex
  CLI's built-in imagegen skill. PRE-CONDITION: the `codex` CLI must be
  installed and authenticated (`codex login`; a ChatGPT subscription is enough
  — no OPENAI_API_KEY needed). Use when asked to "generate an image", "make an
  illustration/hero/mockup/slide image", "gpt-image-2", or "img2". This is the
  single-image primitive that /deck-img2 calls once per slide. Not for
  SVG/vector/code-native graphics — build those directly instead.
---

# /img2 — one gpt-image-2 image via Codex

Produces one bitmap with **gpt-image-2** (OpenAI's current image model) by
shelling out to `codex exec`. Codex's built-in `imagegen` tool does the
generation server-side under ChatGPT-subscription auth, so this works without
`OPENAI_API_KEY`.

The whole call is wrapped in `gen-image.sh` (in this skill folder), which is
the single source of truth for the codex invocation. It mirrors how the gstack
`/codex` skill drives codex: a binary + auth gate, a `gtimeout`/`timeout`
wrapper, `codex exec` with stdin closed, and a parseable `IMAGE_PATH:` stdout
contract. `/deck-img2` reuses this exact script.

## Usage

1. `/img2 <description>` — generate, save to `./generated-images/<slug>.png`
1. `/img2 <description> --out <path.png>` — generate, save to an explicit path
1. `/img2 edit <path/to/image> <instructions>` — edit an existing image

## Step 1: Pre-flight (the pre-condition gate)

`gen-image.sh` checks this itself and exits with a clear `IMAGE_FAIL` line, but
you can probe first:

```bash
command -v codex >/dev/null || echo "CODEX_MISSING"
[ -f "${CODEX_HOME:-$HOME/.codex}/auth.json" ] || [ -n "$OPENAI_API_KEY" ] || [ -n "$CODEX_API_KEY" ] || echo "AUTH_MISSING"
```

1. `CODEX_MISSING` → stop: "Codex CLI not found. Install: `pnpm add -g @openai/codex`, then `codex login`."
1. `AUTH_MISSING` → stop: "Run `codex login` first (a ChatGPT account is enough — no API key needed)."

## Step 2: Resolve inputs

1. **Description** — the user's prompt, near-verbatim. If generic, lightly
   structure it (subject, style/medium, composition, lighting, constraints) but
   do not invent objects, brands, or text the user didn't imply. Quote any
   required in-image text verbatim, in the language requested.
1. **Output path** — `--out <path.png>` if given, else `./generated-images/<slug>.png`.
   Keep it **inside the current working directory** — codex runs with a
   workspace-write sandbox and writes there. (If the target is outside CWD,
   `gen-image.sh` still recovers the file from `~/.codex/generated_images/` and
   copies it into place.)
1. **Size / aspect hint** — third arg to the script, folded into the prompt as
   text (the imagegen tool takes prompt text only, no size flag). Square renders
   fastest. gpt-image-2 honors aspect loosely; see the reference below for valid
   exact sizes when it matters.

## Step 3: Run

One call. Allow up to ~10 minutes (rendering is typically 1–3 min). Use
`timeout: 600000` on the Bash tool call.

```bash
~/.claude/skills/img2/gen-image.sh \
  "<DESCRIPTION>" \
  "generated-images/<slug>.png" \
  "landscape 16:9 aspect ratio, high detail"
```

**Edit mode** — drive codex directly (the script is generate-only):

```bash
codex exec -s workspace-write --skip-git-repo-check 'Load <IMAGE_PATH_IN> with your view_image tool, then use your built-in generateimage (imagegen) skill in edit mode: <EDIT_INSTRUCTIONS>. Change only what was asked; keep everything else unchanged. Save the result as a NEW versioned file next to the original (never overwrite). Print the final saved path on its own line prefixed with IMAGE_PATH:' 2>&1 | tail -30
```

The script's contract:
- `IMAGE_OK <abs_path>` on stdout + exit 0 → parse the path, it's the saved file.
- `IMAGE_FAIL <reason>` + non-zero exit → relay the reason to the user.

## Step 4: Verify and show

1. Confirm the file is a PNG: `file "<path>"`.
1. **Open the image with your image-capable file reader** so it renders inline.
1. Report the saved path and dimensions, and note the folder is untracked
   (suggest `.gitignore` if inside a repo and the user doesn't want binaries in git).
1. If the result misses the brief, iterate with ONE targeted change per retry —
   re-state the parts that were correct as invariants.

## Error handling

1. `IMAGE_FAIL ... stalled` (exit 124) → re-run once; if persistent, simplify
   the prompt or check `~/.codex/logs/`.
1. `IMAGE_FAIL no image produced` → the script already searched
   `~/.codex/generated_images/`; show the user the codex tail it printed to stderr.
1. Auth errors → "Run `codex login` to re-authenticate."
1. Content-policy refusal → relay verbatim what codex reported; do NOT silently
   rewrite the prompt to dodge moderation.

## gpt-image-2 reference (for shaping prompts)

Facts as of 2026-06 (OpenAI docs + the codex imagegen skill):

1. **Model**: `gpt-image-2` — strong instruction following, dense/multilingual
   text rendering, photorealism, accurate label/heading text.
1. **Sizes**: `auto` or any `WIDTHxHEIGHT` where **both edges are multiples of
   16**, max edge ≤ 3840px, aspect ≤ 3:1, total pixels between 655,360 and
   8,294,400. Useful 16:9 picks (both edges ÷16): **1536×864**, **2560×1440**,
   **3840×2160** (4K, the max). Note 1920×1080 is *not* valid (1080 isn't ÷16).
1. **Quality**: `low`/`medium`/`high`/`auto`. (Irrelevant to cost when going
   through codex ChatGPT auth, which bills the subscription, not per-image.)
1. **No native transparency**: gpt-image-2 has no `background=transparent`. For
   cutouts, generate on a flat `#00ff00` chroma-key background and strip it with
   `~/.codex/skills/.system/imagegen/scripts/remove_chroma_key.py`.
1. **Direct API fallback**: codex bundles
   `~/.codex/skills/.system/imagegen/scripts/image_gen.py`
   (`generate`/`edit`/`generate-batch`, defaults to gpt-image-2). Only use it
   when the user explicitly wants API-level control (exact size, masks, batch)
   and has `OPENAI_API_KEY` set.

## Important rules

1. Never overwrite an existing asset — version siblings (`hero-v2.png`).
1. Present codex's output and the final image faithfully; iterate only on the
   user's direction.
1. Don't substitute SVG/HTML placeholders when the user asked for a raster
   image, and vice versa.
