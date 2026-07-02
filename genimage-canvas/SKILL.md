---
name: genimage-canvas
description: >
  Draw a single designed image (poster, cover, slide, hero, art piece) by
  authoring an HTML composition following the canvas-design skill's
  design-philosophy method, then rasterizing it to PNG with the
  browser-screenshot skill. DEPENDS ON both: canvas-design (the authoring
  method — pre-flight STOPS if missing) and browser-screenshot (the
  rasterizer — render.sh fails clearly if missing). Exact on-image text by
  construction — no AI-image garbling, ideal for CJK — no external CLI, no
  cost. Same IMAGE_OK/IMAGE_FAIL contract as /genimage-img2 and /genimage-nb; this is the
  drawn-renderer primitive /deck-image calls per slide. Use when asked to
  "draw/design an image by hand", "genimage-canvas" (old name "img-canvas"), or when exact text matters
  more than photorealism.
---

# /genimage-canvas — one hand-drawn image via canvas-design + browser-screenshot

Produces one bitmap by **drawing it**, not generating it: the agent authors a
fixed-size HTML composition per the **canvas-design** skill's method (design
philosophy first, then visual expression), and `render.sh` (in this skill
folder) rasterizes it headlessly via the **browser-screenshot** skill.

Division of labor — this skill is deliberately thin:

```
canvas-design        HOW to design (philosophy → composition)   ← authoring dependency
genimage-canvas           the workflow + the IMAGE_OK contract       ← THIS skill
browser-screenshot   headless Chrome rasterizer (shot.sh)       ← rendering dependency
```

Versus the sibling primitives: /genimage-img2 and /genimage-nb *generate* (photorealism,
illustration); /genimage-canvas *draws* (designed layouts, typography, exact
text). All three share the contract, so /deck-image can mix them per slide.

## Usage

1. `/genimage-canvas <description>` — design + draw, save to
   `./generated-images/<slug>.png` (source kept beside it as `<slug>.html`)
1. `/genimage-canvas <description> --out <path.png>` — explicit output path
1. Re-render after an edit: tweak the `.html`, re-run `render.sh` — same
   image path, deterministic.

## Step 1: Pre-flight (the dependency gate)

```bash
[ -f "$HOME/.claude/skills/canvas-design/SKILL.md" ] || echo "CANVAS_DESIGN_MISSING"
[ -x "$HOME/.claude/skills/browser-screenshot/scripts/shot.sh" ] || echo "BROWSER_SCREENSHOT_MISSING"
```

1. `CANVAS_DESIGN_MISSING` → **stop**: "the canvas-design skill is required
   (it's the authoring method) — install: copy `skills/canvas-design/` from
   https://github.com/anthropics/skills into `~/.claude/skills/`."
1. `BROWSER_SCREENSHOT_MISSING` → **stop**: "the browser-screenshot skill is
   required (it rasterizes the composition) — link it at
   `~/.claude/skills/browser-screenshot`."

(`render.sh` re-checks both itself: browser-screenshot as a hard
`IMAGE_FAIL`, canvas-design as a stderr `WARN` — an already-authored HTML can
still render, but the warning flags that the method was skipped.)

## Step 2: Author the composition (the canvas-design half)

**Read `~/.claude/skills/canvas-design/SKILL.md` and follow it** — philosophy
first (name the movement, articulate how it manifests in space/form/color),
then express it visually. Constraints that make the result rasterize
correctly:

1. **Fixed-size stage, no scroll**: one wrapper element locked to the target
   pixel size (default 1920×1080; match whatever `WxH` you'll pass to
   `render.sh`), `margin:0`, `overflow:hidden` on body.
1. **Self-contained**: inline CSS/SVG; reference only local files that sit
   beside the HTML (fonts, images). It renders from `file://`.
1. **Fonts**: canvas-design's bundled `canvas-fonts/` are Latin-only. For CJK
   either rely on system fonts (macOS PingFang) or — for project work that
   must match a house look — copy the project's CJK font beside the HTML and
   `@font-face` it. For the thesisbug template that is house-style's ENSFont
   (verified working through render.sh from `file://`):

   ```css
   /* font file copied from <repo>/.agents/skills/house-style/assets/fonts/ */
   @font-face {
     font-family: 'ENS Font';
     src: url('ENSFont.woff2') format('woff2');
     font-weight: 100 900;
     font-style: normal;
   }
   .stage { font-family: 'ENS Font', "PingFang TC", sans-serif; }
   ```
1. **Keep the `.html` source next to the output PNG** — it is the editable
   original; the PNG is a build artifact.

## Step 3: Rasterize

```bash
~/.claude/skills/genimage-canvas/render.sh "<slug>.html" "generated-images/<slug>.png" "1920x1080"
```

The contract (same as /genimage-img2, /genimage-nb):

- `IMAGE_OK <abs_path>` on stdout + exit 0 → the saved PNG.
- `IMAGE_FAIL <reason>` + non-zero exit → relay the reason.

## Step 4: Verify and show

1. **Open the PNG with your image-capable file reader** — a drawn composition
   deserves an eyeball: spacing, contrast, nothing clipped at the edges.
1. Confirm dimensions match the request (`file "<path>"`).
1. Report the saved path and note the `.html` source location for future
   edits.
1. If something is off, edit the HTML and re-run Step 3 — iterate on source,
   never retouch the PNG.

## Error handling

1. `IMAGE_FAIL rasterize failed` → open the `.html` in a browser (or
   `shot.sh --dump` it) to find the rendering error; fix the source.
1. `IMAGE_FAIL browser-screenshot skill missing` → install/link the
   dependency, per Step 1.
1. `WARN canvas-design skill missing` on stderr → the render still ran, but
   go back and do Step 1 properly before authoring anything new.

## Important rules

1. Never overwrite an existing asset the user cares about — version siblings
   (`hero-v2.png` + `hero-v2.html`).
1. Text on the image is set in markup — it must be **exact**, in the language
   requested; that exactness is this primitive's whole advantage.
1. Don't hand-draw what the user asked to AI-generate (that's /genimage-img2 or
   /genimage-nb), and vice versa.
