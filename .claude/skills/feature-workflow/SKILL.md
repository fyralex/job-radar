---
name: feature-workflow
description: How every Job Radar change goes from GitHub issue to audited pull request - issue, branch, build with skills, local checks, PR, up to three auditor rounds, escalation to the owner. Use when starting any feature, fix, chore or docs change in this repo.
---

# Feature workflow: issue -> PR -> audit

Never commit to `main`, never merge, never force-push. The owner merges.

## 1. Issue

Find the issue, or open one if the owner asked for the work and none exists:

```bash
gh issue list --milestone v0.1
gh issue create --title "<what>" --label <feat|fix|chore|docs|ci> --milestone v0.1 \
  --body-file /tmp/issue.md   # Goal / Acceptance criteria / Out of scope
```

If the work adds a platform that isn't on CLAUDE.md's allowed list, stop: the
issue needs the owner's written approval first.

## 2. Branch

```bash
git switch main && git pull --ff-only
git switch -c <type>/<issue>-<slug>        # e.g. feat/12-applications-tracker
```

## 3. Build

Use the skill that fits: `add-source-module`, `db-migration`,
`run-job-radar`. Write the tests with the code. Commit in small, honest
commits. Each message says what and why; end it with the attribution trailer
your session uses.

## 4. Local checks (all must pass)

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src
cd backend && TEST_DATABASE_URL=<url> TEST_REDIS_URL=<url> .venv/bin/pytest -q -rs --cov=job_radar   # 0 skipped
cd frontend && yarn lint && yarn typecheck && yarn test && yarn build
pre-commit run --all-files
"$JOB_RADAR_PRIVATE_SCAN"   # if set: the owner's private personal-data scan
```

## 5. Pull request

```bash
git push -u origin HEAD
gh pr create --title "<type>: <summary>" --body-file /tmp/pr.md
```

The body follows `.github/pull_request_template.md`: `Closes #N`, What, Why,
How tested (paste the check summary), Left out.

## 6. Audit loop (max 3 rounds)

For round N = 1, 2, 3:

1. Run the `auditor` agent: "Audit PR #<pr>, round N", plus, from round 2 on,
   your reply to each earlier finding.
2. Read its verdict.
   - **APPROVE**: `gh pr edit <pr> --add-label audit:approved`, tell the owner
     the PR is ready for review, and stop.
   - **CHANGES_REQUESTED**: go through every blocking finding:
     - Agree: fix it, rerun the local checks, push.
     - Disagree: reply on the PR (`gh pr comment`) with the finding number and
       a concrete reason. Don't change the code for it.
3. Next round.

**Escalate to the owner** (then stop) when:
- round 3 ends without APPROVE, or
- the auditor upholds a finding you still disagree with.

```bash
gh pr edit <pr> --add-label needs-owner
gh pr comment <pr> --body-file /tmp/escalation.md
```

The escalation comment lists each open point: the finding, the auditor's
position, your position, and what each option would mean. Then tell the owner
in chat, with the PR link.

## 7. After merge

The owner merges. Pull `main`, delete the local branch, and pick up the next
issue in the milestone. When a milestone's issues are all closed, the owner
closes the milestone, which runs CI; tag `v<x.y.0>` once it's green.
