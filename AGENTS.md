# AGENTS.md

Personal collection of AI-agent skills. One folder per skill; each `SKILL.md` is the source of truth.

## Skills

- `flush/SKILL.md` — end-of-session project handoff: update repo state, commit, push.
- `sync/SKILL.md` — lightweight git sync. Pushes already-committed work, fast-forwards when remote is ahead and tree is clean, warns on dirty/untracked. Workspace mode: if cwd is a parent of repo subfolders, runs sync on each and aggregates. Never commits, merges, rebases, or force-pushes. Slash `/sync`. Pairs with `/flush`.
- `clear-memory/SKILL.md` — migrate the agent's per-project session memory into the repo's own files, then clear the store. Three-way triage per entry (migrate / drop with reason / ask the user for personal or cross-project facts); clearing requires the migrated content to be committed first; only ever deletes files inside the memory store. The explicit cleanup counterpart `/flush` refuses to perform. Slash `/clear-memory`.
- `init-agents/SKILL.md` — initialize a directory with AI-agnostic agent context (`AGENTS.md` canonical + pointers from agent-specific instruction files). Description-triggered, so no slash collision with the built-in `/init`.
- `recommend/SKILL.md` — pause and surface direction-level recommendations or refactors. Slash `/recommend` plus self-triggers on drift signals.
- `self-evaluate/SKILL.md` — estimate PDCA loops remaining before the work is finished. Cost-driven, phase-agnostic. Investigates (code/env/smoke/web) before estimating. Slash `/self-evaluate`.
- `robust-web-fetch/SKILL.md` — fetch web source material when ordinary fetch tools are insufficient: PDFs, HTML, text, rendered pages, archived copies, and CDN-blocked sources. Description-triggered.
- `pdf-to-markdown/SKILL.md` — convert any PDF (born-digital, scanned, or mixed) to Markdown; covers extract/convert/OCR/cite asks and explicitly preempts ad-hoc pymupdf scripts. Self-contained: bundles `pdf2md.py` (tiered pymupdf4llm → raw text → OCR pipeline) as the cheap default plus a page-combine helper, and falls back to vision transcription when the text layer is unrecoverable. Description-triggered. (Renamed from `transcribe-pdf`.)
- `genimage-img2/SKILL.md` — generate or edit ONE image with gpt-image-2 via the Codex CLI. Bundles `gen-image.sh`: binary+auth gate, timeout wrapper, and the shared renderer contract (`gen-image.sh "<prompt>" <out.png> "<size>"` → `IMAGE_OK <path>` / `IMAGE_FAIL <reason>`) that deck/batch workflows loop over. Pre-condition: `codex` installed + `codex login`. Slash `/genimage-img2`.
- `genimage-nb/SKILL.md` — generate ONE image with nano banana (Gemini) via the agy CLI; `gen-image.sh` honors the same contract as genimage-img2 (drop-in interchangeable). Encodes agy's probed quirks: scratch-dir cwd (absolute cp target), JPEG artifacts (`sips` → PNG), stdout held open by lingering children (redirect, never pipe). Pre-condition: `agy` installed + logged in. Slash `/genimage-nb`.
- `genimage-canvas/SKILL.md` — draw ONE designed image: `gen-image.sh` invokes Claude Code's stock canvas-design skill to author an HTML composition, then rasterizes with browser-cdp's `shot.sh` — exact on-image text, CJK-safe. Depends on authenticated `claude` + stock canvas-design + browser-cdp; same `gen-image.sh` name/args/IMAGE_OK contract as genimage-img2/genimage-nb (all three honor `GENIMAGE_TIMEOUT`). Slash `/genimage-canvas`.
- `yt2sub/SKILL.md` — download and transcribe YouTube videos or local audio files (yt-dlp + faster-whisper). Slash `/yt2sub`.
- `browser-cdp/SKILL.md` — the single entry point for browser work. EXPLORE/QA live pages through the installed gstack browse daemon (navigate, click, fill, assert, before/after diff, console/network inspection, responsive checks); SEE/render through that daemon or the hardened `scripts/shot.sh` + `cdp-shot.mjs` fallback; DRIVE repeatable automation through copy-in `templates/find-browser.mjs` + `templates/cdp-client.mjs`; and PROVISION a user-space Chromium with `scripts/provision.sh` when none works. The skill itself owns backend selection, so callers do not separately invoke gstack or launch a competing Chromium. Absorbed the former browser-screenshot and headless-chromium skills. `scripts/` must stay shipped — `genimage-canvas/gen-image.sh` calls `shot.sh` path-to-path. Preempts `--headless --screenshot` one-liners (149+ writes nothing), `npm i puppeteer/playwright`, fresh CDP clients, and `sudo apt install chromium`. Description-triggered + `/browser-cdp`.
- `browser-e2e/SKILL.md` — give any web app a real-browser e2e suite with zero test dependencies: the e2e *method* layered on browser-cdp's client templates. Bundles the example suite, the suite taxonomy (pure-node / self-contained / server-backed), the verdict contract, and the dead-server rule for service-worker offline testing (emulation never reaches SWs). Prescribes a per-project overlay pattern (the bookworm repo ships the exemplar as `.claude/skills/e2e`); project overlays live in their repos, not here. Description-triggered + `/browser-e2e`. Depends on browser-cdp (seeding copies its templates path-to-path).
- `repo-publish/SKILL.md` — publish or harden a GitHub repo as a complete presence: pre-publish content/history audit and public-or-private decision, README/metadata/images, plus a reusable GitHub security baseline for secret/dependency scanning, branch/PR policy, CI self-bypass, immutable Actions, least-privilege releases, protected tags, SemVer, solo-maintainer exceptions, and post-change verification. Pre-condition: `gh` authenticated. Description-triggered + `/repo-publish`.

