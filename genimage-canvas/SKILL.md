---
name: genimage-canvas
description: >
  Draw a single designed image (poster, cover, slide, hero, art piece) by
  shelling out to Claude Code's stock canvas-design skill to author an exact
  HTML/CSS/SVG composition, then rasterizing that HTML to PNG with the
  browser-cdp skill. PRE-CONDITION: the `claude` CLI must be installed
  and authenticated, with the stock canvas-design skill available at
  ~/.claude/skills/canvas-design. Same IMAGE_OK/IMAGE_FAIL contract as
  /genimage-img2 and /genimage-nb — the drop-in interchangeable hand-drawn
  renderer. Use when asked to "draw/design an image by
  hand", "genimage-canvas" (old name "img-canvas"), or when exact text matters
  more than photorealism.
user-invocable: true
---

# /genimage-canvas — one hand-drawn image via Claude canvas-design

Produces one bitmap by **drawing it**, not generating it. The wrapper script
`gen-image.sh` shells out to `claude -p`, asks Claude Code's stock
**canvas-design** skill to author a fixed-size HTML/CSS/SVG composition, saves
that editable `.html` beside the output, then rasterizes it through the
**browser-cdp** skill's `shot.sh`.

This mirrors the sibling primitive shape:

```
genimage-img2     prompt -> gpt-image-2 -> PNG
genimage-nb       prompt -> agy/nano-banana -> PNG
genimage-canvas   prompt -> claude/canvas-design -> HTML -> PNG
```

All three share the parseable `IMAGE_OK` / `IMAGE_FAIL` contract, so any
deck or batch workflow can call them interchangeably.

## Usage

1. `/genimage-canvas <description>` — design + draw, save to
   `./generated-images/<slug>.png` (source kept beside it as `<slug>.html`)
1. `/genimage-canvas <description> --out <path.png>` — explicit output path
1. Re-render after an edit: tweak the `.html`, re-run `gen-image.sh` — same
   image path, deterministic.

## Step 1: Pre-flight

```bash
command -v claude >/dev/null || echo "CLAUDE_MISSING"
[ -f "$HOME/.claude/skills/canvas-design/SKILL.md" ] || echo "CANVAS_DESIGN_MISSING"
[ -x "$HOME/.claude/skills/browser-cdp/scripts/shot.sh" ] || \
  [ -x "$HOME/.codex/skills/browser-cdp/scripts/shot.sh" ] || \
  echo "BROWSER_CDP_MISSING"
```

(`gen-image.sh` additionally accepts a sibling checkout — a
`browser-cdp/scripts/shot.sh` next to this skill's folder — plus the legacy
`browser-screenshot` locations, so a `BROWSER_CDP_MISSING` probe result can
still succeed when the whole collection is linked together.)

`gen-image.sh` checks these itself and emits `IMAGE_FAIL`, so this probe is
optional.

1. `CLAUDE_MISSING` → stop: "Claude Code CLI not found — install Claude Code."
1. `CANVAS_DESIGN_MISSING` → **stop**: "the canvas-design skill is required
   because `gen-image.sh` asks Claude to use its stock design skill."
1. `BROWSER_CDP_MISSING` → **stop**: "the browser-cdp skill is
   required because its shot.sh rasterizes the HTML."

Useful env overrides:

- `GENCANVAS_CLAUDE_BIN` — Claude Code binary path.
- `GENCANVAS_SHOT` — explicit `browser-cdp/scripts/shot.sh` path.
- `GENCANVAS_TIMEOUT` — authoring timeout in seconds; falls back to the
  family-wide `GENIMAGE_TIMEOUT` (all three genimage primitives honor it),
  then `600`.

## Step 2: Resolve inputs

1. **Description** — pass the user's brief near-verbatim. If generic, lightly
   structure it with subject, style, composition, palette, and exact text
   requirements, but do not invent brands, people, or in-image text.
1. **Output path** — `--out <path.png>` if given, else
   `./generated-images/<slug>.png`. The wrapper writes the editable source
   beside it as `<slug>.html`.
1. **Size** — third arg to `gen-image.sh`, default `1920x1080`. Pass exact
   pixel dimensions when a deck, card, or social image workflow requires
   them. The arg is hint-tolerant for sibling interchangeability: the first
   `WxH` token in it wins, and a freeform hint with none (e.g. "landscape
   16:9, high detail") falls back to `1920x1080`.

For CJK or house fonts, include that in the brief. The Claude subprocess writes
markup; exact text is the reason to use this primitive. Fonts resolve without
copying files: the subprocess is told to `@font-face` canvas-design's bundled
`canvas-fonts/` by absolute path (the rasterizer runs with
`--allow-file-access-from-files`) and to fall back to system CJK fonts
(PingFang on macOS). A house font is the one case that needs a file beside the
HTML — copy it there yourself and name it in the brief.

## Step 3: Run

One call. Let the Bash call run up to ~10 minutes.

```bash
<path-to-skill>/gen-image.sh \
  "<DESCRIPTION>" \
  "generated-images/<slug>.png" \
  "1920x1080"
```

The script's contract:

- `IMAGE_OK <abs_path>` on stdout + exit 0 → parse the path, it is the saved PNG.
- `IMAGE_FAIL <reason>` + non-zero exit → relay the reason to the user.

The editable HTML source is saved beside the PNG with the same basename. The
subprocess may also leave a design-philosophy `.md` beside it — that is part
of the canvas-design method, keep it with the source.

## Re-rendering HTML

To re-render after manual edits, pass the HTML source as the first argument:

```bash
<path-to-skill>/gen-image.sh \
  "generated-images/<slug>.html" \
  "generated-images/<slug>.png" \
  "1920x1080"
```

In this mode `gen-image.sh` skips Claude and only runs the rasterize step.

## Step 4: Verify and show

1. **Open the PNG with your image-capable file reader**: spacing, contrast,
   edge clipping, and exact text matter.
1. Confirm dimensions match the request (`file "<path>"`).
1. Report the saved path and note the `.html` source location for future
   edits.
1. If something is off, edit the HTML and re-run — iterate on source,
   never retouch the PNG.

## Error handling

1. `IMAGE_FAIL claude CLI not found` → install Claude Code or set
   `GENCANVAS_CLAUDE_BIN`.
1. `IMAGE_FAIL Claude canvas-design skill missing` → install/link Claude's
   stock `canvas-design` skill under `~/.claude/skills/canvas-design`.
1. `IMAGE_FAIL claude did not author HTML` / `claude exited N` / `claude
   stalled` → the IMAGE_FAIL line names the full subprocess log; read it.
   Usually auth, permissions, or a refusal to write the requested file.
1. `IMAGE_FAIL browser-cdp skill missing` → install/link the
   dependency or set `GENCANVAS_SHOT`.
1. `IMAGE_FAIL rasterize failed` → open the `.html` in a browser or run
   `shot.sh --dump` to find the rendering issue; fix the source and re-render.

## Important rules

1. Never overwrite an existing asset the user cares about — version siblings
   (`hero-v2.png` + `hero-v2.html`).
1. Text on the image is set in markup — it must be **exact**, in the language
   requested; that exactness is this primitive's whole advantage.
1. Don't hand-draw what the user asked to AI-generate (that's /genimage-img2 or
   /genimage-nb), and vice versa.
