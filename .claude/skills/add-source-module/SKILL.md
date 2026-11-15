---
name: add-source-module
description: Add support for a new job-board platform to Job Radar - policy check first, then the module, a recorded fixture, parser tests and registration. Use when a user wants to follow boards on a platform that isn't supported yet, or a platform's feed changed.
---

# Add a source module

## 0. Policy check (stop here if it fails)

- Is the platform on CLAUDE.md's allowed list (documented public API or feed,
  or schema.org JobPosting markup)? If not, the issue must contain the owner's
  written approval for this platform by name. No approval: stop and ask.
- Fetch the endpoint's host `robots.txt` and check the path is allowed for
  `job-radar` (RFC 9309 rules, as in `http.py`). Disallowed: stop and tell the
  owner. Don't look for another route.
- With the honest User-Agent, does the endpoint answer 200 without cookies,
  tokens or a challenge page? A 403/429, a challenge or a login means stop.

## 1. Module

Create `backend/src/job_radar/sources/<platform>.py`, modelled on
`greenhouse.py` (one JSON request) or `jobvite.py` (XML, grouping rows):

- Docstring: the endpoint, what the slug is, every quirk (pagination stop
  rule, date format, remote flag, one row per location, slug traps), and the
  approval reference if it isn't on the allowed list.
- `PLATFORM_NAME`, `SLUG_HELP`, `OPTIONS` (declare every option with
  `Option("bool" | "list", help)`).
- `board_url(board)`: the public page a candidate opens.
- A pure `parse_*(payload, board) -> list[RawPosting]`. Raise
  `BoardFetchError` on an unexpected shape. Use `clean_title`,
  `parse_iso_date`/`age_days`, `with_remote_marker` for the platform's remote
  flag, `normalize_employment_type` falling back to
  `employment_type_from_title`, and set `workplace` when the platform has the
  field.
- `fetch_board(client, board)`: only `client.get` / `client.get_json`.
  Paginated feeds stop on a short page, `offset >= total`, or a page that adds
  nothing new, and dedupe by URL.
- Never store descriptions or people's names.

Register it in `sources/__init__.py` (`_MODULES`).

## 2. Fixture

```bash
cd backend
.venv/bin/python scripts/record_fixture.py <platform> <well-known-public-slug> tests/fixtures/<platform>.json
```

Add the platform's URL to `URLS` in the script first. Open the fixture and
check it by eye: a few postings, no descriptions, no person's name or email.
Pick a well-known public company, not one from anyone's personal job search.

## 3. Tests

In `tests/test_sources.py`, add a `Test<Platform>` class:
- the fixture parses into complete postings (`_complete`),
- one small inline case per documented quirk,
- a bad payload raises `BoardFetchError`.

`test_every_platform_exports_the_contract` covers registration.

## 4. Docs

- CLAUDE.md: add the platform to the allowed list (or note the approval).
- `config/boards.example.yaml`: add one demo board.

Then continue with the `feature-workflow` skill (local checks, PR, audit).
