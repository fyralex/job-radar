---
name: db-migration
description: Change the Job Radar database schema safely - edit the SQLAlchemy models, autogenerate and review an Alembic migration, test upgrade and downgrade on a throwaway Postgres. Use for any change to backend/src/job_radar/models.py.
---

# Database migration

Rules:
- One migration per PR, ids in order (`0002`, `0003`, ...).
- Never drop a column or table, or narrow a type, without the owner's OK in
  the issue. Prefer adding a column, backfilling, and removing the old one in
  a later PR.
- New non-null columns on existing tables need a `server_default`, or a
  backfill before the NOT NULL constraint is added.

## Steps

1. Edit `backend/src/job_radar/models.py` (typed `Mapped[...]` columns).
2. Start a throwaway database (see the `run-job-radar` skill) and bring it to
   the current head:

   ```bash
   cd backend
   export DATABASE_URL=postgresql+psycopg://jobradar:jobradar@127.0.0.1:55432/jobradar
   .venv/bin/alembic upgrade head
   ```

3. Autogenerate, giving the next id:

   ```bash
   .venv/bin/alembic revision --autogenerate -m "<what changed>" --rev-id 0002
   ```

4. Read the generated file. Autogenerate misses renames (it shows them as a
   drop plus an add), server defaults and data backfills, so fix those by
   hand. Then run `.venv/bin/ruff format migrations`.
5. Round-trip it:

   ```bash
   .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head
   ```

6. Tests: the test suite builds tables from the models (`Base.metadata`), so
   also check the migration matches them. After `upgrade head`,
   `alembic check` must report no differences.
7. Update the "Data model" section of CLAUDE.md.
