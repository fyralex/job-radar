# Job Radar

A self-hosted dashboard for your job search. Follow employers' public job
boards, describe the jobs you want, and see the matching postings in one place:
filtered by title, location, remote policy, posting age and employment type,
with "new since your last visit" badges. Track the jobs you apply to, from
saved to offer.

![The Postings tab with the demo boards](docs/screenshot.png)

- **Your preferences, not hardcoded ones.** Job profiles hold the title terms
  you care about. Start from a preset (software engineering, biostatistics,
  HEOR/real-world evidence) or write your own. Each profile is a tab with its
  own posting count.
- **Filters that stay out of the way.** Search by words, set the posting age,
  and narrow by work type, employment type, local only, new only, or hide
  senior roles. Long lists scroll in their own box with the headers in view.
- **Location that understands remote.** List the states and cities you'd work
  in on site. Remote jobs count only when they're open across the US, or
  limited to a state you listed.
- **Applications.** Use a posting's **Actions** menu to mark it applied, or
  add a job you found elsewhere. Then move it through saved, applied,
  screening, interviewing, offer and the rest, with a dated history and notes.
  The same menu hides postings you don't want.
- **Board health.** Settings shows each board's last few refreshes, so a board
  that stopped working is easy to spot.
- **Polite by design.** It reads only public job-board feeds, identifies itself
  honestly, follows robots.txt, makes at most one request per second per site,
  and stores listing metadata only. It never stores job descriptions.

Supported platforms: Greenhouse, Lever, Ashby, Workable, Teamtailor, Breezy,
Recruitee, Jobvite, and any careers page with schema.org `JobPosting` markup.

## Quick start

You need Docker with Compose.

```bash
cp .env.example .env              # set POSTGRES_PASSWORD (and CONTACT_URL, see below)
docker compose up -d --build
docker compose exec backend flask --app job_radar.wsgi boards import config/boards.example.yaml
```

Open http://localhost:8080. Under **Settings**, add a job profile and your
location. Then press **Refresh now**, or wait for the scheduled refresh.

`config/boards.example.yaml` holds demo boards, one or more per platform. Put
your own list in `config/boards.yaml` (git ignores it) and import that, or add
boards one at a time under **Settings > Boards**, where **Test fetch** checks
a board before you add it.

## Configuration

Settings come from `.env` (copied from `.env.example`, never committed).
Everything else (job profiles, location, filters, the refresh interval) is set
in the UI and stored in PostgreSQL.

| Variable | Default | What it does |
|---|---|---|
| `POSTGRES_PASSWORD` | (required) | Password for the bundled PostgreSQL |
| `POSTGRES_USER`, `POSTGRES_DB` | `jobradar` | PostgreSQL user and database |
| `CONTACT_URL` | empty | Added to the scraper's User-Agent so board operators can see who is calling, e.g. the URL of your fork |
| `HTTP_PORT` | `8080` | Port for the UI; `127.0.0.1:8080` listens on this machine only (see below) |
| `SCRAPE_WORKERS` | `8` | Boards fetched in parallel (requests to one site still go one per second) |
| `REDIS_URL` | set by Compose | Only needed when running the backend outside Compose |
| `CORS_ORIGINS` | empty | Only needed when the UI is served from another origin |

## Running it on a server

Job Radar has **no login**: anyone who can reach its port sees your profiles
and applications. On your own computer that's fine. On a server, keep it
private. Never expose the port to the internet as it is.

First set `HTTP_PORT=127.0.0.1:8080` in `.env`, so the UI listens on the
server itself only. Then pick one way in:

- **SSH tunnel** (nothing else to install): run
  `ssh -L 8080:127.0.0.1:8080 you@your-server` on your computer and open
  http://localhost:8080 there.
- **Tailscale**: run `tailscale serve --bg 8080` on the server. It serves the
  app over HTTPS to your own tailnet devices only.
- **A reverse proxy with a password** on the same server, such as Caddy with
  `basic_auth` or nginx with `auth_basic`, forwarding to `127.0.0.1:8080` and
  adding HTTPS.

(Binding to a private address instead, e.g. `HTTP_PORT=<your WireGuard or
Tailscale IP>:8080`, also works; any device on that network can then reach it.)

Run these commands from the project folder, so they reach this install's
database.

**Back up** the database. Redis holds only short-lived locks and needs no
backup. A dump holds your profiles, applications and notes, so each one goes
to its own dated file outside the project folder (never commit it), readable
only by you. It's written to a temporary file first, so a failed backup never
replaces a good one:

