---
name: self-evaluate
description: >-
  Estimate how many PDCA (plan-do-check-act) loops remain before the work is
  finished. The number is cost-driven - each loop costs time, tokens, and
  attention - and is invokable in any phase: pre-implementation,
  mid-implementation, post-test-failure. The agent chooses the useful level of
  investigation (reads code, smoke-tests, checks env, web-searches, or explains
  why only minimal grounding is needed), so the number is grounded in evidence
  rather than guessed. Use when the user asks "how many more loops", "how close
  are we", "self-evaluate", "are we close to done", "why is this taking so
  long", "give me a status report", "re-evaluate our approach", or wants a
  cost-driven estimate of remaining work.
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - WebFetch
  - WebSearch
  - Agent
---

# /self-evaluate - PDCA loops remaining

Estimate how many plan-do-check-act loops the running agent (with its current tools and environment) needs to take this work from where it is now to done.

This is cost-driven: each loop costs compute, tokens, and human attention. The estimate tells the user how much budget to expect, whether to keep iterating or replan, or whether to switch tools entirely. It is calibration, not a commitment.

The estimate must be **earned through evidence**. The agent decides how much investigation is warranted, but guessing without grounding in the code, environment, current diff, conversation context, or known unknowns is the failure mode this skill exists to prevent.

The skill is **phase-agnostic**. It can be invoked when there is only a plan, mid-implementation with code in flight, after a failed test run, or at any point in between. The flow is the same; only the artifact under evaluation changes.

## Flow

1. **Identify what is being evaluated.** The named artifact (path, PR number, "the plan above", "the work in flight") or the most recent plan/recommendation/diff in the session. Note the phase: pre-implementation, mid-implementation, post-test-failure, etc. If nothing evaluable is in scope, ask. If the artifact is too vague even after asking, refuse - refusal is a valid output.

1. **Investigate to reduce uncertainty.** Choose the scale yourself. Constrain your investigation to a maximum of 2-3 tool calls for isolated changes, or up to 5 tool calls for broad architectural shifts. Do not get stuck in a long research loop. Pick the cheapest checks that move the estimate most. The investigation itself is meta-work, not a loop - it is the preparation that makes the count more accurate.

   - **Code grounding.** Open the files the work touches. Verify symbols, line numbers, function signatures, schema fields. References to things that don't exist mean more loops.
   - **Current state.** If mid-implementation, read the current diff. What's done, what's broken, what's in flight? If post-test-failure, read the actual error output and try a minimal repro.
   - **Environment assessment.** Are the tools the work assumes installed and at the right versions? Are credentials, network, permissions in place? Can this agent actually run the commands the work requires? Missing tools mean more loops, possibly unbounded.
   - **Smoke tests.** Run the build, run the existing tests, run a CLI the work depends on when that is the cheapest way to ground the estimate - does the starting state even work? You cannot estimate fix loops on top of a broken baseline.
   - **Web search.** Unfamiliar library API shape, version-specific behavior, error messages, recent breaking changes. Especially worth it for any third-party dependency the work leans on. If web access is unavailable, cite that as a risk and continue when the missing search is not essential.
   - **Scratch experiments.** When the work hinges on a single uncertain mechanism (regex behavior, API edge case, library quirk), run a tiny throwaway probe rather than guess.

   Keep evaluation checks non-invasive. It is fine to create temporary folders or files for tests and scratch experiments, as long as they are cleaned up afterward. Do not install dependencies, run migrations, rewrite lockfiles, alter persistent data, or perform destructive operations just to evaluate remaining loops unless the user explicitly approves.

   Stop investigating when the next likely check would not move the estimate by more than one loop.

1. **Estimate** using the anchors below. Use a range when the uncertainty is real - false precision helps no one.

1. **Report** in the output shape below.

## Anchors

