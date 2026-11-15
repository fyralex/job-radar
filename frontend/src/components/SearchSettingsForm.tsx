import {useState} from 'react';
import {
  EMPLOYMENT_LABELS,
  EMPLOYMENT_TYPES,
  type EmploymentType,
  type Settings,
  WORK_TYPE_LABELS,
  WORK_TYPES,
  type WorkType,
} from '../datatypes';
import {errorText} from '../errors';
import {splitList, toggle} from '../lib';
import {useGetSettingsQuery, useUpdateSettingsMutation} from '../redux/api';

function Form({settings}: {settings: Settings}) {
  const [states, setStates] = useState(settings.states.join(', '));
  const [cities, setCities] = useState(settings.cities.join('; '));
  const [remote, setRemote] = useState(settings.remote);
  const [remoteStates, setRemoteStates] = useState(settings.remote_states.join(', '));
  const [keepUnknown, setKeepUnknown] = useState(settings.keep_unknown_location);
  const [maxAge, setMaxAge] = useState(settings.max_age_days);
  const [interval, setScrapeInterval] = useState(settings.scrape_interval_hours);
  const [employment, setEmployment] = useState<EmploymentType[]>(settings.employment_types);
  const [workTypes, setWorkTypes] = useState<WorkType[]>(settings.work_types);
  const [update, state] = useUpdateSettingsMutation();
  const [message, setMessage] = useState<string | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await update({
      states: states
        .split(/[,\s]+/)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
      cities: splitList(cities),
      remote,
      remote_states: remoteStates
        .split(/[,\s]+/)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
      keep_unknown_location: keepUnknown,
      max_age_days: maxAge,
      scrape_interval_hours: interval,
      employment_types: employment,
      work_types: workTypes,
    });
    setMessage('error' in result && result.error ? errorText(result.error) : 'Saved.');
  };

  return (
    <form className="settings-form" onSubmit={(e) => void save(e)}>
      <fieldset>
        <legend>Where you&apos;ll work on site</legend>
        <label>
          States (two-letter codes, e.g. TX, CO)
          <input value={states} onChange={(e) => setStates(e.target.value)} />
        </label>
        <label>
          Cities (&quot;City, ST&quot;, separated by semicolons)
          <input
            value={cities}
            onChange={(e) => setCities(e.target.value)}
            placeholder="Austin, TX; Denver, CO"
          />
        </label>
        <p className="hint">Leave both empty to accept any place.</p>
        <label className="inline">
          <input type="checkbox" checked={keepUnknown} onChange={() => setKeepUnknown(!keepUnknown)} />
          Keep postings whose location can&apos;t be read (&quot;3 Locations&quot;, office nicknames)
        </label>
      </fieldset>

      <fieldset>
        <legend>Remote</legend>
        <label className="inline">
          <input type="checkbox" checked={remote} onChange={() => setRemote(!remote)} />
          Include remote jobs open anywhere in the US
        </label>
        <label>
          Also accept remote jobs limited to these states (default: your states above)
          <input
            value={remoteStates}
            onChange={(e) => setRemoteStates(e.target.value)}
            disabled={!remote}
          />
        </label>
      </fieldset>

      <fieldset>
        <legend>Default filters</legend>
        <label>
          Posted within (days)
          <input
            type="number"
            min={1}
            max={365}
            value={maxAge}
            onChange={(e) => setMaxAge(Number(e.target.value))}
          />
        </label>
        <div className="chips">
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
        </div>
        <p className="hint">
          No employment type selected means all. Postings whose board doesn&apos;t say are always
          kept, marked &quot;type unknown&quot;.
        </p>
        <div className="chips">
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
        </div>
      </fieldset>

      <fieldset>
        <legend>Refresh</legend>
        <label>
          Refresh every (hours)
          <input
            type="number"
            min={1}
            max={168}
            value={interval}
            onChange={(e) => setScrapeInterval(Number(e.target.value))}
          />
        </label>
      </fieldset>

      <div className="row">
        <button type="submit" disabled={state.isLoading}>
          Save settings
        </button>
        {message && <span aria-live="polite">{message}</span>}
      </div>
    </form>
  );
}

export function SearchSettingsForm() {
  const {data: settings} = useGetSettingsQuery();
  return (
    <section className="panel">
      <h2>Location and filters</h2>
      {settings ? <Form settings={settings} /> : <p>Loading…</p>}
    </section>
  );
}
