import {useEffect, useMemo, useState} from 'react';
import type {MarkStatus, Posting, Profile} from '../datatypes';
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
import {
  DEFAULT_FILTERS,
  type PostingFilters,
  applyNotice,
  matchesText,
  refreshNotice,
} from '../lib';
import {isSeniorTitle} from '../seniority';
import {FilterBar} from './FilterBar';
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
  // "Hide senior roles" is remembered per browser (stored as its inverse, as
  // before); the other filters reset on reload.
  const [includeSenior, setIncludeSenior] = useLocalPreference('jobradar.senior', true);
  const [rest, setRest] = useState<Omit<PostingFilters, 'hideSenior'>>(DEFAULT_FILTERS);
  const filters: PostingFilters = {...rest, hideSenior: !includeSenior};
  const setFilters = ({hideSenior, ...others}: PostingFilters) => {
    setRest(others);
    setIncludeSenior(!hideSenior);
  };
  const {text, maxAge, workTypes, employment, localOnly, newOnly} = filters;

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
  const refreshMessage = refreshNotice(refreshState.data, refreshState.error);
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

      <FilterBar
        filters={filters}
        onChange={setFilters}
        defaultMaxAge={settings?.max_age_days ?? 30}
        refreshing={refreshing}
        refreshDisabled={refreshing || refreshState.isLoading}
        onRefresh={() => void refresh()}
      />
      {refreshMessage && (
        <p className="notice" role="status">
          {refreshMessage}
        </p>
      )}

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
