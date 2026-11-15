# Job Radar

Job Radar is a self-hosted dashboard for a job search. Each install has one
user, and there is no login. The user:

- follows employers' public job boards (Greenhouse, Lever, Ashby and others),
- describes the jobs they want as **job profiles**: title terms to include and
  exclude, and optional seniority levels,
- sets a **location rule**: states and cities they'd work in on site, and
  whether remote jobs count,
- filters by posting age, work type (on-site, hybrid, remote) and employment
  type (full-time, contract...),
- hides postings they don't want, and sees which postings are new since their
  last visit.

A worker scrapes the boards on a schedule. The dashboard reads from
PostgreSQL. Application tracking (status pipeline, history, notes) is the next
feature (see "Roadmap").

This file is committed to a **public** repository. Keep it free of personal
details: no names, home towns, employer target lists, salaries or application
history. Those live in the app's database or in git-ignored local files.

## Working rules (read first)

1. **Every change starts as a GitHub issue and lands through a pull request.**
   Never commit to `main`. Follow the `feature-workflow` skill: issue, branch,
   build, local checks, PR, audit. Keep each PR small enough to review in
   about 15 minutes.
2. **Every PR is audited** by the `auditor` agent (`.claude/agents/auditor.md`)
   for up to three rounds before the owner reviews it. See "Audit loop".
3. **The owner merges.** Agents never merge, force-push, rewrite published
   history or push to `main`.
4. **Commits are real work, as it happens.** Never backdate a commit or make
   up a history.
5. **Collect data lawfully and politely.** See "Data collection policy". That
   policy outranks getting another board to work.
6. **No secrets in git.** Secrets come from environment variables only.
   `.env.example` holds placeholders. gitleaks runs in pre-commit and at
   milestones.
7. **Tests ship with the code.** Unit tests are required for every change and
   run locally before the PR is opened (see "Testing").
8. **When you're unsure, stop and ask** instead of guessing. This covers
   whether a board is allowed, any schema change that drops data, and any new
   paid service.

## Feature workflow

Each feature or fix is one issue, one branch and one PR.

1. **Issue.** Goal, acceptance criteria and what's out of scope. Use the
   feature template. Planned work sits in a milestone (`v0.1`, ...).
2. **Branch.** `<type>/<issue number>-<slug>`, with type `feat`, `fix`,
   `chore`, `docs` or `ci`. Example: `feat/12-applications-tracker`.
3. **Build** with the skill that fits: `add-source-module` for a new
   platform, `db-migration` for schema changes, `run-job-radar` to run and
   check the app.
4. **Local checks**, all green, before opening the PR (see "Commands").
5. **PR.** The body says `Closes #N`, then what changed, why, how it was
   tested (paste the check summary) and anything left out.
6. **Audit loop**, below.
7. **Owner review and merge.**

### Audit loop

The builder (the session that wrote the code) runs the `auditor` agent on the
PR. The auditor works in a fresh context with read-only tools and checks the PR
against the `audit-pr` skill's checklist. It posts one PR comment per round,
starting `Audit round N: APPROVE` or `Audit round N: CHANGES_REQUESTED`, with
numbered findings, each marked blocking or non-blocking.

- For each blocking finding the builder either fixes it or disputes it in a
  reply that gives the reason. Then the next round starts.
- In the next round the auditor checks the fixes and rules on each dispute.
- **At most 3 rounds.** On APPROVE the PR gets the `audit:approved` label and
  the owner is told. If round 3 ends without APPROVE, or the auditor upholds a
  finding the builder still disputes, the PR gets the `needs-owner` label and
  one comment that lists each open point with both positions. The agents stop
  there and the owner decides.

Labels: `audit:round-1`, `audit:round-2`, `audit:round-3`, `audit:approved`,
`needs-owner`.

## Data collection policy

Read only data that employers publish so that candidates and job sites can use
it.

**Allowed**
- Documented public job-board APIs and feeds: Greenhouse Job Board API, Lever
  Postings API, Ashby Posting API, Teamtailor `jobs.json`, Workable widget
  feed, Recruitee offers API, Breezy `json`, Jobvite XML feed.
- schema.org `JobPosting` markup (ld+json) on a public careers page, which
  employers publish for search engines to read.

