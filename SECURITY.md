# Security policy

## Reporting a problem

Please report security problems **privately**, not in a public issue: use
GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository (the **Security** tab, then **Report a vulnerability**).

Include what you found, how to reproduce it, and what an attacker could do
with it. You'll get a reply as soon as the maintainer can look at it; this is
a one-person project, so please allow some time. Once a fix is released, the
report can be published as an advisory, with credit if you'd like it.

## What's in scope

- The backend API, the worker and the frontend in this repository.
- The scraper's behaviour toward job boards: anything that would make it
  ignore robots.txt, exceed one request per second per site, disguise itself,
  or get past access controls breaks the project's
  [data collection policy](CLAUDE.md#data-collection-policy) and counts as a
  bug worth reporting.
- Secrets or personal data committed to the repository.

## Known limits (by design, not vulnerabilities)

- **There is no login.** Job Radar is a single-user, self-hosted app. Anyone
  who can reach its port can read and change its data. Don't expose it to a
  network you don't trust: see
  [Running it on a server](README.md#running-it-on-a-server) for safe ways to
  reach it remotely.
- Database backups contain your personal job-search data and are yours to
  keep safe. The README's backup steps write them outside the project folder,
  readable only by you.

## Supported versions

Only the latest release (and `main`) gets fixes.
