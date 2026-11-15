import type {Posting} from '../datatypes';

let next = 1;

export function posting(overrides: Partial<Posting> = {}): Posting {
  const id = next++;
  return {
    id,
    posting_key: `acme|engineer ${id}|austin, tx`,
    board_id: 1,
    org: 'Acme',
    category: 'Tech',
    title: `Engineer ${id}`,
    location: 'Austin, TX',
    url: `https://example.com/jobs/${id}`,
    posted_on: '2026-01-01',
    posted_age_days: 3,
    work_type: 'onsite',
    employment_type: 'full_time',
    first_seen_at: '2026-01-01T00:00:00Z',
    is_new: false,
    local: true,
    ...overrides,
  };
}
