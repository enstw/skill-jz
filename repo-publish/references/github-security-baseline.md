# GitHub repository security baseline

Use this baseline for a newly public repository and for an explicit GitHub
settings audit. Query first, mutate only when the request authorizes changes,
then query again. GitHub plan and owner type affect feature availability; mark
unsupported controls as unavailable instead of silently omitting them.

## Contents

1. [Audit inventory](#audit-inventory)
1. [Public-repository defaults](#public-repository-defaults)
1. [Default branch and PR policy](#default-branch-and-pr-policy)
1. [Protect CI integrity](#protect-ci-integrity)
1. [Releases and tags](#releases-and-tags)
1. [Verification and report](#verification-and-report)

## Audit inventory

Capture at least:

1. Repository visibility, collaborators, merge methods, auto-merge, branch
   deletion, branch updates, license, topics, archived/disabled state.
1. Default-branch protection and repository rulesets, including required
   checks/reviews, admin enforcement, linear history, force-push/deletion,
   conversation resolution, and creation/update bypass actors.
1. Actions policy: enabled/allowed actions, default token permission, PR-review
   permission, fork-PR approval policy, and SHA-pinning requirement.
1. Secret scanning, push protection, validity/non-provider checks when
   available, Dependabot alerts/security updates, code scanning, and private
   vulnerability reporting.
1. Environments, deployment protection, repository secrets/variables, deploy
   keys, webhooks, branches, collaborators, releases, and tags. Never print a
   secret value; GitHub does not expose Actions secret values through the API.
1. Workflow files themselves: triggers, permissions, third-party `uses:`,
   untrusted checkout/execution, release credentials, and mutable references.

Useful read-only endpoints (replace `<owner>/<repo>`):

```bash
gh api repos/<owner>/<repo>
gh api repos/<owner>/<repo>/branches/<default>/protection
gh api repos/<owner>/<repo>/rulesets --paginate
gh api repos/<owner>/<repo>/actions/permissions
gh api repos/<owner>/<repo>/actions/permissions/workflow
gh api repos/<owner>/<repo>/actions/permissions/fork-pr-contributor-approval
gh api repos/<owner>/<repo>/collaborators --paginate
gh api repos/<owner>/<repo>/environments
gh api repos/<owner>/<repo>/hooks --paginate
gh api repos/<owner>/<repo>/keys --paginate
gh api repos/<owner>/<repo>/actions/secrets --paginate
gh api repos/<owner>/<repo>/actions/variables --paginate
```

Treat `403`/`404` from security endpoints carefully: the response often means
the feature is disabled or the token lacks scope, not that there are no alerts.

## Public-repository defaults

Apply these controls when supported:

1. Enable secret scanning and push protection before the next push. Enable
   validity and non-provider-pattern checks when the plan supports them.
1. Enable Dependabot vulnerability alerts and security updates. Add code
   scanning appropriate to the languages/build system; do not claim coverage
   until an analysis has completed successfully.
1. Enable private vulnerability reporting and add `SECURITY.md` with supported
   versions, a private reporting link, response expectations, and an explicit
   instruction not to file public vulnerability issues.
1. Keep Actions' default `GITHUB_TOKEN` read-only and unable to approve PRs.
   Give write/OIDC/attestation permissions only to the exact release/deploy job
   that needs them—not at workflow scope when test jobs share the workflow.
1. Require approval for first-time outside contributors at minimum. For an
   expensive CI or abuse-prone project, prefer approval for all outside
   collaborators.
1. Pin every action, reusable workflow, container image, model/data revision,
   and downloaded build input to an immutable digest/SHA where the ecosystem
   supports it. Keep the human-readable version in a comment for Renovate.
1. After all `uses:` references are pinned, restrict Actions to GitHub-owned
   and an explicit allowlist, and enable mandatory SHA pinning when available.

## Default branch and PR policy

Set the default branch to:

1. Require the complete candidate check on the latest base (`strict`). Bind the
   check to its expected GitHub App where supported to prevent name spoofing.
1. Enforce the rule for administrators; require linear history; reject force
   pushes and branch deletion.
1. Require conversation resolution. Require signed commits only when the team
   and automation can satisfy it without bypasses.
1. Disable merge methods that conflict with linear history. Usually keep
   rebase merge; keep squash only when the project wants one commit per PR.
1. Enable automatic deletion of merged head branches and allow PR authors to
   update branches. Make native auto-merge an explicit project choice.

Review policy depends on the maintainer topology:

1. With two or more trusted maintainers, require at least one approval, dismiss
   stale approvals, require approval of the latest push, and add CODEOWNERS for
   `.github/workflows/`, release scripts, dependency config, branch-policy
   documentation, and other trust-boundary files.
1. With one maintainer, do not enable an unsatisfiable approval requirement.
   Record this as a residual risk, recommend a second trusted maintainer, and
   manually inspect every trust-boundary diff before merge. CODEOWNERS alone is
   documentary until an approval rule enforces it.

## Protect CI integrity

A green check is trustworthy only if the proposed change cannot redefine what
"green" means without independent approval.

1. Include `.github/workflows/**`, CI classifiers, their tests, release scripts,
   lockfiles, dependency updater config, and policy files in the highest-cost
   validation scope. Never classify a classifier change as documentation-only.
1. Test changed-path classification against bypass cases: classifier self-edit,
   workflow edit, rename/delete, generated output, dependency config, and mixed
   documentation/code changes.
1. Require independent review for trust-boundary changes. When that is
   impossible in a solo repo, move the required gate to a protected external
   reusable workflow/repository or a GitHub App/check whose implementation the
   PR cannot modify.
1. Avoid `pull_request_target` with untrusted checkout/execution. If it is truly
   necessary, never run fork-controlled code with write credentials.
1. Keep automated dependency merge narrowly scoped to a known bot branch and
   exact required checks. Do not make every green PR auto-merge by accident.

## Releases and tags

1. Create a ruleset for release tags (normally `v*`) that prevents update and
   deletion. Restrict creation/bypass to the release workflow or maintainers
   appropriate to the project.
1. Split build/test from publish. Untrusted or merely proposed code must never
   receive release credentials. Publish only an already-tested protected-branch
   commit, preferably through a protected environment with approval for high-
   impact releases.
1. Validate requested tags as SemVer and require monotonic progression. Never
   derive a public version from an Actions run number after a higher major/minor
   release; it can produce a newer release marked `Latest` with an older version.
1. Attest release artifacts and publish checksums/SBOM where useful. Pin the
   attestation action itself.

## Verification and report

After changes:

1. Re-query every mutated setting and inspect the effective default-branch
   protection/ruleset. Verify admins are covered and force push/deletion are
   still disabled.
1. Open a harmless test PR when practical. Confirm required checks run, an
   outdated branch cannot merge, merge methods behave as documented, and a
   failed check blocks administrators too.
1. Verify workflows still start after action restrictions; verify a release
   from a protected commit and ensure the correct SemVer is marked Latest.
1. Report findings by severity, applied changes, unsupported/deferred controls,
   residual risks, and any manual steps. Never say "secure" solely because the
   mutation API returned success.
