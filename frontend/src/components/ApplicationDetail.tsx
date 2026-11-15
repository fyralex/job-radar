import {useState} from 'react';
import {
  APPLICATION_STATUSES,
  type ApplicationEvent,
  type ApplicationStatus,
  type ApplicationWithEvents,
  STATUS_LABELS,
} from '../datatypes';
import {formatDate} from '../lib';

// Each handler resolves to an error message, or null on success.
type Save = Promise<string | null>;

function eventText(e: ApplicationEvent): string {
  return e.from_status === null
    ? `Added as ${STATUS_LABELS[e.to_status]}`
    : `${STATUS_LABELS[e.from_status]} → ${STATUS_LABELS[e.to_status]}`;
}

function StatusChange({
  current,
  onChange,
}: {
  current: ApplicationStatus;
  onChange: (to: ApplicationStatus, note: string) => Save;
}) {
  const choices = APPLICATION_STATUSES.filter((s) => s !== current);
  const [to, setTo] = useState<ApplicationStatus>(choices[0] ?? 'saved');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const result = await onChange(to, note.trim());
    setBusy(false);
    setError(result);
    if (result === null) setNote('');
  };

  return (
    <form className="row" onSubmit={(e) => void submit(e)}>
      <label>
        New status
        <select value={to} onChange={(e) => setTo(e.target.value as ApplicationStatus)}>
          {choices.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </label>
      <label className="grow">
        Note (optional)
        <input value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
      </label>
      <button type="submit" disabled={busy}>
        Change status
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

function Notes({initial, onSave}: {initial: string; onSave: (notes: string) => Save}) {
  const [notes, setNotes] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = async () => {
    const result = await onSave(notes);
    setError(result);
    setSaved(result === null);
  };

  return (
    <div>
      <label>
        Notes
        <textarea
          rows={4}
          value={notes}
          maxLength={20000}
          onChange={(e) => {
            setNotes(e.target.value);
            setSaved(false);
          }}
        />
      </label>
      <div className="row wrap">
        <button
          type="button"
          className="secondary"
          disabled={notes === initial}
          onClick={() => void save()}
        >
          Save notes
        </button>
        {saved && <span className="ok">Saved</span>}
        {error && <span className="error">{error}</span>}
      </div>
    </div>
  );
}

export function ApplicationDetail({
  application,
  onChangeStatus,
  onSaveNotes,
  onDelete,
}: {
  application: ApplicationWithEvents;
  onChangeStatus: (to: ApplicationStatus, note: string) => Save;
  onSaveNotes: (notes: string) => Save;
  onDelete: () => void;
}) {
  // Newest first: the latest step is what matters most.
  const events = [...application.events].reverse();
  return (
    <div className="application-detail">
      {/* Keyed by status so the choices reset after a change. */}
      <StatusChange
        key={application.status}
        current={application.status}
        onChange={onChangeStatus}
      />
      <Notes key={application.id} initial={application.notes} onSave={onSaveNotes} />
      <h3>History</h3>
      <ol className="timeline">
        {events.map((e) => (
          <li key={e.id}>
            <span className="muted">{formatDate(e.at)}</span> {eventText(e)}
            {e.note && <div className="timeline-note">{e.note}</div>}
          </li>
        ))}
      </ol>
      <button
        type="button"
        className="link-button danger"
        onClick={() => {
          if (window.confirm(`Delete the application for "${application.title}"?`)) onDelete();
        }}
      >
        Delete application
      </button>
    </div>
  );
}
