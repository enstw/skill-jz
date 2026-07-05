---
name: genimage-nb
description: >
  Generate a single image with nano banana (Gemini's image model), driven
  through the agy (Antigravity) CLI's built-in generate_image tool.
  PRE-CONDITION: the `agy` CLI must be installed and authenticated (run agy
  once interactively and log in — billed to the Gemini side, no API key
  needed). Use when asked to "generate an image with nano banana / gemini /
  agy", or "genimage-nb" (old name "img-nb"). Same CLI contract as /genimage-img2 (gpt-image-2) — this is the
  interchangeable per-slide primitive that /deck-image can call once per
  slide. Not for SVG/vector/code-native graphics — build those directly
  instead.
user-invocable: true
---

# /genimage-nb — one nano-banana image via agy

Produces one bitmap with **nano banana** (Gemini's image model) by shelling
out to `agy -p` (Antigravity CLI print mode). The agent's `generate_image`
tool does the generation server-side under agy's Google login, so no API key
is required.

The whole call is wrapped in `gen-image.sh` (in this skill folder), which is
the single source of truth for the agy invocation. It mirrors
`genimage-img2/gen-image.sh` — a binary + auth gate, a `gtimeout`/`timeout` wrapper,
stdout redirected to a log file, and the same parseable contract — so /genimage-img2
and /genimage-nb are drop-in interchangeable renderers for **/deck-image**.

## Usage

1. `/genimage-nb <description>` — generate, save to `./generated-images/<slug>.png`
1. `/genimage-nb <description> --out <path.png>` — generate, save to an explicit path

## Step 1: Pre-flight (the pre-condition gate)

`gen-image.sh` checks this itself and exits with a clear `IMAGE_FAIL` line,
but you can probe first:

```bash
command -v agy >/dev/null || echo "AGY_MISSING"
[ -f "$HOME/.gemini/antigravity-cli/antigravity-oauth-token" ] || echo "AUTH_MISSING"
```

1. `AGY_MISSING` → stop: "agy CLI not found — install the Antigravity CLI first."
1. `AUTH_MISSING` → stop: "Run `agy` once interactively and log in."

## Step 2: Resolve inputs

1. **Description** — the user's prompt, near-verbatim. If generic, lightly
   structure it (subject, style/medium, composition, lighting, constraints)
   but do not invent objects, brands, or text the user didn't imply. Quote any
   required in-image text verbatim, in the language requested.
1. **Output path** — `--out <path.png>` if given, else
   `./generated-images/<slug>.png`. Any path works: the script hands agy an
   *absolute* target (agy's own cwd is its scratch dir, not yours) and
   recovers the artifact itself if the copy was refused.
1. **Size / aspect hint** — third arg to the script, folded into the prompt as
   text (generate_image takes prompt text only). Nano banana honors aspect
   loosely; the probe run returned 1376×768 for "landscape 16:9".

## Step 3: Run

One call. Rendering is fast (~30–60 s in probes); still allow up to ~10
minutes on the Bash call (`timeout: 600000`).

```bash
<path-to-skill>/gen-image.sh \
  "<DESCRIPTION>" \
  "generated-images/<slug>.png" \
  "landscape 16:9 aspect ratio, high detail"
```

Env overrides: `IMGNB_TIMEOUT` caps the run in wall-clock seconds (falls back
to the family-wide `GENIMAGE_TIMEOUT`, then 600).

The script's contract (same as /genimage-img2):

- `IMAGE_OK <abs_path>` on stdout + exit 0 → parse the path, it's the saved file.
- `IMAGE_FAIL <reason>` + non-zero exit → relay the reason to the user.

The delivered file is a real PNG: the raw nano-banana artifact is typically
JPEG, and the script converts with `sips` (macOS built-in) after recovery.

## Step 4: Verify and show

1. Confirm the file is a PNG: `file "<path>"`.
1. **Open the image with your image-capable file reader** so it renders inline.
1. Report the saved path and dimensions, and note the folder is untracked
   (suggest `.gitignore` if inside a repo and the user doesn't want binaries
   in git).
1. If the result misses the brief, iterate with ONE targeted change per retry —
   re-state the parts that were correct as invariants.

## Error handling

1. `IMAGE_FAIL ... stalled` (exit 124) → re-run once; if persistent, check
   `~/.gemini/antigravity-cli/log/`.
1. `IMAGE_FAIL no image produced` → the script already searched agy's
   `scratch/` and `brain/` dirs; show the user the agy tail it printed to
   stderr.
1. Auth errors → "Run `agy` interactively to re-authenticate."
1. Content-policy refusal → relay verbatim what agy reported; do NOT silently
   rewrite the prompt to dodge moderation.

## How it works (agy specifics, probed 2026-07-02 on agy 1.0.13)

1. `agy -p "<prompt>"` runs the full agent non-interactively;
   `generate_image` needs no permission approval, and `cp`/`mkdir` are on the
   user's agy permission allow-list, so the agent can deliver the file to the
   absolute target itself.
1. The raw artifact lands in `~/.gemini/antigravity-cli/brain/<conversation>/`
   (JPEG, descriptive name); the agent's own cwd maps to
   `~/.gemini/antigravity-cli/scratch/`. The script's mtime-fenced fallback
   searches both.
1. agy's stdout can be held open by a lingering child after the main process
   exits — the script therefore redirects to a log file and never pipes.
1. **Parallel runs:** the absolute per-call target makes concurrent calls safe
   in the normal path; only the last-resort fence search could cross-match
   overlapping runs. Cap at ~3 concurrent (as /deck-image does) and re-run
   any slide that looks wrong.

## Important rules

1. Never overwrite an existing asset the user cares about — version siblings
   (`hero-v2.png`).
1. Present agy's output and the final image faithfully; iterate only on the
   user's direction.
1. Don't substitute SVG/HTML placeholders when the user asked for a raster
   image, and vice versa.
