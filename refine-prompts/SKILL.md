---
name: refine-prompts
description: >-
  Refine skills (each SKILL.md and the files it ships) against Anthropic's
  latest published prompting guidance, then commit each refined skill
  separately. Use when the user says "refine the skills", "update the skills
  to the new prompt guide", "apply the latest prompting best practices",
  "/refine-prompts", "用最新的 prompt guide 改寫 skill" — or when a new model
  release ships a new prompting guide. Optional --model <id> adds that model's
  own guide. Do not rewrite skills from remembered prompting advice or from a
  scraped HTML page: the bundled fetch script pulls the live Markdown guides,
  checks them against the docs index, and records hashes so every change is
  traceable to the guide text it came from.
user-invocable: true
---

# refine-prompts

Bring one skill, or every skill in a collection, in line with the current prompting guides. The guides are the authority. Your memory of earlier prompting advice is not: it is out of date by design, and the guides change with each model release.

## Inputs

- **Targets**: skill folder names, or none, meaning every top-level folder with a `SKILL.md` in the current collection. Skip this skill itself unless it is named.
- **`--model <id>`** (optional), e.g. `claude-opus-5-5`.
  - Without it, apply the **general guide** only.
  - With it, apply the general guide **and** that model's own guide, plus the earlier model guide it builds on when it names one. Where they disagree, the model's guide wins for that model.
  - If the model has no guide of its own, the fetch reports `NO_MODEL_GUIDE`; continue with the general guide and say so in the report.

## Procedure

1. **Start clean.** Work on the repo's main branch, synced with the remote. The target folders must have no uncommitted changes, because each skill gets its own commit. If one does, skip that skill and report why.
1. **Fetch the guides.** Run `scripts/fetch-guides.sh [--model <id>] <out_dir>` (use a scratch directory). It prints one `GUIDE <role> <url> sha256:<hash> <bytes> <path>` line per file and writes them to `<out_dir>/MANIFEST`. A non-zero exit means no reliable guide text: stop and report it. Do not fall back to memory or to other copies of the guide found on the web.
1. **Read every fetched guide in full.** Then build a checklist from them. For each point of guidance, decide which group it belongs to:
   - **Skill text**: anything about how instructions are written or what behavior they should ask for. Examples: stating the reason behind a rule, telling the model what to do rather than only what to avoid, calibrating emphasis, naming the specific failure modes to avoid, where examples help, scope and initiative, when to stop and when to keep going.
   - **Harness**: anything a skill's bundled scripts or hooks do, such as continuation logic, stop checks, or progress reporting.
   - **Not applicable**: settings that a skill file cannot control, such as API parameters, thinking or effort settings, prefill, or SDK features.
1. **Keep skill text agent-neutral.** Skills here run on more than one agent and model. Adopt guidance only where it makes the instructions clearer for any capable model, and phrase it that way. Never write model names, API parameters, or one vendor's features into a skill body. Frontmatter fields that a runner reads stay as they are.
1. **Refine each target, one at a time.**
   1. Read the whole `SKILL.md`, plus the bundled scripts, hooks, and references it ships.
   1. Check them against the checklist. For each gap, edit the skill to match the guide. Both rewording and behavior changes are in scope, including changes to bundled scripts and hooks under the harness group.
   1. Keep what the skill's users and callers depend on: the `name`; the user's own trigger phrases in `description`, in every language they appear; documented contracts (exit codes, output lines, stop codes, file paths and arguments other skills call); and concrete facts the skill records from real failures. Before changing a contract, search the collection for its callers. If a caller would break, update the caller in the same commit or leave the contract alone.
   1. Every edit must trace to a specific guide section. If a skill already follows the guidance, leave it untouched. Do not reword for taste, and do not grow a skill: the guides favor short, direct instructions, so a refinement usually removes words.
   1. Verify. Run any tests the repo or skill defines for that skill. Syntax-check every edited script (`bash -n`, `node --check`, `python -m py_compile`, as fits). Re-read the edited `SKILL.md` once from the point of view of an agent seeing it for the first time.
   1. If the skill's one-line summary in the collection's index files (`README.md`, `AGENTS.md`) no longer matches, update it in the same commit.
   1. Commit that skill on its own, with the message format below.
1. **Push** only if the repo's own instructions allow direct pushes. Otherwise leave the commits for the user.
1. **Report**, one line per skill: committed (with short hash and what changed), unchanged (already conforms), or skipped (with the reason). Then list any guidance you could not apply, and any `NO_MODEL_GUIDE` result.

## Commit message

```text
<skill>: refine against prompting guide (<general sha>[, <model> <sha>])

- <change> — <guide file>#<section anchor>
- <change> — <guide file>#<section anchor>

Guides (fetched <fetched-at>):
<url> sha256:<hash>
<url> sha256:<hash>
```

The guide hashes are recorded only in commit messages, never in the skill files. That way a later run can find the last guide each skill was checked against (`git log --grep 'refine against prompting guide' -- <skill>/`) without stamping files that would otherwise not change.

## Re-running

On a later run, first compare the current hashes with the ones in each skill's last refine commit. Matching hashes mean the guides have not changed since that run: report "guides unchanged" and stop, unless the skill itself has been edited since.
