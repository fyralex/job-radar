import {fireEvent, render, screen, within} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {FilterBar} from '../components/FilterBar';
import {FilterMenu} from '../components/FilterMenu';
import {DEFAULT_FILTERS, type PostingFilters, hasActiveFilters} from '../lib';

function renderBar(filters: Partial<PostingFilters> = {}, extra: {refreshing?: boolean} = {}) {
  const onChange = vi.fn();
  const onRefresh = vi.fn();
  render(
    <FilterBar
      filters={{...DEFAULT_FILTERS, ...filters}}
      onChange={onChange}
      defaultMaxAge={30}
      refreshing={extra.refreshing ?? false}
      refreshDisabled={extra.refreshing ?? false}
      onRefresh={onRefresh}
    />,
  );
  return {onChange, onRefresh};
}

describe('hasActiveFilters', () => {
  it('counts this visit\'s filters, not the remembered senior preference', () => {
    expect(hasActiveFilters(DEFAULT_FILTERS)).toBe(false);
    expect(hasActiveFilters({...DEFAULT_FILTERS, text: 'data'})).toBe(true);
    expect(hasActiveFilters({...DEFAULT_FILTERS, maxAge: 7})).toBe(true);
    expect(hasActiveFilters({...DEFAULT_FILTERS, workTypes: ['remote']})).toBe(true);
    expect(hasActiveFilters({...DEFAULT_FILTERS, hideSenior: true})).toBe(false);
  });
});

describe('FilterBar', () => {
  it('shows the saved age when none is set, and searches by words', () => {
    const {onChange} = renderBar();
    expect((screen.getByRole('spinbutton') as HTMLInputElement).value).toBe('30');
    fireEvent.change(screen.getByRole('searchbox'), {target: {value: 'data'}});
    expect(onChange).toHaveBeenCalledWith({...DEFAULT_FILTERS, text: 'data'});
  });

  it('sets a filter through its menu', () => {
    const {onChange} = renderBar({workTypes: ['onsite']});
    fireEvent.click(screen.getByRole('button', {name: /Work type/}));
    fireEvent.click(screen.getByLabelText('Remote'));
    expect(onChange).toHaveBeenCalledWith({...DEFAULT_FILTERS, workTypes: ['onsite', 'remote']});
  });

  it('puts Local only, Hide senior roles and New only under More', () => {
    const {onChange} = renderBar();
    fireEvent.click(screen.getByRole('button', {name: /More/}));
    fireEvent.click(screen.getByLabelText('Hide senior roles'));
    expect(onChange).toHaveBeenCalledWith({...DEFAULT_FILTERS, hideSenior: true});
    expect(screen.getByLabelText('Local only')).toBeTruthy();
    expect(screen.getByLabelText('New only')).toBeTruthy();
  });

  it('hides Clear filters when nothing is set', () => {
    renderBar();
    expect(screen.queryByRole('button', {name: 'Clear filters'})).toBeNull();
  });

  it('Clear filters resets to the defaults', () => {
    const {onChange} = renderBar({text: 'x', localOnly: true, employment: ['contract']});
    fireEvent.click(screen.getByRole('button', {name: 'Clear filters'}));
    expect(onChange).toHaveBeenCalledWith(DEFAULT_FILTERS);
  });

  it('Clear filters keeps the remembered "Hide senior roles"', () => {
    const {onChange} = renderBar({text: 'x', hideSenior: true});
    fireEvent.click(screen.getByRole('button', {name: 'Clear filters'}));
    expect(onChange).toHaveBeenCalledWith({...DEFAULT_FILTERS, hideSenior: true});
  });

  it('does not offer Clear filters for the senior preference alone', () => {
    renderBar({hideSenior: true});
    expect(screen.queryByRole('button', {name: 'Clear filters'})).toBeNull();
    expect(screen.getByRole('button', {name: /More/}).textContent).toContain('1');
  });

  it('opens the More panel from the right edge, so it stays on screen', () => {
    renderBar();
    fireEvent.click(screen.getByRole('button', {name: /More/}));
    expect(screen.getByRole('group').className).toBe('filter-panel align-right');
    fireEvent.click(screen.getByRole('button', {name: /More/}));
    fireEvent.click(screen.getByRole('button', {name: /Work type/}));
    expect(screen.getByRole('group').className).toBe('filter-panel');
  });

  it('refreshes on click', () => {
    const {onRefresh} = renderBar();
    fireEvent.click(screen.getByRole('button', {name: 'Refresh now'}));
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it('disables the refresh button while refreshing', () => {
    renderBar({}, {refreshing: true});
    const button = screen.getByRole('button', {name: 'Refreshing…'}) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });
});

describe('FilterMenu', () => {
  const options = (checked: boolean[]) =>
    ['A', 'B', 'C'].map((label, i) => ({
      key: label,
      label,
      checked: checked[i] ?? false,
      onToggle: vi.fn(),
    }));

  it('shows how many options are on', () => {
    render(<FilterMenu label="Kind" options={options([true, false, true])} />);
    const button = screen.getByRole('button', {name: /Kind/});
    expect(button.textContent).toContain('2');
    expect(button.className).toContain('active');
  });

  it('opens and closes with the button, Escape and an outside click', () => {
    render(
      <>
        <FilterMenu label="Kind" options={options([])} />
        <p>outside</p>
      </>,
    );
    const button = screen.getByRole('button', {name: /Kind/});
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByRole('group')).toBeNull();

    fireEvent.click(button);
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(within(screen.getByRole('group')).getAllByRole('checkbox')).toHaveLength(3);

    fireEvent.keyDown(document, {key: 'Escape'});
    expect(screen.queryByRole('group')).toBeNull();
    expect(document.activeElement).toBe(button); // focus goes back to the button

    fireEvent.click(button);
    fireEvent.mouseDown(screen.getByText('outside'));
    expect(screen.queryByRole('group')).toBeNull();

    fireEvent.click(button);
    fireEvent.click(button);
    expect(screen.queryByRole('group')).toBeNull();
  });

  it('closes when keyboard focus leaves the menu, not when it moves inside', () => {
    render(
      <>
        <FilterMenu label="Kind" options={options([])} />
        <button type="button">elsewhere</button>
      </>,
    );
    const button = screen.getByRole('button', {name: /Kind/});
    fireEvent.click(button);
    const box = screen.getByLabelText('A');
    fireEvent.blur(button, {relatedTarget: box}); // Tab into the panel
    expect(screen.getByRole('group')).toBeTruthy();
    fireEvent.blur(box, {relatedTarget: null}); // a click on empty panel space, or a window switch
    expect(screen.getByRole('group')).toBeTruthy();
    fireEvent.blur(box, {relatedTarget: screen.getByRole('button', {name: 'elsewhere'})});
    expect(screen.queryByRole('group')).toBeNull();
  });

  it('keeps the panel open while ticking options inside it', () => {
    const opts = options([]);
    render(<FilterMenu label="Kind" options={opts} />);
    fireEvent.click(screen.getByRole('button', {name: /Kind/}));
    const box = screen.getByLabelText('B');
    fireEvent.mouseDown(box);
    fireEvent.click(box);
    expect(opts[1]?.onToggle).toHaveBeenCalledOnce();
    expect(screen.getByRole('group')).toBeTruthy();
  });
});
