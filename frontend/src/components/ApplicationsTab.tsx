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

// Tick statuses to show; none ticked shows every status.
export function StatusFilter({
  selected,
  onChange,
}: {
  selected: ApplicationStatus[];
  onChange: (statuses: ApplicationStatus[]) => void;
}) {
  return (
    <div>
      <fieldset className="chips" aria-label="Show statuses">
        {APPLICATION_STATUSES.map((s) => (
          <label key={s} className="chip">
            <input
              type="checkbox"
              checked={selected.includes(s)}
              onChange={() => onChange(toggle(selected, s))}
            />
            {STATUS_LABELS[s]}
          </label>
        ))}
      </fieldset>
      <p className="hint">
        {selected.length === 0 ? 'Showing every status.' : 'Showing the ticked statuses.'}{' '}
        {selected.length > 0 && (
          <button type="button" className="link-button" onClick={() => onChange([])}>
            Show all
          </button>
        )}
      </p>
    </div>
  );
}

// Shown when the open application's status is one the filter hides, e.g.
// right after changing it, so it doesn't just vanish.
export function FilteredOutNotice({
  title,
  status,
  onShowAll,
}: {
  title: string;
  status: ApplicationStatus;
  onShowAll: () => void;
}) {
  return (
    <p className="notice">
      “{title}” is now {STATUS_LABELS[status]}, which the status filter hides.{' '}
      <button type="button" className="link-button" onClick={onShowAll}>
        Show all statuses
      </button>
    </p>
  );
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

  // The open application no longer matches the filter (e.g. its status just
  // changed), so its card has dropped out of the list.
  const filteredOut =
    !isLoading &&
    selected !== undefined &&
    selected.id === selectedId &&
    !applications.some((a) => a.id === selected.id);

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
        <StatusFilter selected={statuses} onChange={setStatuses} />
        {!adding && (
          <button type="button" onClick={() => setAdding(true)}>
            Add application
          </button>
        )}
      </div>
      {filteredOut && selected && (
        <FilteredOutNotice
          title={selected.title}
          status={selected.status}
          onShowAll={() => setStatuses([])}
        />
      )}

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
