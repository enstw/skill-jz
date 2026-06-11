---
name: codex-image
description: >
  Generate or edit images with OpenAI gpt-image-2, driven through the Codex
  CLI's built-in imagegen skill. PRE-CONDITION: the `codex` CLI must be
  installed and authenticated (`codex login`; a ChatGPT subscription is
  enough — no OPENAI_API_KEY needed). Use when asked to "generate an image",
  "make an illustration/logo/hero/mockup", "gpt-image-2", "codex image", or
  to edit/restyle an existing image into a new bitmap asset. Not for
  SVG/vector/code-native graphics — build those directly instead.
---

# /codex-image — Generate images with gpt-image-2 via Codex

Wraps `codex exec` so any coding agent can produce bitmap assets with
**gpt-image-2** (OpenAI's current image model). Codex's built-in `image_gen`
tool does the generation server-side using ChatGPT-subscription auth, so this
works without `OPENAI_API_KEY`.

**Pre-condition:** the Codex CLI must be installed and authenticated. Step 1
verifies this and stops with instructions if not — never skip it.

## Usage

1. `/codex-image <description>` — generate, save to `./generated-images/`
1. `/codex-image <description> --out <folder>` — generate, save to `<folder>`
1. `/codex-image edit <path/to/image> <instructions>` — edit an existing image

## Step 1: Pre-flight (the pre-condition gate)

```bash
command -v codex >/dev/null || echo "CODEX_MISSING"
[ -f "${CODEX_HOME:-$HOME/.codex}/auth.json" ] || [ -n "$OPENAI_API_KEY" ] || [ -n "$CODEX_API_KEY" ] || echo "AUTH_MISSING"
```

1. `CODEX_MISSING` → stop: "Codex CLI not found. Install: `pnpm add -g @openai/codex`, then `codex login`."
1. `AUTH_MISSING` → stop: "Run `codex login` first (ChatGPT account is enough — no API key needed)."

## Step 2: Resolve inputs

1. **Description** — the user's prompt, passed through near-verbatim. If it is
   generic, lightly structure it (subject, style/medium, composition,
   lighting, constraints) but do not invent objects, brands, or text the user
   didn't imply. Quote any required in-image text verbatim.
1. **Destination folder** — `--out <folder>` if given, else `./generated-images/`
   in the current project. **Must be inside the current working directory** —
   codex runs with a workspace-write sandbox and cannot copy files outside it.
   If the user wants a path outside CWD, let the image land in
   `~/.codex/generated_images/<session>/` (codex reports the path) and `cp` it
   yourself afterwards.
1. **Aspect / quality hints** — fold into the prompt text (e.g. "landscape
   16:9", "portrait", "high detail"). Square renders fastest. Do not invent
   CLI flags; the built-in tool takes prompt text only.
1. **Edit mode** — if the user wants to edit a local image, tell codex to load
   it first with its `view_image` tool, then edit. State invariants explicitly
   ("change only X; keep Y unchanged").

## Step 3: Run

Generate (one shell call; allow up to 10 minutes — rendering takes 1–3 min):

```bash
codex exec -s workspace-write 'Use your built-in generateimage (imagegen) skill to generate one image: <DESCRIPTION>. <ASPECT/QUALITY HINTS>. Save the output PNG into <DEST_FOLDER> in this repository (create the folder if needed). Print the final saved path on its own line prefixed with IMAGE_PATH:' 2>&1 | tail -30
```

Edit:

```bash
codex exec -s workspace-write 'Load <IMAGE_PATH_IN> with your view_image tool, then use your built-in generateimage (imagegen) skill in edit mode: <EDIT_INSTRUCTIONS>. Change only what was asked; keep everything else unchanged. Save the result as a new versioned file next to the original (never overwrite). Print the final saved path on its own line prefixed with IMAGE_PATH:' 2>&1 | tail -30
```

Notes:

1. `-s workspace-write` is required — the default read-only sandbox blocks the
   final `cp` into the repo (generation itself still works; the file just
   stays under `~/.codex/generated_images/`).
1. The `IMAGE_PATH:` line is the contract — parse it from the output.
1. Multiple distinct assets → one `codex exec` call per asset, not one big
   prompt.

## Step 4: Verify and show

1. Confirm the file exists and is a PNG (`file <path>`).
1. **Open the image file with your image-capable file reader** so it renders
   inline for the user.
1. Report: saved path, dimensions, and that the folder is untracked (suggest
   `.gitignore` if inside a repo and the user doesn't want binaries in git).
1. If the result misses the brief, iterate with a single targeted change per
   retry — re-state the parts that were correct as invariants.

## Error handling

1. Timeout / stall → re-run once; if persistent, simplify the prompt or check
   `~/.codex/logs/`.
1. Output contains no `IMAGE_PATH:` → search
   `~/.codex/generated_images/` for files newer than the run start; if found,
   copy into the destination yourself.
1. Auth errors in output → "Run `codex login` to re-authenticate."
1. Content-policy refusal → tell the user verbatim what codex reported; do not
   silently rewrite the prompt to dodge moderation.

## gpt-image-2 reference (for shaping prompts)

Facts as of 2026-06 (source: OpenAI docs + the codex imagegen skill):

1. **Model**: `gpt-image-2` — OpenAI's state-of-the-art image generation and
   editing model. Strong instruction following, dense/multilingual text
   rendering, photorealism, and product shots with accurate label text.
1. **Endpoints** (direct API path): `v1/images/generations` and
   `v1/images/edits`. Up to 16 reference images per edit request. Always uses
   high input fidelity (no `input_fidelity` knob).
1. **Sizes**: `auto` or any `WIDTHxHEIGHT` where both edges are multiples of
   16, max edge ≤ 3840px, aspect ratio ≤ 3:1, total pixels between 655,360
   and 8,294,400. Common picks: 1024x1024 (fastest), 1536x1024, 1024x1536,
   2048x2048, 3840x2160 (4K landscape), 2160x3840 (4K portrait).
1. **Quality**: `low` / `medium` / `high` / `auto`. Low ≈ $0.006 per 1024²
   image, medium ≈ $0.05, high ≈ $0.21 (API token-based pricing; irrelevant
   when going through codex ChatGPT auth, which bills the subscription).
1. **No native transparency**: `gpt-image-2` does not support
   `background=transparent`. For cutouts: generate on a flat `#00ff00`
   chroma-key background and remove it locally (codex has a helper at
   `~/.codex/skills/.system/imagegen/scripts/remove_chroma_key.py`), or fall
   back to `gpt-image-1.5 --background transparent` via codex's CLI mode
   (needs `OPENAI_API_KEY` — ask the user first).
1. **Direct API fallback**: codex bundles a CLI at
   `~/.codex/skills/.system/imagegen/scripts/image_gen.py`
   (`generate` / `edit` / `generate-batch`) defaulting to `gpt-image-2`. Only
   use it when the user explicitly wants API-level control (exact size,
   quality, masks, batch) and has `OPENAI_API_KEY` set.

## Important rules

1. Never overwrite an existing asset — version siblings (`hero-v2.png`).
1. Present codex's output and the final image faithfully; iterate only on the
   user's direction.
1. Don't substitute SVG/HTML placeholders when the user asked for a raster
   image, and vice versa — repo-native vector assets should be edited
   directly, not regenerated as bitmaps.
