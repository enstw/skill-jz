# AGENTS.md

Personal collection of AI-agent skills. One folder per skill; each `SKILL.md` is the source of truth.

## Skills

- `flush/SKILL.md` — end-of-session project handoff: update repo state, commit, push.
- `sync/SKILL.md` — lightweight git sync. Pushes already-committed work, fast-forwards when remote is ahead and tree is clean, warns on dirty/untracked. Workspace mode: if cwd is a parent of repo subfolders, runs sync on each and aggregates. Never commits, merges, rebases, or force-pushes. Slash `/sync`. Pairs with `/flush`.
- `init-agents/SKILL.md` — initialize a directory with AI-agnostic agent context (`AGENTS.md` canonical + pointers from agent-specific instruction files). Description-triggered, so no slash collision with the built-in `/init`.
- `recommend/SKILL.md` — pause and surface direction-level recommendations or refactors. Slash `/recommend` plus self-triggers on drift signals.
- `self-evaluate/SKILL.md` — estimate PDCA loops remaining before the work is finished. Cost-driven, phase-agnostic. Investigates (code/env/smoke/web) before estimating. Slash `/self-evaluate`.
- `robust-web-fetch/SKILL.md` — fetch web source material when ordinary fetch tools are insufficient: PDFs, HTML, text, rendered pages, archived copies, and CDN-blocked sources. Description-triggered.
- `transcribe-pdf/SKILL.md` — transcribe a PDF to Markdown for downstream AI reading. Self-contained: bundles `pdf2md.py` as the cheap default plus a page-combine helper, and falls back to vision transcription when the text layer is unrecoverable. Description-triggered.
- `generate-image/SKILL.md` — generate or edit bitmap images with OpenAI `gpt-image-2` via the Codex CLI's built-in imagegen skill (`codex exec -s workspace-write`). ChatGPT-subscription auth, no API key. Saves into the current project; edit mode loads the source image first. Slash `/generate-image`.

## Conventions

- **AI-agnostic output.** Skill bodies and the docs they write into user repos use agent-neutral language. Don't bake tool-specific paths or instructions into a skill's body. Frontmatter (`allowed-tools`, `user-invocable`, etc.) is runner-specific metadata; keep that as the only agent-specific surface.
- **One skill per top-level folder.** Add new skills as `<name>/SKILL.md`. Link them from `README.md` and from this file.
- **Solo-repo workflow.** Direct commits and pushes. No PR step.
- **Handoff-first for `/flush`.** Let the agent decide what project state matters. Don't create docs or commits just to record that nothing happened.
- **No automatic cache wipe in `/flush`.** It's a durable handoff workflow, not a cache deletion routine.

## Layout

- `flush/`, `sync/`, `init-agents/`, `recommend/`, `self-evaluate/`, `robust-web-fetch/`, `transcribe-pdf/`, ... — one folder per skill.
- `README.md` — outward-facing description and install instructions.
- `AGENTS.md` — this file (orientation for any agent working on the repo).
- `TODO.md` — open items.

## Install

See `README.md` for the AI-agnostic installation prompts. To install one skill, symlink its folder into the agent's global-skills directory. To install the full collection, symlink every top-level folder that contains a `SKILL.md`, replacing stale symlinks but not real directories or files without confirmation.