| Loops remaining | Meaning |
|---|---|
| 0 | Done. Relevant verification passes now. Reserved for confirmed completion. |
| 1 | One round: implement (or polish) + verify, ship. |
| 2-4 | Normal iteration on a grounded plan. Edge cases, test fixtures, library-edge behavior. |
| 5-10 | Multiple unverified assumptions. Each loop will reveal more. |
| 10+ | Plan needs rework before implementation; replan rather than push through. |
| Unbounded | Fundamentally stuck. Direction is wrong, the environment can't support it, or scope is unclear. Stop and rethink. |

Anchor rules:

1. **0 loops** requires relevant verification to have actually passed - tests, build, smoke check, rendered docs, or another concrete done signal - not "the plan looks right".
1. **1 loop** requires the plan is verified end-to-end against the relevant artifact and any environment needed to finish.
1. **2-4 loops** requires the plan's claims have been verified against the actual artifact, code, or environment.
1. **10+ or Unbounded** should come with a recommendation to replan rather than execute. Don't bury that under a number.

## Output shape

1. **Loops remaining: N** (or **N-M**, or **Unbounded**). One line. Wrap the estimate in XML tags, e.g., `<loops_remaining>N</loops_remaining>`.
1. **Where they'll land.** Bulleted breakdown - "~1 loop on build setup, 2-3 on integration tests, 1 on polish". This *is* the body of the estimate; the number must be justified by this list.
1. **What could push it higher.** Concrete risks. Each cites a file:line, a missing tool, a known unknown, or an assumption the time budget did not cover. If you cannot name at least one, the estimate is too low.
1. **What pulls it lower.** Concrete grounding from the investigation. Each cites a verified file, current diff, conversation artifact, passing smoke test, confirmed tool version, or settled search result. If you cannot name at least one, the estimate is too high.
1. **Investigations performed.** One-line bullets: what was checked, what it confirmed or invalidated. Makes the estimate auditable. If you intentionally kept investigation minimal, say what evidence made that enough.

## Hard rules

1. **Ground before estimating.** A count with no supporting evidence is unsupported. Decide whether the situation calls for broad investigation, a narrow check, or minimal grounding; if the time budget truly allowed nothing, say "insufficient grounding - tentative N loops" rather than a clean number.
1. **No estimate without evidence.** Every supporting claim must cite a file:line, current diff, conversation artifact, command output, search hit, or smoke-test result.
1. **No invented confidence.** If a key assumption could not be verified, list it under "what could push it higher" rather than estimating around it.
1. **No estimate drift from pushback.** If the previous estimate this session was 5 loops and nothing material changed, the new estimate is still 5. Pushback is not new evidence; new investigation is.
1. **Refusal is valid.** If the artifact is too vague to estimate even after grounding or clarification, return "insufficient detail to estimate" with a concrete list of what is missing.
1. **Unbounded is valid.** Don't force a number when the work is fundamentally blocked. "Unbounded - replan first" is a real answer.

## Second opinion (optional)

When the user asks for a second opinion, use a fresh-context reviewer when the running environment supports it - a subagent, a separate session, or a different tool - and give it the same rubric and the same artifact. Report both estimates side by side. Disagreements of more than 2x (e.g. one says 2, the other says 5+) are worth surfacing as a discussion, not auto-reconciling. If a fresh-context reviewer is unavailable, say so and provide the rubric or prompt the user can run in another session by hand.

## Example Output

**Loops remaining:** `<loops_remaining>2-3</loops_remaining>`
- ~1 loop on fixing the type errors in `src/auth.ts`.
- ~1-2 loops on updating the integration tests to match the new schema.

**What could push it higher:**
- The third-party OAuth provider API might have undocumented rate limits (we haven't tested the live endpoint yet).
- `tests/integration/auth.spec.ts` has multiple skipped tests that might fail when re-enabled.

**What pulls it lower:**
- The database schema migration has already been verified and applied successfully (checked `db/schema.sql`).
- The user confirmed the auth flow logic is acceptable in the previous turn.

**Investigations performed:**
- Checked `src/auth.ts` current diff (verified type errors exist).
- Ran `npm run test:integration` (confirmed 3 tests are failing).