```bash
(umask 077; mkdir -p ~/job-radar-backups
 f=~/job-radar-backups/job-radar-$(date +%F-%H%M).sql
 docker compose exec -T postgres sh -c 'pg_dump --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$f.tmp" && mv "$f.tmp" "$f")
```

A leftover `.tmp` file is a backup that failed and can be deleted. (An older
version of these steps wrote a single `~/job-radar-backup.sql`; move it into
`~/job-radar-backups/` or delete it.)

**Restore** a backup. Set `f` to the file you want. The backup is checked
first (it must end with pg_dump's "dump complete" line), then the database is
emptied and the backup loaded in one transaction, so anything that goes wrong
leaves your current data exactly as it was:

```bash
f=~/job-radar-backups/job-radar-YYYY-MM-DD-HHMM.sql   # the backup to restore
docker compose stop backend worker
if tail -n 5 "$f" 2>/dev/null | grep -q 'PostgreSQL database dump complete'; then
  { echo 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'; cat "$f"; } |
    docker compose exec -T postgres sh -c 'psql -q -1 -v ON_ERROR_STOP=1 -o /dev/null -f - -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    && echo "Restored." || echo "Restore failed: nothing was changed."
else
  echo "Not a complete backup, nothing was changed: $f"
fi
docker compose start backend worker
```

A backup works with the version it was taken with or any newer one (the
backend brings the data up to date when it starts), but not with an older one.

**Update** to a newer version (take a backup first):

```bash
git pull
docker compose up -d --build    # database changes apply when the backend starts
```

**Roll back** an update that went wrong: restore the backup you took before
it (the steps above, but leave out the last line, so the backend and worker
stay stopped), then go back to the version you were on and start it:

```bash
git checkout v0.1.0             # the release or commit you were on before
docker compose up -d --build
```

This leaves git on that release. To update again later, run
`git checkout main` before `git pull`.

The data lives in the `pgdata` Docker volume, so it survives restarts and
rebuilds. `docker compose down -v` deletes it.

## How it works

```mermaid
flowchart LR
    user([You]) --> frontend["frontend<br/>nginx + React UI"]
    frontend -- "/api" --> backend["backend<br/>Flask API"]
    backend --> postgres[("PostgreSQL<br/>boards, postings,<br/>profiles, applications")]
    worker["worker<br/>scheduled refresh"] --> postgres
    backend -- "Refresh now" --> boards
    worker --> boards[["Public job-board APIs<br/>and careers pages"]]
    backend <--> redis[("Redis<br/>locks and the<br/>per-site rate limit")]
    worker <--> redis
```

- The **worker** refreshes every board on a schedule. **Refresh now** in the
  UI starts the same refresh from the backend.
- **Redis** holds a lock so two refreshes never run at once, and the
  one-request-per-second limit for each site, shared by the worker and the
  backend.
- Postings are stored once and filtered when you read them, so changing a
  setting never needs a new refresh.

## Data collection

Job Radar reads only what employers publish for candidates and job sites to
use: documented public job-board APIs and feeds, and schema.org `JobPosting`
markup on public careers pages. On every request it:

- sends an honest User-Agent (`job-radar/<version>`, plus your `CONTACT_URL`),
- checks robots.txt first and respects it,
- waits at least one second between requests to the same site, including
  redirects and robots.txt itself,
- stores only listing metadata (title, organization, location, dates, work and
  employment type, link) and never job descriptions or people's names.

It never works around bot protection, logins or blocks. A board that blocks it
is dropped. The full policy is in [CLAUDE.md](CLAUDE.md#data-collection-policy).

## Development

See [CLAUDE.md](CLAUDE.md) for the architecture, the data model, the full data
collection policy and the contribution workflow: every change starts as a
GitHub issue, lands through a pull request, and is audited before the owner
merges it. The local checks:

```bash
cd backend && ruff check . && ruff format --check . && mypy src
cd backend && TEST_DATABASE_URL=postgresql+psycopg://... TEST_REDIS_URL=redis://... pytest -q -rs
cd frontend && yarn lint && yarn typecheck && yarn test && yarn build
```

The database and Redis tests need a throwaway PostgreSQL and Redis; the
`run-job-radar` skill in `.claude/skills/` shows how to start them.

## License

MIT. See [LICENSE](LICENSE).
