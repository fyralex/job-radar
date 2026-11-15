import {useState} from 'react';
import {
  APPLICATION_STATUSES,
  type ApplicationInput,
  type ApplicationStatus,
  STATUS_LABELS,
} from '../datatypes';

// For jobs found outside Job Radar. Resolves to an error message, or null.
export function AddApplicationForm({
  onSubmit,
  onCancel,
}: {
  onSubmit: (input: ApplicationInput) => Promise<string | null>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState('');
  const [org, setOrg] = useState('');
  const [location, setLocation] = useState('');
  const [url, setUrl] = useState('');
  const [source, setSource] = useState('');
  const [status, setStatus] = useState<ApplicationStatus>('applied');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(
      await onSubmit({
        title: title.trim(),
        org: org.trim(),
        location: location.trim(),
        url: url.trim(),
        source: source.trim(),
        status,
        notes: notes.trim(),
        note: '',
      }),
    );
    setBusy(false);
  };

  return (
    <form className="panel" onSubmit={(e) => void submit(e)} aria-label="Add application">
      <h2>Add an application</h2>
      <p className="hint">For a job you found somewhere other than Job Radar.</p>
      <div className="term-columns">
        <label>
          Job title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={500} />
        </label>
        <label>
          Organization
          <input value={org} onChange={(e) => setOrg(e.target.value)} required maxLength={200} />
        </label>
        <label>
          Location
          <input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={500} />
        </label>
        <label>
          Job link
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://"
            maxLength={2000}
          />
        </label>
        <label>
          Where you found it
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="e.g. referral, LinkedIn"
            maxLength={100}
          />
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value as ApplicationStatus)}>
            {APPLICATION_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        Notes
        <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={20000} />
      </label>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button type="submit" disabled={busy}>
          Add application
        </button>
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
