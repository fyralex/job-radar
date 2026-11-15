import {useState} from 'react';
import type {Preset, Profile, ProfileInput} from '../datatypes';
import {errorText} from '../errors';
import {useActionError} from '../hooks/useActionError';
import {parseTerms} from '../lib';
import {
  useCreateProfileMutation,
  useDeleteProfileMutation,
  useGetPresetsQuery,
  useGetProfilesQuery,
  useUpdateProfileMutation,
} from '../redux/api';

const EMPTY: ProfileInput = {
  name: '',
  include_terms: [],
  exclude_terms: [],
  seniority_terms: [],
  advanced: false,
  enabled: true,
};

function fromPreset(preset: Preset): ProfileInput {
  return {
    name: preset.name,
    include_terms: preset.include_terms,
    exclude_terms: preset.exclude_terms,
    seniority_terms: preset.seniority_terms,
    advanced: preset.advanced,
    enabled: true,
  };
}

function ProfileForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial: ProfileInput;
  submitLabel: string;
  onSubmit: (input: ProfileInput) => Promise<string | null>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial.name);
  const [include, setInclude] = useState(initial.include_terms.join('\n'));
  const [exclude, setExclude] = useState(initial.exclude_terms.join('\n'));
  const [seniority, setSeniority] = useState(initial.seniority_terms.join('\n'));
  const [advanced, setAdvanced] = useState(initial.advanced);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(
      await onSubmit({
        name: name.trim(),
        include_terms: parseTerms(include),
        exclude_terms: parseTerms(exclude),
        seniority_terms: parseTerms(seniority),
        advanced,
        enabled: initial.enabled,
      }),
    );
  };

  return (
    <form className="profile-form" onSubmit={(e) => void submit(e)}>
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
      </label>
      <div className="term-columns">
        <label>
          Title must include one of
          <textarea rows={6} value={include} onChange={(e) => setInclude(e.target.value)} />
        </label>
        <label>
          …and none of
          <textarea rows={6} value={exclude} onChange={(e) => setExclude(e.target.value)} />
        </label>
        <label>
          …and one of these levels (optional)
          <textarea rows={6} value={seniority} onChange={(e) => setSeniority(e.target.value)} />
        </label>
      </div>
      <p className="hint">
        One term per line. Terms match whole words in the job title; spaces and hyphens are
        interchangeable.
      </p>
      <label className="inline">
        <input type="checkbox" checked={advanced} onChange={() => setAdvanced(!advanced)} />
        Terms are regular expressions
      </label>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button type="submit">{submitLabel}</button>
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function ProfilesEditor() {
  const {data: profiles = []} = useGetProfilesQuery();
  const {data: presets = []} = useGetPresetsQuery();
  const [createProfile] = useCreateProfileMutation();
  const [updateProfile] = useUpdateProfileMutation();
  const [deleteProfile] = useDeleteProfileMutation();
  const removal = useActionError();
  const [editing, setEditing] = useState<Profile | 'new' | null>(null);
  const [draft, setDraft] = useState<ProfileInput>(EMPTY);

  const startNew = (input: ProfileInput) => {
    setDraft(input);
    setEditing('new');
  };

  const save = async (input: ProfileInput): Promise<string | null> => {
    const result =
      editing === 'new'
        ? await createProfile(input)
        : editing
          ? await updateProfile({id: editing.id, ...input})
          : null;
    if (result && 'error' in result && result.error) return errorText(result.error);
    setEditing(null);
    return null;
  };

  return (
    <section className="panel">
      <h2>Job profiles</h2>
      <p className="hint">Each profile is a tab on the Postings page.</p>
      {removal.error && (
        <p className="error" role="alert">
          Couldn’t delete the profile: {removal.error}
        </p>
      )}
      <ul className="item-list">
        {profiles.map((p) => (
          <li key={p.id}>
            <label className="inline">
              <input
                type="checkbox"
                checked={p.enabled}
                onChange={() => void updateProfile({id: p.id, enabled: !p.enabled})}
                aria-label={`Show ${p.name}`}
              />
              <strong>{p.name}</strong>
            </label>
            <span className="muted"> {p.include_terms.length} terms</span>
            <button type="button" className="link-button" onClick={() => setEditing(p)}>
              Edit
            </button>
            <button
              type="button"
              className="link-button danger"
              onClick={() => {
                if (window.confirm(`Delete the profile "${p.name}"?`)) {
                  void removal.run(deleteProfile(p.id));
                }
              }}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>

      {editing === null ? (
        <div className="row wrap">
          <button type="button" onClick={() => startNew(EMPTY)}>
            New profile
          </button>
          {presets.map((preset) => (
            <button
              key={preset.key}
              type="button"
              className="secondary"
              title={preset.description}
              onClick={() => startNew(fromPreset(preset))}
            >
              Start from “{preset.name}”
            </button>
          ))}
        </div>
      ) : (
        <ProfileForm
          key={editing === 'new' ? `new-${draft.name}` : editing.id}
          initial={editing === 'new' ? draft : editing}
          submitLabel={editing === 'new' ? 'Add profile' : 'Save'}
          onSubmit={save}
          onCancel={() => setEditing(null)}
        />
      )}
    </section>
  );
}
