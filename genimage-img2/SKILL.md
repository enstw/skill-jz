---
name: genimage-img2
description: >
  Generate or edit a raster image specifically with OpenAI gpt-image-2. Prefer
  a native tool only when the caller can confirm it uses gpt-image-2; otherwise
  use the bundled Codex CLI wrapper. Use for image,
  illustration, hero, banner, social card, mockup, or gpt-image requests. Not
  for SVG/vector/code-native graphics.
---

# genimage-img2

Generate one project-ready raster image specifically with **OpenAI
gpt-image-2** while adapting to the caller's capabilities. This skill may be
used by Codex or by another AI agent; its model identity must not drift.

## Choose the execution path

Use the first available path:

1. **Confirmed native gpt-image-2 tool — preferred.** If the current runtime
   exposes an image-generation tool and its contract explicitly identifies
   OpenAI `gpt-image-2` (for example Codex `image_gen`), call it directly.
2. **Portable Codex CLI fallback.** When the native tool uses Gemini, another
   model, or an unknown model, do not use it. Run this skill's `gen-image.sh`;
   it delegates generation to an authenticated Codex CLI gpt-image-2 path.
3. **No usable renderer.** Return `IMAGE_FAIL` with the missing capability or
   authentication reason so an orchestrator can try another renderer.

Never treat an arbitrary native image tool as equivalent: Gemini, nano banana,
and model-unknown tools violate this skill's gpt-image-2 contract. Conversely,
never shell out to `codex exec` from an agent that already has a confirmed
native gpt-image-2 tool. In particular, Codex must not start a nested Codex
app-server merely to reach its own built-in `image_gen` tool.

## Native path

1. Shape the user's request into a concise production prompt: intended use,
   subject, composition, style, palette, exact text, and exclusions.
1. Generate directly with the runtime's native image tool.
1. Inspect the returned image for composition, text accuracy, and requested
   invariants.
1. For a project asset, copy the generated file from the runtime-managed
   output directory into the requested workspace path. Do not assume the tool
   accepts a destination-path argument.
1. Do not overwrite an existing asset unless explicitly requested; otherwise
   use a versioned sibling.
1. Report `IMAGE_OK <absolute-workspace-path>` to an orchestrating workflow.

For edits, first load a local target into the current runtime's image context,
then call the native tool in edit mode. Preserve all unrequested details.

## Portable CLI fallback

Use this path after establishing that the caller has no confirmed native
gpt-image-2 tool. The presence of a different native image model does not
disable this fallback.

Pre-flight:

```sh
command -v codex >/dev/null || echo "CODEX_MISSING"
[ -f "${CODEX_HOME:-$HOME/.codex}/auth.json" ] || \
  [ -n "$OPENAI_API_KEY" ] || [ -n "$CODEX_API_KEY" ] || echo "AUTH_MISSING"
```

Generate:

```sh
<skill-dir>/gen-image.sh \
  "<description>" \
  "<workspace-output.png>" \
  "<size/aspect hint>"
```

The wrapper emits `IMAGE_OK <absolute-path>` on success or
`IMAGE_FAIL <reason>` on failure. Allow up to ten minutes. It supports
`IMG2_TIMEOUT`, falling back to `GENIMAGE_TIMEOUT` and then 600 seconds.

The wrapper is intentionally retained for non-Codex hosts and agents without
a confirmed native gpt-image-2 tool. It is not the default path for Codex.

## Prompt and output rules

1. Preserve the user's requested content; add only details that materially
   improve composition or production fitness.
1. Quote required in-image text verbatim and minimize other text.
1. Generate one image per call; distinct assets require distinct calls.
1. Use raster generation for raster requests; do not substitute SVG, HTML, or
   canvas placeholders.
1. Inspect the final PNG with an image-capable viewer and confirm its file type
   and dimensions.
1. Keep project-referenced assets inside the workspace, not only in a runtime
   cache or generated-images directory.
1. On policy or authentication failure, report the real error. Do not silently
   switch providers or weaken the request.
