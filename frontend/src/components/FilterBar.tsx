import {
  EMPLOYMENT_LABELS,
  EMPLOYMENT_TYPES,
  WORK_TYPE_LABELS,
  WORK_TYPES,
} from '../datatypes';
import {DEFAULT_FILTERS, type PostingFilters, hasActiveFilters, toggle} from '../lib';
import {FilterMenu} from './FilterMenu';

// The Postings filter bar: search, age and refresh on top; Work type,
// Employment and More menus below, with "Clear filters" once anything is set.
export function FilterBar({
  filters,
  onChange,
  defaultMaxAge,
  refreshing,
  refreshDisabled,
  onRefresh,
}: {
  filters: PostingFilters;
  onChange: (filters: PostingFilters) => void;
  defaultMaxAge: number;
  refreshing: boolean;
  refreshDisabled: boolean;
  onRefresh: () => void;
}) {
  const set = (patch: Partial<PostingFilters>) => onChange({...filters, ...patch});
  return (
    <div className="filter-bar">
      <div className="filter-row">
        <input
          type="search"
          className="grow"
          placeholder="Filter by words"
          value={filters.text}
          onChange={(e) => set({text: e.target.value})}
          aria-label="Filter by words in title, organization or location"
        />
        <label className="inline">
          Posted within{' '}
          <input
            type="number"
            min={1}
            max={365}
            value={filters.maxAge ?? defaultMaxAge}
            onChange={(e) => set({maxAge: Number(e.target.value) || undefined})}
            className="days-input"
          />{' '}
          days
        </label>
        <button
          type="button"
          className="refresh-button"
          onClick={onRefresh}
          disabled={refreshDisabled}
        >
          {refreshing ? 'Refreshing…' : 'Refresh now'}
        </button>
      </div>
      <div className="filter-row">
        <FilterMenu
          label="Work type"
          options={WORK_TYPES.map((w) => ({
            key: w,
            label: WORK_TYPE_LABELS[w],
            checked: filters.workTypes.includes(w),
            onToggle: () => set({workTypes: toggle(filters.workTypes, w)}),
          }))}
        />
        <FilterMenu
          label="Employment"
          options={EMPLOYMENT_TYPES.map((t) => ({
            key: t,
            label: EMPLOYMENT_LABELS[t],
            checked: filters.employment.includes(t),
            onToggle: () => set({employment: toggle(filters.employment, t)}),
          }))}
        />
        <FilterMenu
          label="More"
          options={[
            {
              key: 'local',
              label: 'Local only',
              checked: filters.localOnly,
              onToggle: () => set({localOnly: !filters.localOnly}),
            },
            {
              key: 'senior',
              label: 'Hide senior roles',
              checked: filters.hideSenior,
              onToggle: () => set({hideSenior: !filters.hideSenior}),
            },
            {
              key: 'new',
              label: 'New only',
              checked: filters.newOnly,
              onToggle: () => set({newOnly: !filters.newOnly}),
            },
          ]}
        />
        {hasActiveFilters(filters) && (
          <button type="button" className="link-button" onClick={() => onChange(DEFAULT_FILTERS)}>
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}
