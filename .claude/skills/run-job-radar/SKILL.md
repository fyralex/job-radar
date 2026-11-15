---
name: run-job-radar
description: Run, check and test Job Radar - start the Docker Compose stack, import demo boards, scrape, smoke-check the API and UI, and run every backend and frontend check including database tests on a throwaway Postgres. Use when asked to run the app, try a change in the real app, or run the tests.
---

# Run and test Job Radar

## Full stack (Docker Compose)

```bash
cp .env.example .env            # first time: set POSTGRES_PASSWORD (e.g. openssl rand -hex 16)
docker compose up -d --build    # postgres, backend (runs migrations), worker, frontend
docker compose ps               # all four should become healthy
```

The UI is at `http://localhost:${HTTP_PORT:-8080}`. Port in use? Set
`HTTP_PORT` in `.env`.

Seed and smoke-check:

```bash
docker compose exec backend flask --app job_radar.wsgi boards import config/boards.example.yaml
docker compose exec backend flask --app job_radar.wsgi scrape     # prints boards / failed / postings
curl -s localhost:8080/api/health
curl -s localhost:8080/api/boards | python3 -m json.tool | grep -E '"org"|last_status'
```

A healthy demo run scrapes every example board with 0 failed. If one fails,
read its `last_error`: a robots.txt refusal or a 403 means the board is
dropped, not worked around (see CLAUDE.md's data collection policy).

After code changes: `docker compose up -d --build <service>`. Logs:
`docker compose logs -f backend worker`.

## Backend checks

```bash
cd backend
python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # first time
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src
```

Database tests need PostgreSQL and Redis tests need Redis. Throwaway ones:

```bash
docker run -d --rm --name jobradar-testdb -e POSTGRES_USER=jobradar \
  -e POSTGRES_PASSWORD=jobradar -e POSTGRES_DB=jobradar -p 127.0.0.1:55432:5432 postgres:16-alpine
docker run -d --rm --name jobradar-testredis -p 127.0.0.1:56379:6379 redis:7-alpine
TEST_DATABASE_URL=postgresql+psycopg://jobradar:jobradar@127.0.0.1:55432/jobradar \
TEST_REDIS_URL=redis://127.0.0.1:56379/0 REQUIRE_DATABASE=1 REQUIRE_REDIS=1 \
  .venv/bin/pytest -q -rs --cov=job_radar
docker stop jobradar-testdb jobradar-testredis
```

`-rs` lists skipped tests. Database and Redis tests skip when their service is
unreachable, so a passing run must show 0 skipped; the `REQUIRE_*` variables
make a missing service fail instead. The network is blocked in tests
(pytest-socket); localhost is allowed.

To try a change in the real app without touching your own stack, run a
separate compose project with its own volumes, and leave out the worker if
you seed postings by hand (it would scrape and close them):

```bash
HTTP_PORT=18090 docker compose -p jobradar-review up -d --build postgres redis backend frontend
HTTP_PORT=18090 docker compose -p jobradar-review down -v   # removes its database too
```

## Frontend checks

```bash
cd frontend
yarn install --frozen-lockfile
yarn lint && yarn typecheck && yarn test && yarn build
yarn dev    # dev server on :5173, proxies /api to a backend on :8000
```

## Secrets and personal data

```bash
pre-commit install && pre-commit run --all-files   # ruff, whitespace, gitleaks (via Docker)
# If pre-commit says InvalidManifestError ("Expected one of commit, ... got: 'pre-commit'"),
# a system pre-commit older than 3.2 is on PATH; use backend/.venv/bin/pre-commit instead.
```

If `JOB_RADAR_PRIVATE_SCAN` is set, run it too. It's the owner's private scan
for personal terms; it lives outside the repo because its pattern is itself
personal.