**Not allowed, ever**
- Getting past bot protection or access controls: Cloudflare, Akamai,
  Imperva/Incapsula, PerimeterX, AWS WAF, CAPTCHAs, or 403/429 blocks. That
  includes TLS fingerprint spoofing, headless browsers used to pass a
  challenge, rotating user agents or proxies, and header tricks.
- Taking tokens, CSRF values, JWTs or API keys out of a site's JavaScript or
  session and reusing them.
- Anything that needs a login.
- Collecting personal data about people, such as recruiters' names or emails.

**On every request** (`backend/src/job_radar/http.py` does all of this; source
modules must use its `HttpClient`, never `requests` directly):
- An honest `User-Agent`: `job-radar/<version> (+<CONTACT_URL>)`. If a site
  blocks it, the board is dropped. The client is never disguised.
- robots.txt is checked first, cached 24 hours per host, following RFC 9309:
  a 2xx file is parsed with `urllib.robotparser`, any 4xx means no rules, and a
  5xx or network error means the host is treated as disallowed. (The stdlib's
  own `read()` treats 401/403 as disallow-all; Ashby's API host answers
  robots.txt with 401, and the RFC reading was the owner's call.)
- At most one request per second per host. 429 and 5xx are retried with
  backoff, honouring `Retry-After`.
- Only listing metadata is stored: title, organization, location, posted date,
  workplace type, employment type and URL. The dashboard links to the employer
  for the full text. Descriptions are never stored or shown.

**Excluded platforms.** SmartRecruiters' API host disallows every crawler but
one in robots.txt, so it is not supported. Any other platform, including
undocumented JSON endpoints behind an employer's own careers page, needs the
owner's approval in its issue before it gets a module, and the decision goes
in the module's docstring.

## Stack

- **Backend:** Python 3.11, Flask 3 app factory, gunicorn, SQLAlchemy 2.0
  (typed ORM) with Alembic, psycopg 3, PostgreSQL 16, `requests`,
  BeautifulSoup. Redis 7 arrives in its own PR (see "Roadmap").
- **Frontend:** React 19, TypeScript in strict mode, Vite, Redux Toolkit Query.
- **Tests:** pytest (pytest-socket blocks the network, `responses` fakes HTTP,
  pytest-cov); Vitest with `@testing-library/react` 16 and jsdom.
- **Tooling:** ruff (lint and format), mypy `--strict`, ESLint
  (typescript-eslint strict), `tsc --noEmit`, gitleaks, pre-commit.
- **Runtime:** Docker Compose with `frontend` (nginx serving the build and
  proxying `/api`), `backend`, `worker` and `postgres`, each with a
  healthcheck.

## Architecture

```
backend/src/job_radar/
  app.py              create_app(): blueprints, DB session per request, errors -> JSON
  config.py           typed settings from environment variables
  http.py             HttpClient: honest UA, robots.txt, per-host throttle, retries
  models.py           SQLAlchemy models (migrations in backend/migrations)
  worker.py           scheduled scraper (python -m job_radar.worker)
  cli.py              flask boards import <yaml>, flask scrape
  sources/
    common.py         Board, RawPosting, location-text and employment-type helpers
    options.py        per-platform option declarations and validation
    <platform>.py     one module per allowed platform
  services/
    scraper.py        fetch boards in parallel (8 threads, one client per board)
    refresh.py        one scrape run: fetch, store, record each board's status
    postings_repo.py  upsert postings with first_seen / last_seen / closed_at
    location.py       LocationRule built from the user's settings
    matching.py       job profiles (title terms) and presets
    work_type.py      onsite / hybrid / remote / unknown
    filters.py        posting_key, PostingView, the dashboard filter pipeline
    applications_repo.py  applications and their status history
    boards_repo.py, profiles_repo.py, settings_repo.py, marks_repo.py
  blueprints/         /api/postings, /api/boards, /api/profiles, /api/settings, /api/marks,
                      /api/applications, /api/health
frontend/src/
  redux/api.ts        RTK Query endpoints
  datatypes.ts        mirrors the API's JSON (snake_case)
  lib.ts              pure helpers (sorting, text filter, form parsing)
  components/         PostingsTab, PostingsList, MarksPanel, ProfilesEditor,
                      BoardsEditor, SearchSettingsForm, Badges,
                      ApplicationsTab, ApplicationsList, ApplicationDetail,
                      AddApplicationForm
```

### Source module contract

Every `sources/<platform>.py` exports:
- `PLATFORM_NAME: str`, the display name.
- `SLUG_HELP: str`, which tells the user what to enter as the slug.
- `OPTIONS: dict[str, Option]`, the platform's optional switches.
- `fetch_board(client: HttpClient, board: Board) -> list[RawPosting]`.
- `board_url(board: Board) -> str`, the public page a candidate would open.
- A pure `parse_*` function that turns the raw response into postings, so
  tests can run it on fixtures.

Register the module in `sources/__init__.py`. Boards are rows in the `boards`
table, added in the UI or with `flask boards import`. Platform quirks
(pagination stop rules, date formats, remote flags, slug traps) stay inside
the module and are documented in its docstring.

`RawPosting` is the shared shape:

```python
@dataclass(frozen=True, slots=True)
class RawPosting:
    board_key: str
    org: str
    category: str
    req_id: str
    title: str
    location: str | None
    posted_raw: str
    posted_age_days: int | None
    url: str
    workplace: str | None = None         # the platform's onsite/hybrid/remote field
    employment_type: str | None = None   # full_time, part_time, contract, internship, temporary
```

### Filtering

Postings are stored complete. Every filter runs at read time against the
user's settings, so changing a setting never needs a rescrape.

- **Job profiles** match the title only, since listings carry no description.
  The title must contain an include term and no exclude term, plus a
  seniority term if the profile lists any. Plain terms are case-insensitive
  phrases on word boundaries, with spaces and hyphens between words
  interchangeable or optional. An `advanced` profile uses regexes. The presets
  (`services/matching.py`) were tuned on real titles; the software one is broad
  on purpose, because a stray match costs less than a missed posting.
- **Location rule** (`services/location.py`): states, "City, ST" cities, a
  remote switch, the remote states, and whether to keep unreadable locations.
  Remote counts only when it's open across the whole US, or limited to a state
  the user listed. A state list names where you must live. City names shared
  across states count only next to their state, or with no state named.
- **Employment type**: a posting with an unknown type is kept and badged
  "type unknown", because most boards don't publish it.
- **Dedupe key** is org + title + location (`posting_key`), not `req_id`,
  because some boards list one opening under several ids. Marks use the same
  key.

### Data model

- `boards`: platform, slug, org, category, options, enabled, and the last
  run's status, error and count.
- `postings`: one row per `posting_key`, with `first_seen_at`, `last_seen_at`
  and `closed_at`. A board that fails a run is left untouched, so an outage
  never closes its jobs.
- `posting_marks`: hidden / not interested, by `posting_key`.
- `job_profiles`: name, include/exclude/seniority terms, advanced, position,
  enabled.
- `applications`: jobs being pursued, copied from a posting (`posting_key`,
  unique when set) or entered by hand. They copy the posting's fields, so they
  outlive the posting and its board. `status` is one of saved, applied,
  screening, interviewing, offer, accepted, rejected, withdrawn, ghosted;
  `applied_at` is the first time it became applied.
- `application_events`: one row per status change (from, to, note, time).
  The status only changes by adding an event, so the history always explains
  it; creation records the first event with no `from_status`.
- `app_settings`: one row holding the location rule, default filters, scrape
  interval and visit timestamps. "New since last visit" means first seen after
  `previous_visit_at`.

### API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/postings` | `profile`, `maxAgeDays`, `workType`, `employmentType`, `category` (repeatable), `local=true`. Returns `{postings, failures, scraped_at, refreshing}` |
| POST | `/api/refresh` | Starts a scrape in the background (202) |
| POST | `/api/visits` | Records a dashboard visit for the "New" badges |
| GET | `/api/platforms` | Supported platforms, slug help and options |
| GET / POST | `/api/boards` | List or follow boards |
| PATCH / DELETE | `/api/boards/<id>` | Edit or stop following |
| POST | `/api/boards/validate` | One test fetch, nothing stored |
| GET / POST | `/api/profiles` | List or add job profiles |
| PATCH / DELETE | `/api/profiles/<id>` | Edit or delete |
| GET | `/api/profiles/presets` | Starting points |
| GET / PUT | `/api/settings` | Location rule, default filters, scrape interval |
| GET / POST / DELETE | `/api/marks` | Hidden postings; DELETE takes `?key=<posting_key>` |
| GET / POST | `/api/applications` | List (`status`, repeatable) or create, by hand or from `posting_key`; 409 if that posting already has one. POST takes `status`, `note` (the first event's note) and `notes` (the application's own notes); with `posting_key` the title, org, location and URL come from the posting, `source` is the platform name, and those fields are ignored |
| GET / PATCH / DELETE | `/api/applications/<id>` | One application with its events; PATCH edits fields and notes, never the status |
| POST | `/api/applications/<id>/events` | Change the status: `{to_status, note}` |
| GET | `/api/health` | Checks the database; used by the compose healthcheck |

JSON stays in snake_case end to end, and `frontend/src/datatypes.ts` mirrors it
exactly. The API has one consumer, so there's no camelCase layer.

## Config

| File | In git? | Holds |
|---|---|---|
| `.env.example` | yes | Placeholders: Postgres credentials, `CONTACT_URL`, `HTTP_PORT`, `SCRAPE_WORKERS`, `CORS_ORIGINS` |
| `.env` | **no** | Real values |
| `config/boards.example.yaml` | yes | Demo boards, at least one per platform |
| `config/boards.yaml` | **no** | The owner's own board list, imported with `flask boards import` |

Everything else (profiles, location rule, filters) is set in the UI and stored
in PostgreSQL.

## Commands

```bash
cp .env.example .env                       # then set POSTGRES_PASSWORD
docker compose up -d --build               # UI at http://localhost:8080
docker compose exec backend flask --app job_radar.wsgi boards import config/boards.example.yaml
docker compose exec backend flask --app job_radar.wsgi scrape

# Local checks (run all before opening a PR)
cd backend && ruff check . && ruff format --check . && mypy src
cd backend && TEST_DATABASE_URL=postgresql+psycopg://... pytest -q --cov=job_radar
cd frontend && yarn lint && yarn typecheck && yarn test && yarn build
pre-commit run --all-files                 # includes gitleaks
```

The `run-job-radar` skill has the details, including a throwaway Postgres for
tests.

## Testing

- **Unit tests are required for every change** and run locally: the builder
  before opening the PR and after each fix, and the auditor again on its own.
  CI doesn't run per PR (see "CI").
- **Parser tests** run against recorded fixtures in `backend/tests/fixtures/`.
  Record them with `backend/scripts/record_fixture.py`, which goes through the
  polite client, keeps a few postings and drops descriptions and people's
  names. Review every fixture before committing it.
- **No live HTTP in unit tests.** pytest-socket blocks the network; fake HTTP
  with `responses`.
- **Database and API tests** run against real PostgreSQL at
  `TEST_DATABASE_URL`, each in a transaction rolled back afterwards. The
  fixtures drop every table, so they never fall back to `DATABASE_URL`. They
  skip when no database is reachable, so a green local run must show them
  passing, not skipped. With `REQUIRE_DATABASE=1` (set in CI) a missing
  database fails the run instead.
- **Live checks** against real boards are marked `@pytest.mark.live` and
  excluded by default.

## CI (GitHub Actions)

CI runs **at milestones, not on every push or PR**. `ci.yml` is triggered when
a milestone is closed, when a `v*` tag is pushed (one per milestone, e.g.
`v0.1.0`), or by hand (`workflow_dispatch`). It runs:

1. **backend:** ruff, mypy, `alembic upgrade head` on a fresh database, pytest
   with coverage, against a `postgres:16` service container.
2. **frontend:** `yarn install --frozen-lockfile`, lint, typecheck, Vitest,
   build.
3. **docker:** `docker compose build`.
4. **secrets:** gitleaks.

A red milestone run gets an issue, and the release waits for it. GitHub only
offers a manual run for workflows on the default branch, so a change to
`ci.yml` is first run by hand right after it merges:
`gh workflow run ci.yml --ref main`. `main` needs
a PR and a linear history; there are no required status checks, since CI
doesn't run per PR.

## Roadmap

Milestone `v0.1`, one PR each:
1. Milestone CI, issue and PR templates.
2. Applications tab: status pipeline (saved, applied, screening, interviewing,
   offer, accepted, rejected, withdrawn, ghosted), status history with notes,
   manual entries for jobs found elsewhere. Marking a posting "Applied" copies
   it into Applications.
3. Redis: shared per-board cache and lock, a per-host rate limiter shared
   across processes, and a scheduler lock.
4. `scrape_runs` history and a health column for boards.
5. README with a screenshot, architecture diagram and quick start.

Later: more platforms, one PR each and only after the owner approves the
platform.
