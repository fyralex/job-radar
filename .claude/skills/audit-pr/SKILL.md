---
name: audit-pr
description: The auditor's checklist and comment format for reviewing one Job Radar pull request. Load this when acting as the auditor agent, or to self-check a PR before asking for an audit.
---

# Audit a pull request

## Checklist

Mark a finding **blocking** if it breaks a rule in CLAUDE.md, fails a check,
or ships a bug. Everything else is **non-blocking**.

**Scope**
- The PR closes exactly one issue (`Closes #N`), and every acceptance
  criterion in the issue is met. Name any that isn't.
- No unrelated changes: drive-by refactors, formatting churn, stray files.
- The description says what changed, why, how it was tested (with the check
  summary) and what was left out.

**Data collection policy** (blocking if broken)
- Every outbound request goes through `job_radar.http.HttpClient`. No
  `requests.get` or new HTTP library in source modules.
- No browser automation, TLS fingerprint spoofing, rotating user agents or
  proxies, header tricks, or token/CSRF/JWT/API-key reuse.
- A new platform is on the allowed list, or the issue records the owner's
  approval and the module docstring repeats the decision.
- Nothing stores or returns job descriptions or anyone's name or email.

**Privacy and secrets** (blocking)
- No personal details: names, home towns, employer target lists,
  applications. Fixtures are trimmed and scrubbed.
- No secrets, tokens or real `.env` values. Only placeholders in
  `.env.example`.
- If `$JOB_RADAR_PRIVATE_SCAN` is set, run it on the checkout; any hit is
  blocking.

**Tests**
- New or changed behaviour has unit tests. A new source module has a recorded
  fixture plus parser tests for each documented quirk. A new endpoint has API
  tests, including validation errors.
- No live network in unit tests. Database tests ran (passed, not skipped).

**Code**
- mypy `--strict` and `tsc --noEmit` pass; no new `Any`, `# type: ignore` or
  `as` casts without a comment saying why.
- Schema changes come with an Alembic migration that upgrades and downgrades
  cleanly. Dropping data needs the owner's OK in the issue.
- API JSON stays snake_case, and `frontend/src/datatypes.ts` matches it.
- Errors reach the user as clear messages, not stack traces.
- Docs: CLAUDE.md and docstrings are updated where the change makes them
  wrong.

## Re-run the checks

```bash
git worktree add --detach /tmp/audit-pr-<N> origin/<head-branch>   # after: gh pr view <N> --json headRefName
cd /tmp/audit-pr-<N>/backend && ruff check . && ruff format --check . && mypy src
cd /tmp/audit-pr-<N>/backend && TEST_DATABASE_URL=<url> TEST_REDIS_URL=<url> pytest -q -rs
cd /tmp/audit-pr-<N>/frontend && yarn install --frozen-lockfile && yarn lint && yarn typecheck && yarn test && yarn build
git worktree remove /tmp/audit-pr-<N>
```

Use the backend venv from the main checkout (`../../<repo>/backend/.venv/bin/`)
or create one in the worktree. The `run-job-radar` skill shows how to start a
throwaway Postgres and Redis for `TEST_DATABASE_URL` and `TEST_REDIS_URL`.

## Comment format

Post with `gh pr comment <N> --body-file <file>`:

```markdown
## Audit round <N>: APPROVE | CHANGES_REQUESTED

**Checks:** backend lint/types ✅ · backend tests ✅ (<passed> passed, 0 skipped) · frontend ✅

### Findings
1. **[blocking]** `path/to/file.py:42`: what is wrong, why it matters, what would fix it.
2. **[non-blocking]** ...

### Earlier findings            <!-- round 2 and 3 only -->
- #1 fixed · #2 withdrawn: <reason> · #3 upheld: <reason>
```

Then label the round:

```bash
gh pr edit <N> --add-label audit:round-<N> --remove-label audit:round-<N-1>
```
