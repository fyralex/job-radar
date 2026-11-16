import type {Posting, RefreshResult, ScrapeRun} from './datatypes';
import {errorText} from './errors';

// Pure helpers shared by components and tests.

export type SortKey = 'org' | 'title' | 'location' | 'posted';

function compare(a: Posting, b: Posting, key: SortKey): number {
  if (key === 'posted') {
    // Undated postings sort after dated ones in either direction.
    if (a.posted_age_days === null && b.posted_age_days === null) return 0;
    if (a.posted_age_days === null) return 1;
    if (b.posted_age_days === null) return -1;
    return a.posted_age_days - b.posted_age_days;
  }
  const value = (p: Posting) =>
    key === 'org' ? p.org : key === 'title' ? p.title : (p.location ?? '');
  return value(a).localeCompare(value(b), undefined, {sensitivity: 'base'});
}

// New postings first, then the chosen column; undated postings stay last.
export function sortPostings(postings: Posting[], key: SortKey, desc: boolean): Posting[] {
  return [...postings].sort((a, b) => {
    const byNew = Number(b.is_new) - Number(a.is_new);
    if (byNew !== 0) return byNew;
    const primary = compare(a, b, key);
    const undatedTie = key === 'posted' && (a.posted_age_days === null || b.posted_age_days === null);
    const ordered = desc && !undatedTie ? -primary : primary;
    return ordered !== 0 ? ordered : compare(a, b, 'org');
  });
}

export function postedLabel(p: Posting): string {
  if (p.posted_age_days === null) return 'no date';
  if (p.posted_age_days <= 0) return 'today';
  if (p.posted_age_days === 1) return '1 day ago';
  return `${p.posted_age_days} days ago`;
}

// Every typed word must appear in the title, organization or location.
export function matchesText(posting: Posting, text: string): boolean {
  const haystack = `${posting.title} ${posting.org} ${posting.location ?? ''}`.toLowerCase();
  return text
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word));
}

// One term per line in the profile textareas.
export function parseTerms(text: string): string[] {
  return text
    .split('\n')
    .map((t) => t.trim())
    .filter(Boolean);
}

// Cities are separated by semicolons or newlines ("Austin, TX; Denver, CO").
export function splitList(text: string): string[] {
  return text
    .split(/[;\n]/)
    .map((v) => v.trim())
    .filter(Boolean);
}

export function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

// "Nov 15, 2026" in the browser's locale; the API sends ISO timestamps.
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

// The notice after "Applied". A 409 means the posting is already in
// Applications (e.g. the second request of a double-click), which is what the
// user wanted, so it isn't shown as an error.
export function applyNotice(
  title: string,
  error: Parameters<typeof errorText>[0],
): {text: string; error: boolean} {
  if (!error) return {text: `Added “${title}” to Applications as Applied.`, error: false};
  if ('status' in error && error.status === 409) {
    return {text: `“${title}” is already in Applications.`, error: false};
  }
  return {text: `Couldn’t add “${title}”: ${errorText(error)}`, error: true};
}

// What to tell the user after "Refresh now"; null when a run started (the
// button itself then shows "Refreshing…").
export function refreshNotice(
  result: RefreshResult | undefined,
  error: Parameters<typeof errorText>[0],
): string | null {
  if (error) return `Couldn’t start a refresh: ${errorText(error)}`;
  if (!result || result.started) return null;
  if (result.reason === 'already_running') {
    return 'A refresh is already running; new postings appear when it finishes.';
  }
  return 'Refreshing is unavailable right now (the lock service is down). Try again later.';
}

// One scrape run for a tooltip and screen readers, e.g.
// "Nov 15, 2026, 9:30 AM: 12 postings" or "...: failed (HTTP 404)".
export function runLabel(run: ScrapeRun): string {
  const when = new Date(run.started_at).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
  if (run.status === 'error') return `${when}: failed (${run.error ?? 'unknown error'})`;
  const count = run.count ?? 0;
  return `${when}: ${count} ${count === 1 ? 'posting' : 'postings'}`;
}
