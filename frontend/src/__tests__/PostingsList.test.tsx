import {fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {PostingsList} from '../components/PostingsList';
import {applyNotice, postedLabel, sortPostings} from '../lib';
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

  it('hides a posting from its actions menu', () => {
    const onMark = vi.fn();
    const p = posting();
    render(<PostingsList postings={[p]} onMark={onMark} />);
    fireEvent.click(screen.getByRole('button', {name: `Actions for ${p.title}`}));
    fireEvent.click(screen.getByRole('button', {name: 'Not interested'}));
    expect(onMark).toHaveBeenCalledWith(p, 'not_interested');
  });
});

function setScreen(narrow: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: narrow,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

describe('PostingsList actions menu', () => {
  afterEach(() => setScreen(false));

  it('opens a panel of buttons; nothing happens until one is pressed', () => {
    const onApply = vi.fn();
    const onMark = vi.fn();
    const p = posting({title: 'Data Engineer'});
    render(<PostingsList postings={[p]} onApply={onApply} onMark={onMark} />);
    const toggle = screen.getByRole('button', {name: 'Actions for Data Engineer'});
    expect(toggle.getAttribute('aria-expanded')).toBe('false');

    // Keys on the closed button (an arrow press acted at once on the old select).
    fireEvent.keyDown(toggle, {key: 'ArrowDown'});
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    const panel = screen.getByRole('group', {name: 'Actions for Data Engineer'});
    expect(within(panel).getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Mark as applied',
      'Hide',
      'Not interested',
    ]);
    expect(onApply).not.toHaveBeenCalled();
    expect(onMark).not.toHaveBeenCalled();
    // All three look the same; none is singled out (owner's choice).
    expect(within(panel).getAllByRole('button').map((b) => b.className)).toEqual([
      'secondary',
      'secondary',
      'secondary',
    ]);

    fireEvent.click(within(panel).getByRole('button', {name: 'Mark as applied'}));
    expect(onApply).toHaveBeenCalledWith(p);
    expect(onMark).not.toHaveBeenCalled();
    expect(screen.queryByRole('group')).toBeNull(); // closes after a choice
  });

  it('scrolls the panel into view when it opens (the list box clips it on the last rows)', () => {
    const scrollIntoView = vi.fn();
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoView;
    try {
      render(<PostingsList postings={[posting({title: 'Last'})]} onApply={vi.fn()} />);
      fireEvent.click(screen.getByRole('button', {name: 'Actions for Last'}));
      expect(scrollIntoView).toHaveBeenCalledWith({block: 'nearest'});
      expect(scrollIntoView.mock.contexts[0]).toBe(screen.getByRole('group'));
    } finally {
      Element.prototype.scrollIntoView = original;
    }
  });

  it('closes on Escape without acting', () => {
    const onApply = vi.fn();
    const p = posting({title: 'Analyst'});
    render(<PostingsList postings={[p]} onApply={onApply} />);
    const toggle = screen.getByRole('button', {name: 'Actions for Analyst'});
    fireEvent.click(toggle);
    fireEvent.keyDown(document, {key: 'Escape'});
    expect(screen.queryByRole('group')).toBeNull();
    expect(document.activeElement).toBe(toggle);
    expect(onApply).not.toHaveBeenCalled();
  });

  it('is the same menu on phone-width cards', () => {
    setScreen(true);
    const onApply = vi.fn();
    const p = posting({title: 'Analyst'});
    render(<PostingsList postings={[p]} onApply={onApply} />);
    expect(screen.queryByRole('table')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Actions for Analyst'}));
    fireEvent.click(screen.getByRole('button', {name: 'Mark as applied'}));
    expect(onApply).toHaveBeenCalledWith(p);
  });

  it('moves focus to the next posting once an action takes one out of the list', () => {
    const a = posting({title: 'First', posted_age_days: 1});
    const b = posting({title: 'Second', posted_age_days: 2});
    const onMark = vi.fn();
    const {rerender} = render(<PostingsList postings={[a, b]} onMark={onMark} />);
    fireEvent.click(screen.getByRole('button', {name: 'Actions for First'}));
    fireEvent.click(screen.getByRole('button', {name: 'Hide'}));
    expect(onMark).toHaveBeenCalledWith(a, 'hidden');

    // The posting is still listed until the server confirms: focus stays put.
    rerender(<PostingsList postings={[a, b]} onMark={onMark} />);
    expect(document.activeElement).not.toBe(screen.getByRole('button', {name: 'Actions for Second'}));

    rerender(<PostingsList postings={[b]} onMark={onMark} />);
    expect(document.activeElement).toBe(screen.getByRole('button', {name: 'Actions for Second'}));
  });

  it('leaves focus alone if the user moved on after an action that failed', () => {
    const a = posting({title: 'First', posted_age_days: 1});
    const b = posting({title: 'Second', posted_age_days: 2});
    const onMark = vi.fn();
    const {rerender} = render(
      <>
        <input aria-label="search" />
        <PostingsList postings={[a, b]} onMark={onMark} />
      </>,
    );
    fireEvent.click(screen.getByRole('button', {name: 'Actions for First'}));
    fireEvent.click(screen.getByRole('button', {name: 'Hide'}));
    // The action failed: First is still listed, focus is back on its button.
    expect(document.activeElement).toBe(screen.getByRole('button', {name: 'Actions for First'}));
    // The user moves to the search box, and a filter later removes First.
    const search = screen.getByLabelText('search');
    search.focus();
    rerender(
      <>
        <input aria-label="search" />
        <PostingsList postings={[b]} onMark={onMark} />
      </>,
    );
    expect(document.activeElement).toBe(search);
  });

  it('moves focus to the previous posting when the last one goes', () => {
    const a = posting({title: 'First', posted_age_days: 1});
    const b = posting({title: 'Second', posted_age_days: 2});
    const onApply = vi.fn();
    const {rerender} = render(<PostingsList postings={[a, b]} onApply={onApply} />);
    fireEvent.click(screen.getByRole('button', {name: 'Actions for Second'}));
    fireEvent.click(screen.getByRole('button', {name: 'Mark as applied'}));
    rerender(<PostingsList postings={[a]} onApply={onApply} />);
    expect(document.activeElement).toBe(screen.getByRole('button', {name: 'Actions for First'}));
  });

  it('focuses the empty-list message when the only posting goes', () => {
    const a = posting({title: 'Only'});
    const onMark = vi.fn();
    const {rerender} = render(<PostingsList postings={[a]} onMark={onMark} />);
    fireEvent.click(screen.getByRole('button', {name: 'Actions for Only'}));
    fireEvent.click(screen.getByRole('button', {name: 'Not interested'}));
    rerender(<PostingsList postings={[]} onMark={onMark} />);
    expect(document.activeElement).toBe(screen.getByText(/No postings match/));
  });

  it('has no action column without handlers', () => {
    render(<PostingsList postings={[posting()]} />);
    expect(screen.queryByRole('button', {name: /^Actions for/})).toBeNull();
    expect(screen.getAllByRole('columnheader')).toHaveLength(4);
  });
});

describe('applyNotice', () => {
  it('confirms a new application', () => {
    expect(applyNotice('Analyst', undefined)).toEqual({
      text: 'Added “Analyst” to Applications as Applied.',
      error: false,
    });
  });

  it('treats a 409 (already added, e.g. a double-click) as success', () => {
    const conflict = {status: 409, data: {error: 'that posting already has an application'}};
    expect(applyNotice('Analyst', conflict)).toEqual({
      text: '“Analyst” is already in Applications.',
      error: false,
    });
  });

  it('shows other errors with the server message', () => {
    expect(applyNotice('Analyst', {status: 400, data: {error: 'no posting with that posting_key'}})).toEqual({
      text: 'Couldn’t add “Analyst”: no posting with that posting_key',
      error: true,
    });
    expect(applyNotice('Analyst', {status: 'FETCH_ERROR', error: 'offline'}).error).toBe(true);
  });
});

describe('PostingsList scroll area', () => {
  afterEach(() => setScreen(false));

  it('puts the table in a focusable scroll region with its own headers', () => {
    render(<PostingsList postings={[posting()]} />);
    const region = screen.getByRole('region', {name: 'Postings'});
    expect(region.className).toContain('scroll-area');
    expect(region.getAttribute('tabindex')).toBe('0'); // keyboard users can scroll it
    expect(within(region).getByRole('table')).toBeTruthy();
    expect(within(region).getAllByRole('columnheader')).toHaveLength(4);
  });

  it('scrolls the phone cards the same way, with the sort menu outside', () => {
    setScreen(true);
    render(<PostingsList postings={[posting()]} />);
    const region = screen.getByRole('region', {name: 'Postings'});
    expect(within(region).getAllByRole('listitem')).toHaveLength(1);
    expect(within(region).queryByLabelText(/Sort by/)).toBeNull();
    expect(screen.getByLabelText(/Sort by/)).toBeTruthy();
  });
});
