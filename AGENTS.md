# AGENTS.md

Personal collection of AI-agent skills. One folder per skill; each `SKILL.md` is the source of truth.

## Skills

- `flush/SKILL.md` — end-of-session project handoff: update repo state, commit, push.
- `init-agents/SKILL.md` — initialize a directory with AI-agnostic agent context (`AGENTS.md` canonical + pointers from agent-specific instruction files). Description-triggered, so no slash collision with the built-in `/init`.
- `recommend/SKILL.md` — pause and surface direction-level recommendations or refactors. Slash `/recommend` plus self-triggers on drift signals.
- `self-evaluate/SKILL.md` — estimate PDCA loops remaining before the work is finished. Cost-driven, phase-agnostic. Investigates (code/env/smoke/web) before estimating. Slash `/self-evaluate`.
- `fetch-blocked-pdf/SKILL.md` — download CDN-blocked PDFs/pages (Cloudflare/Akamai 403). `curl-cffi` TLS impersonation, optional Playwright HTML-to-Markdown fallback. Description-triggered.

## Conventions

- **AI-agnostic output.** Skill bodies and the docs they write into user repos use agent-neutral language. Don't bake tool-specific paths or instructions into a skill's body. Frontmatter (`allowed-tools`, `user-invocable`, etc.) is runner-specific metadata; keep that as the only agent-specific surface.
- **One skill per top-level folder.** Add new skills as `<name>/SKILL.md`. Link them from `README.md` and from this file.
- **Solo-repo workflow.** Direct commits and pushes. No PR step.
- **Handoff-first for `/flush`.** Let the agent decide what project state matters. Don't create docs or commits just to record that nothing happened.
- **No automatic cache wipe in `/flush`.** It's a durable handoff workflow, not a cache deletion routine.

## Layout

- `flush/`, `init-agents/`, `recommend/`, `self-evaluate/`, `fetch-blocked-pdf/`, ... — one folder per skill.
- `README.md` — outward-facing description and install instructions.
- `AGENTS.md` — this file (orientation for any agent working on the repo).
- `TODO.md` — open items.

## Install

See `README.md` for the AI-agnostic installation prompts. To install one skill, symlink its folder into the agent's global-skills directory. To install the full collection, symlink every top-level folder that contains a `SKILL.md`, replacing stale symlinks but not real directories or files without confirmation.
