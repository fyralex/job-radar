import {useState} from 'react';
import type {BoardInput, BoardOptions, BoardValidation, Platform} from '../datatypes';
import {errorText} from '../errors';
import {
  useCreateBoardMutation,
  useDeleteBoardMutation,
  useGetBoardsQuery,
  useGetPlatformsQuery,
  useUpdateBoardMutation,
  useValidateBoardMutation,
} from '../redux/api';

function OptionFields({
  platform,
  options,
  onChange,
}: {
  platform: Platform;
  options: BoardOptions;
  onChange: (options: BoardOptions) => void;
}) {
  return (
    <>
      {Object.entries(platform.options).map(([name, spec]) =>
        spec.kind === 'bool' ? (
          <label key={name} className="inline">
            <input
              type="checkbox"
              checked={options[name] === true}
              onChange={(e) => onChange({...options, [name]: e.target.checked})}
            />
            {spec.help}
          </label>
        ) : (
          <label key={name}>
            {spec.help} (comma-separated)
            <input
              value={Array.isArray(options[name]) ? (options[name] as string[]).join(', ') : ''}
              onChange={(e) =>
                onChange({
                  ...options,
                  [name]: e.target.value
                    .split(',')
                    .map((v) => v.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
        ),
      )}
    </>
  );
}

function AddBoardForm({platforms}: {platforms: Platform[]}) {
  const [platformId, setPlatformId] = useState(platforms[0]?.id ?? '');
  const [slug, setSlug] = useState('');
  const [org, setOrg] = useState('');
  const [category, setCategory] = useState('');
  const [options, setOptions] = useState<BoardOptions>({});
  const [check, setCheck] = useState<BoardValidation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validate, validation] = useValidateBoardMutation();
  const [createBoard, creation] = useCreateBoardMutation();
  const platform = platforms.find((p) => p.id === platformId);

  const input: BoardInput = {platform: platformId, slug: slug.trim(), org: org.trim(), category, options};

  const onTest = async () => {
    setError(null);
    const result = await validate(input);
    if ('error' in result && result.error) setError(errorText(result.error));
    else setCheck(result.data ?? null);
  };

  const onAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await createBoard(input);
    if ('error' in result && result.error) {
      setError(errorText(result.error));
      return;
    }
    setSlug('');
    setOrg('');
    setOptions({});
    setCheck(null);
    setError(null);
  };

  return (
    <form className="board-form" onSubmit={(e) => void onAdd(e)}>
      <div className="row wrap">
        <label>
          Platform
          <select
            value={platformId}
            onChange={(e) => {
              setPlatformId(e.target.value);
              setOptions({});
              setCheck(null);
            }}
          >
            {platforms.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          {platform?.slug_help ?? 'Slug'}
          <input value={slug} onChange={(e) => setSlug(e.target.value)} required />
        </label>
        <label>
          Organization
          <input value={org} onChange={(e) => setOrg(e.target.value)} required />
        </label>
        <label>
          Category (optional)
          <input value={category} onChange={(e) => setCategory(e.target.value)} />
        </label>
      </div>
      {platform && <OptionFields platform={platform} options={options} onChange={setOptions} />}
      <div className="row">
        <button
          type="button"
          className="secondary"
          onClick={() => void onTest()}
          disabled={!slug || !org || validation.isLoading}
        >
          {validation.isLoading ? 'Testing…' : 'Test fetch'}
        </button>
        <button type="submit" disabled={!slug || !org || creation.isLoading}>
          Follow board
        </button>
      </div>
      {check &&
        (check.ok ? (
          <p className="ok">
            Found {check.count} open postings{check.sample.length ? `, e.g. ${check.sample.join('; ')}` : ''}.
            Check the organization is the one you expect: another company can use the same slug.
          </p>
        ) : (
          <p className="error">Test fetch failed: {check.error}</p>
        ))}
      {error && <p className="error">{error}</p>}
    </form>
  );
}

export function BoardsEditor() {
  const {data: platforms = []} = useGetPlatformsQuery();
  const {data: boards = []} = useGetBoardsQuery();
  const [updateBoard] = useUpdateBoardMutation();
  const [deleteBoard] = useDeleteBoardMutation();

  return (
    <section className="panel">
      <h2>Boards you follow ({boards.length})</h2>
      <p className="hint">
        Only public job-board feeds are supported. The app identifies itself honestly, follows
        robots.txt and waits a second between requests to the same site.
      </p>
      {platforms.length > 0 && <AddBoardForm platforms={platforms} />}
      <div className="table-scroll">
        <table className="boards">
          <thead>
            <tr>
              <th>On</th>
              <th>Organization</th>
              <th>Platform</th>
              <th>Last refresh</th>
              <th>
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {boards.map((b) => (
              <tr key={b.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={b.enabled}
                    aria-label={`Follow ${b.org}`}
                    onChange={() => void updateBoard({id: b.id, enabled: !b.enabled})}
                  />
                </td>
                <td>
                  <a href={b.url} target="_blank" rel="noreferrer">
                    {b.org}
                  </a>
                  {b.category && <span className="muted"> · {b.category}</span>}
                </td>
                <td>{b.platform_name}</td>
                <td>
                  {b.last_status === 'error' ? (
                    <span className="error" title={b.last_error ?? ''}>
                      failed
                    </span>
                  ) : b.last_status === 'ok' ? (
                    `${b.last_count ?? 0} postings`
                  ) : (
                    <span className="muted">not yet</span>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="link-button danger"
                    onClick={() => {
                      if (window.confirm(`Stop following ${b.org}? Its postings are removed.`)) {
                        void deleteBoard(b.id);
                      }
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
