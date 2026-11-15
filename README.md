# Job Radar

A self-hosted dashboard for your job search. Follow employers' public job
boards, describe the jobs you want, and see the matching postings in one place:
filtered by title, location, remote policy, posting age and employment type,
with "new since your last visit" badges.

- **Your preferences, not hardcoded ones.** Job profiles hold the title terms
  you care about. Start from a preset (software engineering, biostatistics,
  HEOR/real-world evidence) or write your own.
- **Location that understands remote.** List the states and cities you'd work
  in on site. Remote jobs count only when they're open across the US, or
  limited to a state you listed.
- **Polite by design.** It reads only public job-board feeds, identifies itself
  honestly, follows robots.txt, makes at most one request per second per site,
  and stores listing metadata only. It never stores job descriptions.

Supported platforms: Greenhouse, Lever, Ashby, Workable, Teamtailor, Breezy,
Recruitee, Jobvite, and any careers page with schema.org `JobPosting` markup.

## Quick start

```bash
cp .env.example .env              # set POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec backend flask --app job_radar.wsgi boards import config/boards.example.yaml
```

Open http://localhost:8080. Under **Settings**, add a job profile and your
location. Then press **Refresh now**, or wait for the scheduled refresh.

## Development

See [CLAUDE.md](CLAUDE.md) for the architecture, the data collection policy,
and the contribution workflow (issue → pull request → audit). Checks:

```bash
cd backend && ruff check . && mypy src && pytest -q
cd frontend && yarn lint && yarn typecheck && yarn test
```

## License

MIT. See [LICENSE](LICENSE).
