import type {ReactNode} from 'react';
import {type Application, type ApplicationStatus, STATUS_LABELS} from '../datatypes';
import {formatDate} from '../lib';

// Statuses where the search for this job is over; shown muted.
const CLOSED: ApplicationStatus[] = ['accepted', 'rejected', 'withdrawn', 'ghosted'];

export function StatusBadge({status}: {status: ApplicationStatus}) {
  const muted = CLOSED.includes(status);
  return (
    <span className={muted ? 'badge badge-muted' : 'badge badge-status'}>
      {STATUS_LABELS[status]}
    </span>
  );
}

// One card per application. The selected one renders `detail` under it, so
// the layout is the same on a phone and a desktop.
export function ApplicationsList({
  applications,
  selectedId,
  onSelect,
  detail,
}: {
  applications: Application[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  detail?: ReactNode;
}) {
  if (applications.length === 0) {
    return <p className="empty">No applications yet.</p>;
  }
  return (
    <ul className="cards">
      {applications.map((a) => {
        const open = a.id === selectedId;
        return (
          <li key={a.id} className="card">
            <div className="card-head">
              {a.url ? (
                <a href={a.url} target="_blank" rel="noreferrer" className="card-title">
                  {a.title}
                </a>
              ) : (
                <span className="card-title">{a.title}</span>
              )}
              <StatusBadge status={a.status} />
            </div>
            <div className="card-meta">
              <span>
                {a.org}
                {a.location ? ` · ${a.location}` : ''}
              </span>
              <span>
                {a.applied_at ? `Applied ${formatDate(a.applied_at)}` : `Added ${formatDate(a.created_at)}`}
                {a.source ? ` · ${a.source}` : ''}
              </span>
            </div>
            <div>
              <button
                type="button"
                className="link-button"
                aria-expanded={open}
                onClick={() => onSelect(open ? null : a.id)}
              >
                {open ? 'Close' : 'Details'}
                <span className="visually-hidden"> for {a.title}</span>
              </button>
            </div>
            {open && detail}
          </li>
        );
      })}
    </ul>
  );
}
