import {render, screen, within} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {BoardHealth} from '../components/BoardHealth';
import type {ScrapeRun} from '../datatypes';
import {runLabel} from '../lib';

const ok = (day: number, count: number): ScrapeRun => ({
  started_at: `2026-03-0${day}T12:00:00Z`,
  finished_at: `2026-03-0${day}T12:00:05Z`,
  status: 'ok',
  count,
  error: null,
});
const failed: ScrapeRun = {
  started_at: '2026-03-04T12:00:00Z',
  finished_at: '2026-03-04T12:00:01Z',
  status: 'error',
  count: null,
  error: 'HTTP 404',
};

describe('runLabel', () => {
  it('gives the count or the error', () => {
    expect(runLabel(ok(1, 12))).toMatch(/2026.*: 12 postings$/);
    expect(runLabel(ok(1, 1))).toMatch(/: 1 posting$/);
    expect(runLabel(failed)).toMatch(/: failed \(HTTP 404\)$/);
    expect(runLabel({...failed, error: null})).toMatch(/failed \(unknown error\)$/);
  });
});

describe('BoardHealth', () => {
  it('shows recent runs oldest first, each labelled, and the latest outcome', () => {
    render(
      <BoardHealth
        board={{
          recent_runs: [ok(1, 10), ok(2, 11), failed],
          last_status: 'error',
          last_count: 11,
          last_error: 'HTTP 404',
        }}
      />,
    );
    const dots = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(dots).toHaveLength(3);
    expect(dots.map((d) => d.className)).toEqual(['dot dot-ok', 'dot dot-ok', 'dot dot-error']);
    expect(dots[2]?.getAttribute('aria-label')).toMatch(/failed \(HTTP 404\)/);
    expect(dots[0]?.getAttribute('title')).toMatch(/10 postings/);
    expect(screen.getByText('failed').getAttribute('title')).toBe('HTTP 404');
  });

  it('shows the count after a good run', () => {
    render(
      <BoardHealth
        board={{recent_runs: [ok(1, 7)], last_status: 'ok', last_count: 7, last_error: null}}
      />,
    );
    expect(screen.getByText('7 postings')).toBeTruthy();
  });

  it('says "not yet" before the first run, with no dots', () => {
    render(
      <BoardHealth
        board={{recent_runs: [], last_status: null, last_count: null, last_error: null}}
      />,
    );
    expect(screen.queryByRole('list')).toBeNull();
    expect(screen.getByText('not yet')).toBeTruthy();
  });
});
