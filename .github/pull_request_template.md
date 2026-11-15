Closes #

## What

<!-- The change, briefly. -->

## Why

<!-- The reason, or a link to the issue's goal. -->

## How tested

<!-- Paste the local check summary. CI runs only at milestones. -->

- [ ] Backend: `ruff check`, `ruff format --check`, `mypy src`
- [ ] Backend: `pytest -q -rs` with `TEST_DATABASE_URL` (0 skipped)
- [ ] Frontend: `yarn lint`, `yarn typecheck`, `yarn test`, `yarn build`
- [ ] `pre-commit run --all-files` (includes gitleaks)

## Left out

<!-- Anything not done, and why. -->

## Audit

<!-- Filled in by the audit loop: rounds run, verdict. -->
