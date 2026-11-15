import {useEffect, useMemo, useState} from 'react';
import {
  EMPLOYMENT_LABELS,
  EMPLOYMENT_TYPES,
  type EmploymentType,
  type MarkStatus,
  type Posting,
  type Profile,
  WORK_TYPE_LABELS,
  WORK_TYPES,
  type WorkType,
} from '../datatypes';
import {errorText} from '../errors';
import {useLocalPreference} from '../hooks/useLocalPreference';
import {
  useAddMarkMutation,
  useApplyToPostingMutation,
  useGetPostingsQuery,
  useGetProfilesQuery,
  useGetSettingsQuery,
  useRefreshMutation,
} from '../redux/api';
import {applyNotice, matchesText, toggle} from '../lib';
import {isSeniorTitle} from '../seniority';
import {MarksPanel} from './MarksPanel';
import {PostingsList} from './PostingsList';

const ALL = 'all';

function ProfileTabs({
  profiles,
  selected,
  onSelect,
}: {
  profiles: Profile[];
  selected: string;
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
        </button>
      ))}
    </div>
  );
}

export function PostingsTab({onOpenSettings}: {onOpenSettings: () => void}) {
  const {data: profiles = [], isLoading: profilesLoading} = useGetProfilesQuery();
  const {data: settings} = useGetSettingsQuery();
  const [selected, setSelected] = useLocalPreference<string>('jobradar.profile', ALL);
  const [includeSenior, setIncludeSenior] = useLocalPreference('jobradar.senior', true);
  const [maxAge, setMaxAge] = useState<number | undefined>(undefined);
  const [workTypes, setWorkTypes] = useState<WorkType[]>([]);
  const [employment, setEmployment] = useState<EmploymentType[]>([]);
  const [localOnly, setLocalOnly] = useState(false);
  const [newOnly, setNewOnly] = useState(false);
  const [text, setText] = useState('');

  const enabledProfiles = profiles.filter((p) => p.enabled);
  const profileId =
    selected !== ALL && enabledProfiles.some((p) => String(p.id) === selected)
      ? Number(selected)
      : undefined;

  const postings = useGetPostingsQuery({
    profile: profileId,
    maxAgeDays: maxAge,
    workType: workTypes,
    employmentType: employment,
    local: localOnly,
  });
  const [refresh, refreshState] = useRefreshMutation();
  const [addMark] = useAddMarkMutation();
  const [applyToPosting] = useApplyToPostingMutation();
  const [applyMessage, setApplyMessage] = useState<{text: string; error: boolean} | null>(null);

  // While a scrape runs, poll so new results appear when it finishes.
  const refreshing = postings.data?.refreshing ?? false;
  const {refetch} = postings;
  useEffect(() => {
    if (!refreshing) return undefined;
    const timer = window.setInterval(() => void refetch(), 5000);
    return () => window.clearInterval(timer);
  }, [refreshing, refetch]);

  const visible = useMemo(
    () =>
      (postings.data?.postings ?? []).filter(
        (p) =>
          (includeSenior || !isSeniorTitle(p.title)) &&
          (!newOnly || p.is_new) &&
          matchesText(p, text),
      ),
    [postings.data, includeSenior, newOnly, text],
  );
  const newCount = visible.filter((p) => p.is_new).length;

  const onMark = (posting: Posting, status: MarkStatus) => void addMark({posting, status});
  const onApply = async (posting: Posting) => {
    const result = await applyToPosting(posting.posting_key);
    setApplyMessage(applyNotice(posting.title, result.error));
  };

  if (!profilesLoading && profiles.length === 0) {
    return (
      <div className="notice">
        <p>
          Add a job profile (what kinds of jobs you want) and a few boards to follow, then
          refresh.
        </p>
        <button type="button" onClick={onOpenSettings}>
          Open settings
        </button>
      </div>
    );
  }

  return (
    <section>
      <ProfileTabs
        profiles={profiles}
        selected={profileId === undefined ? ALL : selected}
        onSelect={setSelected}
      />

      <div className="toolbar">
        <label className="inline">
          Posted within{' '}
          <input
            type="number"
            min={1}
            max={365}
            value={maxAge ?? settings?.max_age_days ?? 30}
            onChange={(e) => setMaxAge(Number(e.target.value) || undefined)}
            className="days-input"
          />{' '}
          days
        </label>
        <input
          type="search"
          placeholder="Filter by words"
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label="Filter by words in title, organization or location"
        />
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={refreshing || refreshState.isLoading}
        >
          {refreshing ? 'Refreshing…' : 'Refresh now'}
        </button>
      </div>

      <fieldset className="chips">
        <legend className="visually-hidden">Work type</legend>
        {WORK_TYPES.map((w) => (
          <label key={w} className="chip">
            <input
              type="checkbox"
              checked={workTypes.includes(w)}
              onChange={() => setWorkTypes(toggle(workTypes, w))}
            />
            {WORK_TYPE_LABELS[w]}
          </label>
        ))}
        {EMPLOYMENT_TYPES.map((t) => (
          <label key={t} className="chip">
            <input
              type="checkbox"
              checked={employment.includes(t)}
              onChange={() => setEmployment(toggle(employment, t))}
            />
            {EMPLOYMENT_LABELS[t]}
          </label>
        ))}
        <label className="chip">
          <input type="checkbox" checked={localOnly} onChange={() => setLocalOnly(!localOnly)} />
          Local only
        </label>
        <label className="chip">
          <input
            type="checkbox"
            checked={includeSenior}
            onChange={() => setIncludeSenior(!includeSenior)}
          />
          Senior roles
        </label>
        <label className="chip">
          <input type="checkbox" checked={newOnly} onChange={() => setNewOnly(!newOnly)} />
          New only
        </label>
      </fieldset>

      <p className="status" aria-live="polite">
        {postings.isFetching && !postings.data
          ? 'Loading…'
          : `${visible.length} postings${newCount ? `, ${newCount} new` : ''}`}
        {postings.data?.scraped_at &&
          ` · last refreshed ${new Date(postings.data.scraped_at).toLocaleString()}`}
      </p>

      {postings.error && <p className="error">Couldn&apos;t load postings: {errorText(postings.error)}</p>}

      {postings.data && postings.data.failures.length > 0 && (
        <details className="failures">
          <summary>{postings.data.failures.length} boards failed on the last refresh</summary>
          <ul>
            {postings.data.failures.map((f) => (
              <li key={f.board_id}>
                <strong>{f.org}</strong>: {f.error}
              </li>
            ))}
          </ul>
        </details>
      )}

      {applyMessage && (
        <p className={applyMessage.error ? 'error' : 'ok'} role="status">
          {applyMessage.text}
        </p>
      )}
      <PostingsList postings={visible} onMark={onMark} onApply={(p) => void onApply(p)} />
      <MarksPanel />
    </section>
  );
}
