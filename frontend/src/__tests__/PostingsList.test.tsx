import {fireEvent, render, screen, within} from '@testing-library/react';
import {beforeAll, describe, expect, it, vi} from 'vitest';
import {PostingsList} from '../components/PostingsList';
import {postedLabel, sortPostings} from '../lib';
import {posting} from './factories';

beforeAll(() => {
  // jsdom has no matchMedia; report a wide screen so the table renders.
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

describe('sortPostings', () => {
  it('puts new postings first, then newest, undated last', () => {
    const old = posting({title: 'Old', posted_age_days: 20});
    const fresh = posting({title: 'Fresh', posted_age_days: 1});
    const undated = posting({title: 'Undated', posted_age_days: null});
    const brandNew = posting({title: 'New', posted_age_days: 10, is_new: true});
    expect(sortPostings([old, undated, fresh, brandNew], 'posted', false).map((p) => p.title)).toEqual(
      ['New', 'Fresh', 'Old', 'Undated'],
    );
    // Undated stays last when the direction flips.
    expect(sortPostings([old, undated, fresh], 'posted', true).map((p) => p.title)).toEqual([
      'Old',
      'Fresh',
      'Undated',
    ]);
  });
});

describe('postedLabel', () => {
  it('describes the age', () => {
    expect(postedLabel(posting({posted_age_days: null}))).toBe('no date');
    expect(postedLabel(posting({posted_age_days: 0}))).toBe('today');
    expect(postedLabel(posting({posted_age_days: 1}))).toBe('1 day ago');
    expect(postedLabel(posting({posted_age_days: 5}))).toBe('5 days ago');
  });
});

describe('PostingsList', () => {
  it('shows an empty message', () => {
    render(<PostingsList postings={[]} />);
    expect(screen.getByText(/No postings match/)).toBeTruthy();
  });

  it('renders rows with badges and a link to the employer', () => {
    const p = posting({title: 'Backend Engineer', is_new: true, employment_type: null, work_type: 'remote'});
    render(<PostingsList postings={[p]} />);
    const link = screen.getByRole('link', {name: 'Backend Engineer'});
    expect(link.getAttribute('href')).toBe(p.url);
    const row = link.closest('tr');
    expect(row).not.toBeNull();
    const cells = within(row as HTMLElement);
    expect(cells.getByText('New')).toBeTruthy();
    expect(cells.getByText('Remote')).toBeTruthy();
    expect(cells.getByText('type unknown')).toBeTruthy();
  });

  it('sorts by a column when its header is clicked', () => {
    const b = posting({org: 'Beta'});
    const a = posting({org: 'Alpha'});
    render(<PostingsList postings={[b, a]} />);
    fireEvent.click(screen.getByRole('button', {name: /Organization/}));
    const orgs = screen.getAllByRole('row').slice(1).map((r) => r.firstElementChild?.textContent);
    expect(orgs).toEqual(['Alpha', 'Beta']);
  });

  it('calls onMark with the chosen status', () => {
    const onMark = vi.fn();
    const p = posting();
    render(<PostingsList postings={[p]} onMark={onMark} />);
    fireEvent.change(screen.getByLabelText(`Hide ${p.title}`), {target: {value: 'not_interested'}});
    expect(onMark).toHaveBeenCalledWith(p, 'not_interested');
  });
});
