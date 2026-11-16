import {fireEvent, render, screen} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {ALL, ProfileTabs} from '../components/ProfileTabs';
import type {Profile} from '../datatypes';

const profile = (id: number, name: string, enabled = true): Profile => ({
  id,
  name,
  include_terms: ['x'],
  exclude_terms: [],
  seniority_terms: [],
  advanced: false,
  position: id,
  enabled,
});
const PROFILES = [profile(1, 'Software'), profile(2, 'Data'), profile(3, 'Off', false)];

describe('ProfileTabs', () => {
  it('shows a tab per enabled profile plus All postings, each with its count', () => {
    render(
      <ProfileTabs
        profiles={PROFILES}
        selected="2"
        counts={{all: 52, '1': 40, '2': 7}}
        onSelect={vi.fn()}
      />,
    );
    // Screen readers hear "Software, 40 postings"; the pill itself is hidden from them.
    expect(screen.getByRole('tab', {name: 'Software , 40 postings'})).toBeTruthy();
    expect(screen.getByRole('tab', {name: 'All postings , 52 postings'})).toBeTruthy();
    const data = screen.getByRole('tab', {name: /^Data/});
    expect(data.getAttribute('aria-selected')).toBe('true');
    expect(data.className).toBe('subtab active');
    expect(data.querySelector('.tab-count')?.textContent).toBe('7');
    expect(data.querySelector('.tab-count')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('leaves the counts out until the postings have loaded', () => {
    render(<ProfileTabs profiles={PROFILES} selected={ALL} counts={null} onSelect={vi.fn()} />);
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'Software',
      'Data',
      'All postings',
    ]);
  });

  it('selects a tab by its key', () => {
    const onSelect = vi.fn();
    render(<ProfileTabs profiles={PROFILES} selected={ALL} counts={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('tab', {name: 'Software'}));
    fireEvent.click(screen.getByRole('tab', {name: 'All postings'}));
    expect(onSelect.mock.calls).toEqual([['1'], [ALL]]);
  });
});
