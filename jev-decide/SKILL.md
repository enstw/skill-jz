---
name: jev-decide
description: >-
  Make a bounded decision with TypeSafe's Jev (System One) as a gated advisor.
  Use when you would otherwise stop and ask the user "which of these next
  steps / approaches / priorities?" and the choice is 2–4 concrete,
  mutually-exclusive options — the next ticket, which implementation approach,
  how to order a backlog. Also the choice-point tool of the long-run skill. The
  payload is the discipline of asking well (rich observed state, every option
  with pros AND cons, docs-first) plus a three-gate verdict (margin /
  confidence / irreversible) that says when a human must decide. Do not
  hand-roll a System One fetch — the bundled runner already does the call, the
  gates, and the PROCEED/ESCALATE exit code. PRE-CONDITION: a TypeSafe API key
  at ~/.config/typesafe/cred.json. For the TypeSafe API itself see the
  typesafe-ai plugin skill.
---

# jev-decide — Jev as a gated decision advisor

Jev returns a typed, calibrated pick over options *you* define. It does not do the thinking for you: the decision quality lives entirely in the state and options you hand it. This skill is that authoring discipline plus a gate that flags when the human, not the tool, should decide.

## What the verdict licenses

- **Normal mode — advisory.** PROCEED: report the pick and offer to act; wait for a yes. ESCALATE: lay out the trade-off for the user.
- **Inside a long run** (the `long-run` skill; a `.long-run` flag at the project root) the user has pre-delegated these choices. PROCEED: act on the pick immediately and note it on the work item. ESCALATE: park the item as *blocked: needs user decision* with the options and trade-off written down, and move to the next item — never stop the run on it.

In both modes: one decision per invocation, and `irreversible: true` always escalates.

## Author the spec (this is the real work)

A decision spec is JSON; the runner takes a file path or stdin:

```json
{
  "state": { "goal": "…", "done": ["…"], "blocked": "…", "constraints": ["…"] },
  "decision": {
    "instructions": "Choose the single best … Each option lists pros AND cons — weigh them.",
    "irreversible": false,
    "options": {
      "option_key": { "what": "what it is", "pros": "why it helps", "cons": "what it costs / risks" }
    }
  },
  "thresholds": { "minConfidence": 0.6, "minMargin": 0.15 }
}
```

Rules that make the answer trustworthy:

1. **Enough background.** Give the goal, what is already done (and how well verified), what is blocked and why, the hard constraints, and — if a consumer is waiting — its concrete unmet needs. A terse state produces a shallow pick; a rich one can change the pick outright.
1. **Every option carries `what` + `pros` + `cons`.** Never list only upside. The cons are how Jev (and the human reading the output) weigh the trade-off.
1. **Observed facts only, kept separate from inferred.** `state` is what is true, not what you hope. Don't smuggle a preferred conclusion into the framing.
1. **Docs-first — never invent facts to feed Jev.** If an option depends on something the project's docs don't establish, say so in its `cons` (or drop the option). A confident pick built on a guessed premise is worse than an honest ESCALATE.
1. **2–4 mutually-exclusive options**, plus a real "wait / do nothing" option when stopping is a legitimate outcome. Keep keys machine-friendly; put the meaning in `what/pros/cons`.
1. **Include every option you would actually consider.** Jev can only pick from the list; an option you leave out (e.g. "the remaining secondary items") can never win.

## Run it

```sh
node <this-skill-dir>/scripts/jev_decide.mts <spec.json>     # or: cat spec.json | node …/jev_decide.mts
node <this-skill-dir>/scripts/jev_decide.mts <this-skill-dir>/example-decision.json   # worked example
```

Needs Node 22.6+ (runs TypeScript directly) and the key at `~/.config/typesafe/cred.json` (`{ "api_key": "…" }`, outside any repo; override the path with `TYPESAFE_CRED`). Never print the key. Write specs to a scratch directory, not the project tree. Zero dependencies — plain `fetch`.

## Read the verdict

The runner prints the choice, the full distribution, the confidence, the **margin** (top1 − top2), and a VERDICT. Exit code: `0` = PROCEED, `10` = ESCALATE, `1`/`2` = call or spec error.

Gates (ESCALATE if ANY trips):

1. **margin < `minMargin`** (default 0.15) — a close race between the top two. This, not raw confidence, is the primary "ask a human" signal.
1. **confidence < `minConfidence`** (default 0.60) — a diffuse distribution.
1. **`irreversible: true`** — anything hard to reverse or outward-facing (deploy, delete, send a real order, spend) that no standing authorization covers. Always escalates, regardless of confidence.

**Why margin, not confidence alone:** confidence measures how concentrated the distribution is, not whether the pick is correct or safe. Several good options spread probability, so a low-confidence pick between near-equivalent choices is often fine — a close margin is the real ambiguity. Tune thresholds per decision; the verdict only says when to look.

## When two options are equally good (the tie option)

The margin gate has one honest false positive: two *equivalent* options produce a close margin. When you expect that, add an explicit "either is fine" option flagged `"tie": true`:

```json
"either_is_fine": {
  "what": "The options above are equally good — pick either arbitrarily.",
  "pros": "unblocks a trivial choice without deliberation",
  "cons": "only valid if the options are truly interchangeable",
  "tie": true
}
```

When a tie option wins, the runner waives the margin and confidence gates and returns PROCEED — pick any. The irreversible gate still applies.

**A tie option means the options are EQUIVALENT, not "unsure".** If it meant "I don't know", Jev could dump probability into it to dodge a decision that needs a human or more evidence. When the real problem is missing evidence, fix the `state` or ESCALATE — don't add a tie option.
