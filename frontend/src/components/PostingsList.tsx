import {useState} from 'react';
import {MARK_LABELS, type MarkStatus, type Posting} from '../datatypes';
import {useMediaQuery} from '../hooks/useMediaQuery';
import {type SortKey, postedLabel, sortPostings} from '../lib';
import {EmploymentBadge, WorkTypeBadge} from './Badges';

type OnMark = (posting: Posting, status: MarkStatus) => void;
type OnApply = (posting: Posting) => void;

const COLUMNS: {key: SortKey; label: string}[] = [
  {key: 'org', label: 'Organization'},
  {key: 'title', label: 'Title'},
  {key: 'location', label: 'Location'},
  {key: 'posted', label: 'Posted'},
];

type Action = 'applied' | MarkStatus;

// One compact menu per posting: mark it Applied (copies it into
// Applications) or hide it. It resets to "Actions" after each choice.
function ActionMenu({
  posting,
  onMark,
  onApply,
}: {
  posting: Posting;
  onMark?: OnMark;
  onApply?: OnApply;
}) {
  const choose = (action: Action) => {
    if (action === 'applied') onApply?.(posting);
    else onMark?.(posting, action);
  };
  return (
    <select
      className="action-menu"
      value=""
      aria-label={`Actions for ${posting.title}`}
      // Options come from the fixed list below, so the cast holds.
      onChange={(e) => choose(e.target.value as Action)}
    >
      <option value="" disabled>
        Actions…
      </option>
      {onApply && <option value="applied">Mark as applied</option>}
      {onMark &&
        (Object.keys(MARK_LABELS) as MarkStatus[]).map((status) => (
          <option key={status} value={status}>
            {MARK_LABELS[status]}
          </option>
        ))}
    </select>
  );
}

function Location({posting}: {posting: Posting}) {
  return (
    <>
      <WorkTypeBadge workType={posting.work_type} /> <EmploymentBadge type={posting.employment_type} />{' '}
      {posting.location || <span className="muted">not listed</span>}
    </>
  );
}

export function PostingsList({
  postings,
  onMark,
  onApply,
}: {
  postings: Posting[];
  onMark?: OnMark;
  onApply?: OnApply;
}) {
  const hasActions = onMark !== undefined || onApply !== undefined;
  const [sort, setSort] = useState<{key: SortKey; desc: boolean}>({key: 'posted', desc: false});
  const narrow = useMediaQuery('(max-width: 640px)');

  if (postings.length === 0) {
    return <p className="empty">No postings match these filters.</p>;
  }
  const sorted = sortPostings(postings, sort.key, sort.desc);
  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? {key, desc: !s.desc} : {key, desc: false}));

  if (narrow) {
    return (
      <>
        <label className="sort-select">
          Sort by{' '}
          <select
            value={`${sort.key}:${sort.desc ? 'desc' : 'asc'}`}
            onChange={(e) => {
              const [key, dir] = e.target.value.split(':');
              setSort({key: key as SortKey, desc: dir === 'desc'});
            }}
          >
            <option value="posted:asc">Newest first</option>
            <option value="posted:desc">Oldest first</option>
            <option value="org:asc">Organization A-Z</option>
            <option value="title:asc">Title A-Z</option>
            <option value="location:asc">Location A-Z</option>
          </select>
        </label>
        <div className="scroll-area" role="region" aria-label="Postings" tabIndex={0}>
          <ul className="cards">
            {sorted.map((p) => (
              <li key={p.posting_key} className="card">
                <a href={p.url} target="_blank" rel="noreferrer" className="card-title">
                  {p.is_new && <span className="new-badge">New</span>}
                  {p.title}
                </a>
                <div className="card-meta">
                  <span>{p.org}</span>
                  <span>
                    <Location posting={p} />
                  </span>
                  <span>{postedLabel(p)}</span>
                </div>
                {hasActions && <ActionMenu posting={p} onMark={onMark} onApply={onApply} />}
              </li>
            ))}
          </ul>
        </div>
      </>
    );
  }

  return (
    <div className="table-scroll scroll-area" role="region" aria-label="Postings" tabIndex={0}>
      <table className="postings">
        <thead>
          <tr>
            {COLUMNS.map(({key, label}) => (
              <th
                key={key}
                aria-sort={sort.key === key ? (sort.desc ? 'descending' : 'ascending') : 'none'}
              >
                <button type="button" className="sort-button" onClick={() => toggleSort(key)}>
                  {label}
                  {sort.key === key ? (sort.desc ? ' ▼' : ' ▲') : ''}
                </button>
              </th>
            ))}
            {hasActions && (
              <th>
                <span className="visually-hidden">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {sorted.map((p) => (
            <tr key={p.posting_key}>
              <td>{p.org}</td>
              <td>
                {p.is_new && <span className="new-badge">New</span>}
                <a href={p.url} target="_blank" rel="noreferrer">
                  {p.title}
                </a>
              </td>
              <td>
                <Location posting={p} />
              </td>
              <td className="nowrap">{postedLabel(p)}</td>
              {hasActions && (
                <td>
                  <ActionMenu posting={p} onMark={onMark} onApply={onApply} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
