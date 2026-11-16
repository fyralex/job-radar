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
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((t) => t.textContent)).toEqual(['Software40', 'Data7', 'All postings52']);
    expect(screen.getByRole('tab', {name: /Data/}).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tab', {name: /Data/}).className).toBe('subtab active');
    expect(screen.getByLabelText('40 postings')).toBeTruthy();
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
