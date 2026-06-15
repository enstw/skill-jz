# Making this repo `skills`-compatible

Note on how this repo works with the agent-agnostic **`skills` CLI** (agentskills.dev, run as `npx skills`), so anyone can install these skills straight from the GitHub URL.

## Status: already compatible

No structural changes are needed. The CLI discovers all skills today:

```bash
npx -y skills add enstw/skill-jz -l   # list without installing
```

This clones the repo and reports `Found 8 skills` (flush, init-agents, recommend, robust-web-fetch, self-evaluate, sync, transcribe-pdf, yt2sub). Re-run this command after any change to confirm the repo still parses.

## What makes a repo `skills`-compatible

The CLI walks a cloned repo looking for `SKILL.md` files and reads each one's frontmatter.

1. **One skill per top-level folder, each with a `SKILL.md`.** This repo already follows that (`flush/SKILL.md`, `sync/SKILL.md`, …).
1. **No root `SKILL.md`.** With no root file, the repo is treated as a *multi-skill* collection and every subfolder skill is discovered. A root `SKILL.md` would make the CLI treat the repo as a *single* skill (unless the installer passes `--full-depth`). Keep the root free of `SKILL.md`.
1. **Required frontmatter: `name` and `description`.** `name` should be lowercase-kebab and match the folder name. `description` is the trigger text an agent matches against, so keep it self-contained (what it does + when to use it).
1. **Bundle scripts and assets inside the skill folder, referenced by relative path.** The CLI copies/symlinks the *whole folder*, so anything outside it won't ship. `transcribe-pdf/scripts/`, `yt2sub/scripts/`, and `robust-web-fetch/scripts/` already do this correctly.
1. **Runner-specific frontmatter is fine.** Fields like `user-invocable` and `allowed-tools` are read by some runners and ignored by others — harmless to leave in.
1. **Keep consumer artifacts gitignored.** `.claude/`, `.antigravitycli/`, and `.opencode/` are already in `.gitignore`. (`skills-lock.json` is generated on the *consumer* side, not here, so it never appears in this repo.)

## How people install from the GitHub URL

```bash
npx -y skills add enstw/skill-jz                      # all skills
npx -y skills add enstw/skill-jz --skill flush sync   # pick specific ones
npx -y skills add enstw/skill-jz --agent claude-code  # target one agent (default: detected agent)
npx -y skills add enstw/skill-jz -g                   # global (user-level) instead of project
npx -y skills add enstw/skill-jz --copy               # vendor a copy instead of symlinking
```

`owner/repo` shorthand and the full `https://github.com/enstw/skill-jz.git` URL both work.

## Sync model: pinned, not live

The `skills` CLI **vendors a pinned copy** — it does not stay linked to GitHub. On the consumer side, `skills-lock.json` records each skill's source, path, and a content hash; `skills experimental_install` restores from it (the `npm ci` equivalent). Updates are manual:

```bash
npx -y skills update           # update all installed skills to latest
npx -y skills update flush     # update one
```

There is no auto-pull daemon. As the source repo, we do nothing for "sync" — consumers re-run `update` when they want newer versions.

## Relationship to the README install method

The README's symlink approach (`gemini skills link ./flush`, or a manual symlink into the agent's global-skills dir) is the **live** path: pull this repo, and linked skills update automatically. The `skills` CLI is the **registry/CLI** path: install-from-URL with a pinned lockfile and a manual `update`. Both target the same `<name>/SKILL.md` layout — supporting one costs nothing for the other.

## When adding a new skill

Follow the existing convention and it stays compatible automatically: create `<name>/SKILL.md` with `name` + `description` frontmatter, bundle any scripts under `<name>/`, link it from `README.md` and `AGENTS.md`, then verify with `npx -y skills add enstw/skill-jz -l`.
