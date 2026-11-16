import type {Profile} from '../datatypes';

// The key of the "All postings" tab; profile tabs use the profile's id.
export const ALL = 'all';

// One tab per enabled job profile, then "All postings". Each shows how many
// postings it holds under the current filters (`counts`, keyed like the tabs)
// once they are known.
export function ProfileTabs({
  profiles,
  selected,
  counts,
  onSelect,
}: {
  profiles: Profile[];
  selected: string;
  counts: Record<string, number> | null;
  onSelect: (key: string) => void;
}) {
  const tabs = [...profiles.filter((p) => p.enabled).map((p) => ({key: String(p.id), name: p.name}))];
  tabs.push({key: ALL, name: 'All postings'});
  return (
    <div className="subtabs" role="tablist" aria-label="Job profiles">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          type="button"
          aria-selected={selected === t.key}
          className={selected === t.key ? 'subtab active' : 'subtab'}
          onClick={() => onSelect(t.key)}
        >
          {t.name}
          {counts && (
            <span className="tab-count" aria-label={`${counts[t.key] ?? 0} postings`}>
              {counts[t.key] ?? 0}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
