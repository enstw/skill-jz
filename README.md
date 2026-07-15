# skill-jz

A personal collection of AI-agent skills. Each top-level directory is one skill; the `SKILL.md` inside is the source of truth.

## Skills

- **[flush](./flush/)** — End-of-session project handoff. Updates the repo with current project state, commits, and pushes so work can resume from another machine or session.
- **[sync](./sync/)** — Lightweight git sync. Pushes already-committed work when it's safe, fast-forwards when the remote is ahead and the tree is clean, and warns about untracked/uncommitted files. Never commits, merges, rebases, or force-pushes. If the current directory is a parent of multiple git repos (e.g. a workspace folder), runs the same sync on each child repo and reports per repo plus an aggregate. Slash-invocable as `/sync`; pairs with `/flush` (flush records and commits, sync pushes).
- **[init-agents](./init-agents/)** — Initialize a directory with AI-agnostic agent context: `AGENTS.md` as the canonical file, plus short pointers from agent-specific instruction files such as `CLAUDE.md` and `GEMINI.md`. Description-triggered (no slash command), so it doesn't collide with Claude Code's built-in `/init`.
- **[recommend](./recommend/)** — Pause the current trajectory, surface direction-level recommendations, and offer to refactor. Slash-invocable as `/recommend`; also self-triggers when the agent senses drift (scope creep, naming churn, half-finished implementations).
- **[self-evaluate](./self-evaluate/)** — Estimate how many PDCA (plan-do-check-act) loops remain before the work is finished. Cost-driven and phase-agnostic: invokable pre-implementation, mid-implementation, or post-test-failure. The agent investigates (reads code, smoke-tests, checks env, web-searches) before estimating so the number is grounded in evidence. Slash-invocable as `/self-evaluate`.
- **[robust-web-fetch](./robust-web-fetch/)** — Fetch web source material when ordinary `curl`, `wget`, or `web_fetch` is insufficient, including PDFs, HTML pages, text files, rendered pages, archived copies, and CDN-blocked sources. Description-triggered (no slash command).
- **[pdf-to-markdown](./pdf-to-markdown/)** — Convert any PDF (born-digital, scanned, or mixed) to Markdown: text/table extraction, OCR, and page-accurate transcripts for citation or repeated AI lookup. Self-contained: bundles the offline `pdf2md.py` converter (tiered pymupdf4llm → raw text → OCR pipeline with gibberish detection and CJK support) plus a page-combine helper, with macOS/Homebrew and Ubuntu dependency hints. Uses vision fallback only when the text layer is unrecoverable. Description-triggered. *(Renamed from `transcribe-pdf`.)*
- **[browser-screenshot](./browser-screenshot/)** — Headless screenshot or rendered-DOM dump of any URL or local HTML/SVG file. Routes through the shared gstack browse daemon (`$B`) when installed; falls back to the bundled `scripts/shot.sh`, hardened against the cold-profile hang that makes naive `--headless --screenshot` commands stall or write nothing (one reused profile + GNU `timeout` hard-kill + `Singleton*` lock cleanup). When no browser exists at all, shot.sh auto-provisions one via **headless-chromium**. Description-triggered.
- **[headless-chromium](./headless-chromium/)** — Provision a working user-space headless Chromium on machines with no usable browser: no root, no snap, container-safe. Finds or downloads a playwright headless shell, extracts missing libs via `apt download` + `dpkg -x`, probes whether the kernel sandbox works, and emits a self-contained `BROWSER_BIN` wrapper that shot.sh, raw-CDP scripts, and playwright-core all accept. Idempotent (`scripts/provision.sh`). Description-triggered.
- **[genimage-img2](./genimage-img2/)** — Generate or edit a single image with OpenAI gpt-image-2 via the Codex CLI. Bundles `gen-image.sh` with the shared renderer contract (`IMAGE_OK <path>` / `IMAGE_FAIL <reason>`) that image-deck workflows loop over. Slash-invocable as `/genimage-img2`. **Pre-condition:** `codex` installed and authenticated.
- **[genimage-nb](./genimage-nb/)** — Generate a single image with nano banana (Gemini's image model) via the agy (Antigravity) CLI. `gen-image.sh` is drop-in interchangeable with genimage-img2's (same contract) and encodes agy's quirks: scratch-dir cwd, JPEG artifacts converted to PNG, and safe stdout handling. Slash-invocable as `/genimage-nb`. **Pre-condition:** `agy` installed and logged in.
- **[genimage-canvas](./genimage-canvas/)** — Draw a single designed image (poster, banner, slide) by having `gen-image.sh` invoke Claude Code's stock canvas-design skill to author an HTML composition, then rasterizing it to PNG via browser-screenshot. Exact on-image text (CJK-safe). Same `gen-image.sh` name, args, and contract as genimage-img2/genimage-nb. Slash-invocable as `/genimage-canvas`. **Depends on:** `claude` authenticated with stock `canvas-design`, plus browser-screenshot.
- **[yt2sub](./yt2sub/)** — Download and transcribe YouTube videos or local audio files, using yt-dlp and faster-whisper. Slash-invocable as `/yt2sub`.
- **[repo-publish](./repo-publish/)** — Publish a local folder to GitHub as a complete repo presence: a pre-publish audit (secrets in history, PII, redistribution rights, license) feeding an explicit **public-or-private** decision (private-first when in doubt), a README authored from the folder's real contents, `gh repo create` + description/topics, a README banner and 1280×640 social-preview card rendered via the img primitives, and the social-preview upload step (GitHub has no API for it). Slash-invocable as `/repo-publish`. **Pre-condition:** `gh` installed and authenticated.

## AI-agnostic output

Some `SKILL.md` metadata is runner-specific, such as `allowed-tools` and `user-invocable`; that metadata is the only agent-specific surface. Each skill body instructs the running agent in generic terms, and what the skills *write into user repos* is agent-neutral. The workflow ports to any agent with a similar shape, and the repos these skills touch stay portable across tools and human readers.

## Install

We recommend **linking** skills rather than installing (copying) them. This creates a symbolic link so that whenever you pull updates to this repository, your agent's skills are updated automatically.

### Linking a skill

Ask your AI agent to symlink the skill folder into the directory where it loads global user skills. If your agent has a native CLI (like Gemini CLI), you can run:

```bash
gemini skills link ./flush
```

For other agents, you can use a prompt like:

> **Prompt:** "Please install the skill located in `./flush` by creating a symlink to it in the directory where you load global user skills."

### Linking all skills

To link all skills in this repo, you can ask your agent:

> **Prompt:** "Please link all the skills in this repository. For each folder containing a `SKILL.md`, create a symlink to it in your global skills directory. If you have a native `link` command, use that."

Restart or reload the agent session if the skill list is cached.

### Installing with the `skills` CLI

The repo is also compatible with the agent-agnostic [`skills` CLI](https://agentskills.dev), which vendors a **pinned copy** (updated manually with `npx skills update`) instead of a live symlink:

```bash
npx -y skills add enstw/skill-jz                      # all skills
npx -y skills add enstw/skill-jz --skill flush sync   # pick specific ones
npx -y skills add enstw/skill-jz -g                   # global (user-level) instead of project
```

See [SKILLS-CLI.md](./SKILLS-CLI.md) for how the compatibility works and the trade-offs between the two install methods.

## Requirements

Per skill — see each `SKILL.md`. In general:

- Git, for repo detection and any commit/push step a skill performs.
- `gh` (optional) for repo bootstrapping flows.
- HTTPS pushes to github.com require `gh auth setup-git` to be run once, or another credential helper. Skills never try to fix auth on their own — they report and stop.

## Adding a new skill

One skill per top-level folder. Create `<name>/SKILL.md` with frontmatter and body, link it from this README and from `AGENTS.md`, and follow the AI-agnostic-output rule for anything the skill writes into user repos.
