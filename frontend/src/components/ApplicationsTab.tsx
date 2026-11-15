import {useState} from 'react';
import {APPLICATION_STATUSES, type ApplicationStatus, STATUS_LABELS} from '../datatypes';
import {errorText} from '../errors';
import {useLocalPreference} from '../hooks/useLocalPreference';
import {toggle} from '../lib';
import {
  useChangeApplicationStatusMutation,
  useCreateApplicationMutation,
  useDeleteApplicationMutation,
  useGetApplicationQuery,
  useGetApplicationsQuery,
  useUpdateApplicationMutation,
} from '../redux/api';
import {AddApplicationForm} from './AddApplicationForm';
import {ApplicationDetail} from './ApplicationDetail';
import {ApplicationsList} from './ApplicationsList';

// Turns an RTK Query result into the "error message or null" the forms expect.
function outcome(result: {error?: Parameters<typeof errorText>[0]}): string | null {
  return result.error ? errorText(result.error) : null;
}

export function ApplicationsTab() {
  // No status ticked means every status.
  const [statuses, setStatuses] = useLocalPreference<ApplicationStatus[]>(
    'jobradar.applicationStatuses',
    [],
  );
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);

  const {data: applications = [], isLoading, error} = useGetApplicationsQuery(statuses);
  const {data: selected} = useGetApplicationQuery(selectedId ?? 0, {skip: selectedId === null});
  const [createApplication] = useCreateApplicationMutation();
  const [updateApplication] = useUpdateApplicationMutation();
  const [deleteApplication] = useDeleteApplicationMutation();
  const [changeStatus] = useChangeApplicationStatusMutation();

  const detail =
    selected && selected.id === selectedId ? (
      <ApplicationDetail
        application={selected}
        onChangeStatus={async (to, note) =>
          outcome(await changeStatus({id: selected.id, to_status: to, note}))
        }
        onSaveNotes={async (notes) => outcome(await updateApplication({id: selected.id, notes}))}
        onDelete={() => {
          setSelectedId(null);
          void deleteApplication(selected.id);
        }}
      />
    ) : (
      <p className="status">Loading…</p>
    );

  return (
    <section>
      <div className="row wrap">
        <fieldset className="chips" aria-label="Show statuses">
          {APPLICATION_STATUSES.map((s) => (
            <label key={s} className="chip">
              <input
                type="checkbox"
                checked={statuses.includes(s)}
                onChange={() => setStatuses(toggle(statuses, s))}
              />
              {STATUS_LABELS[s]}
            </label>
          ))}
        </fieldset>
        {!adding && (
          <button type="button" onClick={() => setAdding(true)}>
            Add application
          </button>
        )}
      </div>
      <p className="hint">
        {statuses.length === 0 ? 'Showing every status.' : 'Showing the ticked statuses.'}
      </p>

      {adding && (
        <AddApplicationForm
          onSubmit={async (input) => {
            const result = await createApplication(input);
            if (result.error) return errorText(result.error);
            setAdding(false);
            setSelectedId(result.data.id);
            return null;
          }}
          onCancel={() => setAdding(false)}
        />
      )}

      {error ? (
        <p className="error">Couldn’t load applications: {errorText(error)}</p>
      ) : isLoading ? (
        <p className="status">Loading…</p>
      ) : (
        <ApplicationsList
          applications={applications}
          selectedId={selectedId}
          onSelect={setSelectedId}
          detail={detail}
        />
      )}
    </section>
  );
}
