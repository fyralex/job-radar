import type {ApplicationWithEvents, Posting} from '../datatypes';

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

let nextApplication = 1;

export function application(overrides: Partial<ApplicationWithEvents> = {}): ApplicationWithEvents {
  const id = nextApplication++;
  return {
    id,
    posting_key: null,
    title: `Analyst ${id}`,
    org: 'Elsewhere Inc',
    location: 'Remote',
    url: `https://example.com/apply/${id}`,
    source: 'referral',
    status: 'saved',
    applied_at: null,
    notes: '',
    created_at: '2026-03-01T12:00:00Z',
    updated_at: '2026-03-01T12:00:00Z',
    events: [{id: id * 10, from_status: null, to_status: 'saved', note: '', at: '2026-03-01T12:00:00Z'}],
    ...overrides,
  };
}
