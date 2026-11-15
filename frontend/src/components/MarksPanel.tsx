import {MARK_LABELS} from '../datatypes';
import {useGetMarksQuery, useRemoveMarkMutation} from '../redux/api';

// Hidden postings, collapsed at the bottom of the Postings tab. Unhiding one
// brings it back on the next load.
export function MarksPanel() {
  const {data: marks = []} = useGetMarksQuery();
  const [removeMark] = useRemoveMarkMutation();
  if (marks.length === 0) return null;
  return (
    <details className="marks">
      <summary>Hidden postings ({marks.length})</summary>
      <ul>
        {marks.map((m) => (
          <li key={m.posting_key}>
            <span className="badge badge-muted">{MARK_LABELS[m.status]}</span>{' '}
            {m.url ? (
              <a href={m.url} target="_blank" rel="noreferrer">
                {m.title}
              </a>
            ) : (
              m.title
            )}{' '}
            <span className="muted">
              {m.org}
              {m.location ? ` · ${m.location}` : ''}
            </span>{' '}
            <button type="button" className="link-button" onClick={() => void removeMark(m.posting_key)}>
              Unhide
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
