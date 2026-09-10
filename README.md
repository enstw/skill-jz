# skill-jz

A personal collection of AI-agent skills. Each top-level directory is one skill; the `SKILL.md` inside is the source of truth.

## Skills

- **[flush](./flush/)** — End-of-session project handoff and agent-memory drain. Updates the repo with current project state; migrates the agent's persistent per-project memory into the repo's own files (memory is machine-local, the repo is the durable, portable source of truth — each entry is migrated into the right existing file, dropped with a stated reason, or, when it's personal/cross-project, routed to the home the runner names for such facts and otherwise left in place and reported — never blocking the handoff on a question) and clears the store only after the migrated content is committed; then commits and pushes so work can resume from another machine or session. Also handles a plain "clear my memory" request. Only ever deletes files inside the memory store. Slash-invocable as `/flush`.
- **[sync](./sync/)** — Lightweight git sync. Pushes already-committed work when it's safe, fast-forwards when the remote is ahead and the tree is clean, and warns about untracked/uncommitted files. Never commits, merges, rebases, or force-pushes. If the current directory is a parent of multiple git repos (e.g. a workspace folder), runs the same sync on each child repo and reports per repo plus an aggregate. Slash-invocable as `/sync`; pairs with `/flush` (flush records and commits, sync pushes).
- **[init-agents](./init-agents/)** — Initialize a directory with AI-agnostic agent context: `AGENTS.md` as the canonical file, plus short pointers from agent-specific instruction files such as `CLAUDE.md` and `GEMINI.md`. Description-triggered (no slash command), so it doesn't collide with Claude Code's built-in `/init`.
- **[recommend](./recommend/)** — Pause the current trajectory, surface direction-level recommendations, and offer to refactor. Slash-invocable as `/recommend`; also self-triggers when the agent senses drift (scope creep, naming churn, half-finished implementations).
- **[self-evaluate](./self-evaluate/)** — Estimate how many PDCA (plan-do-check-act) loops remain before the work is finished. Cost-driven and phase-agnostic: invokable pre-implementation, mid-implementation, or post-test-failure. The agent investigates (reads code, smoke-tests, checks env, web-searches) before estimating so the number is grounded in evidence. Slash-invocable as `/self-evaluate`.
- **[robust-web-fetch](./robust-web-fetch/)** — Fetch web source material when ordinary `curl`, `wget`, or `web_fetch` is insufficient, including PDFs, HTML pages, text files, rendered pages, archived copies, and CDN-blocked sources. Description-triggered (no slash command).
- **[pdf-to-markdown](./pdf-to-markdown/)** — Convert any PDF (born-digital, scanned, or mixed) to Markdown: text/table extraction, OCR, and page-accurate transcripts for citation or repeated AI lookup. Self-contained: bundles the offline `pdf2md.py` converter (tiered pymupdf4llm → raw text → OCR pipeline with gibberish detection and CJK support) plus a page-combine helper, with macOS/Homebrew and Ubuntu dependency hints. Uses vision fallback only when the text layer is unrecoverable. Description-triggered. *(Renamed from `transcribe-pdf`.)*
- **[genimage-img2](./genimage-img2/)** — Generate or edit a single image with OpenAI gpt-image-2 via the Codex CLI. Bundles `gen-image.sh` with the shared renderer contract (`IMAGE_OK <path>` / `IMAGE_FAIL <reason>`) that image-deck workflows loop over. Slash-invocable as `/genimage-img2`. **Pre-condition:** `codex` installed and authenticated.
- **[genimage-nb](./genimage-nb/)** — Generate a single image with nano banana (Gemini's image model) via the agy (Antigravity) CLI. `gen-image.sh` is drop-in interchangeable with genimage-img2's (same contract) and encodes agy's quirks: scratch-dir cwd, JPEG artifacts converted to PNG, and safe stdout handling. Slash-invocable as `/genimage-nb`. **Pre-condition:** `agy` installed and logged in.
- **[genimage-canvas](./genimage-canvas/)** — Draw a single designed image (poster, banner, slide) by having `gen-image.sh` invoke Claude Code's stock canvas-design skill to author an HTML composition, then rasterizing it to PNG via browser-cdp's `shot.sh`. Exact on-image text (CJK-safe). Same `gen-image.sh` name, args, and contract as genimage-img2/genimage-nb. Slash-invocable as `/genimage-canvas`. **Depends on:** `claude` authenticated with stock `canvas-design`, plus browser-cdp.
- **[yt2sub](./yt2sub/)** — Download and transcribe YouTube videos or local audio files, using yt-dlp and faster-whisper. Slash-invocable as `/yt2sub`.
- **[browser-cdp](./browser-cdp/)** — The single entry point for browser work: **explore and QA** live pages (navigate, click, fill, assert, before/after diff, console/network inspection, responsive checks) through the installed gstack browse daemon; **see and render** pages (screenshots, DOM dump, local HTML/SVG visual QA) through that daemon or the hardened `scripts/shot.sh` fallback; **automate** repeatable browser jobs with the bundled `find-browser.mjs` + `cdp-client.mjs` templates; and **provision** a user-space Chromium where none exists. The skill owns backend selection, so callers do not invoke a separate gstack skill or launch a competing Chromium. Zero npm dependencies, minimal env footprint. Absorbs the former **browser-screenshot** and **headless-chromium** skills. Description-triggered + `/browser-cdp`.
- **[browser-e2e](./browser-e2e/)** — Give any web app a real-browser e2e test suite with **zero test dependencies**: plain node scripts (node ≥22) driving a headless Chromium over CDP. The e2e *method* layered on **browser-cdp** (which owns the discovery + client templates): an example suite, the suite taxonomy, the JSON verdict contract, and the dead-server rule for service-worker offline testing (network emulation never reaches SWs). Includes an honest "when to use playwright instead" decision rule, and prescribes a per-project overlay pattern: each project keeps its own thin runbook (suite matrix, ports, env) in its repo — the [bookworm](https://github.com/enstw/bookworm) reader ships the exemplar as `.claude/skills/e2e`. Description-triggered + `/browser-e2e`. **Depends on:** browser-cdp.
- **[init-machine](./init-machine/)** — Set up Claude Code's global environment on a new machine (macOS or Ubuntu) from the canonical copies bundled in the skill: lease-based keep-awake hooks (the machine stays awake while the agent works, then the inhibition self-expires) and cross-platform notification chimes. Merges into `~/.claude` without clobbering existing settings. The one deliberately runner-specific skill in this collection — its subject is Claude Code's own config. Slash-invocable as `/init-machine`.
- **[ppng-handoff](./ppng-handoff/)** — Hand a file off to another device or person over the network from a machine the recipient can't reach directly, by streaming it through the hosted [piping-server](https://github.com/nwtgck/piping-server) relay at ppng.io — no account, nothing stored, sender→receiver with backpressure, NAT-friendly. Preempts spinning up `python -m http.server`, uploading to transfer.sh/a pastebin, or committing a file just to move it. The relay path is the only secret (generate a long random one), single-use/one-receiver, and the relay sees plaintext — so encrypt sensitive content first (age/gpg/7z, key out-of-band) or use piping-ui.org for browser E2E. Always hands the user three outputs — an ASCII QR of the URL (`qrencode -t UTF8`, or `uvx --from qrcode qr --ascii` where qrencode is absent) for a phone to scan, a clickable URL for a browser, and the ready-to-run receiving `curl` for a shell. Folds in the macOS Quick Look (`qlmanage`) local-viewer path for the person at this machine. Migrated from the machine's global preferences. Description-triggered + `/ppng-handoff`.
- **[slash-command-autonomous](./slash-command-autonomous/)** — Run a slash command that exists only inside an agent CLI's interactive TUI (e.g. Claude Code's `/artifacts` to list/copy/rename/pin/delete published artifacts) when running headlessly with no tool or flag for it: launch a second, nested agent CLI in a detached `tmux` session and drive its TUI with literal `send-keys` + `capture-pane` read-back (Escape-then-Enter to beat autocomplete; capture between keystrokes because they land intermittently; confirm the target before any destructive key; `kill-session` on every exit). Strictly for pre-authorized actions that merely lack a headless path — never to route around a refusal, a confirmation the user hasn't given, or a capability absent by design, and never as cover for reverse-engineering a service's endpoints or lifting its credentials. Description-triggered.
- **[repo-publish](./repo-publish/)** — Publish or harden a GitHub repository as a complete presence: pre-publish content/history audit and explicit **public-or-private** decision, README and metadata, GitHub security/branch/Actions/release controls, a README banner and 1280×640 social-preview card, and post-change verification. The baseline covers secret scanning, Dependabot, CI self-bypass, least-privilege workflows, immutable Actions, tag protection, release SemVer, and the solo-maintainer review exception. Slash-invocable as `/repo-publish`. **Pre-condition:** `gh` installed and authenticated.

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