## Conventions

- **Descriptions preempt hand-rolling.** Agents default to writing a quick ad-hoc script instead of loading a skill, so a tool-wrapping skill's `description` must trigger on the *task* ("needs text out of a PDF"), not on the failure of the obvious approach ("when curl is insufficient") — by the time the agent notices the failure, it's already deep in its own script. Name the ad-hoc script the agent would otherwise write (pymupdf snippet, curl retry loop, `--headless --screenshot` one-liner, yt-dlp + whisper pipe) and state why the bundled path already wins. `pdf-to-markdown` set the pattern; `browser-cdp`, `robust-web-fetch`, and `yt2sub` follow it.
- **AI-agnostic output.** Skill bodies and the docs they write into user repos use agent-neutral language. Don't bake tool-specific paths or instructions into a skill's body. Frontmatter (`allowed-tools`, `user-invocable`, etc.) is runner-specific metadata; keep that as the only agent-specific surface.
- **One skill per top-level folder.** Add new skills as `<name>/SKILL.md`. Link them from `README.md` and from this file.
- **Solo-repo workflow.** Direct commits and pushes. No PR step.
- **Handoff-first for `/flush`.** Let the agent decide what project state matters. Don't create docs or commits just to record that nothing happened.
- **No automatic cache wipe in `/flush`.** It's a durable handoff workflow, not a cache deletion routine.

## Layout

- `flush/`, `sync/`, `clear-memory/`, `init-agents/`, `recommend/`, `self-evaluate/`, `robust-web-fetch/`, `pdf-to-markdown/`, `browser-cdp/`, `browser-e2e/`, `genimage-img2/`, `genimage-nb/`, `genimage-canvas/`, `yt2sub/`, `repo-publish/`, ... — one folder per skill.
- `README.md` — outward-facing description and install instructions.
- `AGENTS.md` — this file (orientation for any agent working on the repo).
- `SKILLS-CLI.md` — how this repo stays compatible with the agent-agnostic `skills` CLI (agentskills.dev); re-verify with `npx -y skills add enstw/skill-jz -l` after structural changes.
- `TODO.md` — open items.

## Install

See `README.md` for the AI-agnostic installation prompts. To install one skill, symlink its folder into the agent's global-skills directory. To install the full collection, symlink every top-level folder that contains a `SKILL.md`, replacing stale symlinks but not real directories or files without confirmation.
