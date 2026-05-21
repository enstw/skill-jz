# skill-jz

A personal collection of AI-agent skills. Each top-level directory is one skill; the `SKILL.md` inside is the source of truth.

## Skills

- **[flush](./flush/)** — End-of-session project handoff. Updates the repo with current project state, commits, and pushes so work can resume from another machine or session.
- **[init-agents](./init-agents/)** — Initialize a directory with AI-agnostic agent context: `AGENTS.md` as the canonical file, plus short pointers from agent-specific instruction files such as `CLAUDE.md` and `GEMINI.md`. Description-triggered (no slash command), so it doesn't collide with Claude Code's built-in `/init`.
- **[recommend](./recommend/)** — Pause the current trajectory, surface direction-level recommendations, and offer to refactor. Slash-invocable as `/recommend`; also self-triggers when the agent senses drift (scope creep, naming churn, half-finished implementations).
- **[self-evaluate](./self-evaluate/)** — Estimate how many PDCA (plan-do-check-act) loops remain before the work is finished. Cost-driven and phase-agnostic: invokable pre-implementation, mid-implementation, or post-test-failure. The agent investigates (reads code, smoke-tests, checks env, web-searches) before estimating so the number is grounded in evidence. Slash-invocable as `/self-evaluate`.
- **[fetch-blocked-pdf](./fetch-blocked-pdf/)** — Download PDFs or web pages blocked by CDNs such as Cloudflare or Akamai (403 Forbidden to `curl`/`web_fetch`). Bundles a `curl-cffi` browser-TLS-impersonation script with an optional Playwright HTML-to-Markdown fallback. Description-triggered (no slash command).
- **[transcribe-pdf](./transcribe-pdf/)** — Transcribe a PDF to Markdown for downstream AI reading (citation lookup, research notes). Encodes the token-economy case for transcribing once instead of re-reading the PDF every lookup, prefers the offline `pdf2md.py` tool, and escalates to a parallel-subagent vision fan-out only when the text layer is unrecoverable. Description-triggered.

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

## Requirements

Per skill — see each `SKILL.md`. In general:

- Git, for repo detection and any commit/push step a skill performs.
- `gh` (optional) for repo bootstrapping flows.
- HTTPS pushes to github.com require `gh auth setup-git` to be run once, or another credential helper. Skills never try to fix auth on their own — they report and stop.

## Adding a new skill

One skill per top-level folder. Create `<name>/SKILL.md` with frontmatter and body, link it from this README and from `AGENTS.md`, and follow the AI-agnostic-output rule for anything the skill writes into user repos.
