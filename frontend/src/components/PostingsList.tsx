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

function MarkMenu({posting, onMark}: {posting: Posting; onMark: OnMark}) {
  return (
    <select
      className="mark-menu"
      value=""
      aria-label={`Hide ${posting.title}`}
      onChange={(e) => onMark(posting, e.target.value as MarkStatus)}
    >
      <option value="" disabled>
        Hide…
      </option>
      {(Object.keys(MARK_LABELS) as MarkStatus[]).map((status) => (
        <option key={status} value={status}>
          {MARK_LABELS[status]}
        </option>
      ))}
    </select>
  );
}

function ApplyButton({posting, onApply}: {posting: Posting; onApply: OnApply}) {
  return (
    <button
      type="button"
      className="secondary apply-button"
      aria-label={`Applied to ${posting.title}`}
      title="Copy to Applications as Applied"
      onClick={() => onApply(posting)}
    >
      Applied
    </button>
  );
}

// The "Applied" button and the hide menu, in one cell or card footer.
function Actions({
  posting,
  onMark,
  onApply,
}: {
  posting: Posting;
  onMark?: OnMark;
  onApply?: OnApply;
}) {
  return (
    <div className="posting-actions">
      {onApply && <ApplyButton posting={posting} onApply={onApply} />}
      {onMark && <MarkMenu posting={posting} onMark={onMark} />}
    </div>
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
                {hasActions && <Actions posting={p} onMark={onMark} onApply={onApply} />}
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
                  <Actions posting={p} onMark={onMark} onApply={onApply} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
