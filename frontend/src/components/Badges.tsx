import {EMPLOYMENT_LABELS, type EmploymentType, WORK_TYPE_LABELS, type WorkType} from '../datatypes';

const WORK_TITLES: Record<WorkType, string> = {
  onsite: 'On-site: the posting names a place and says nothing about remote or hybrid work',
  hybrid: 'Hybrid',
  remote: 'Remote',
  unknown: "Unknown: the board doesn't say where or how this job is done",
};

export function WorkTypeBadge({workType}: {workType: WorkType}) {
  return (
    <span className={`badge badge-${workType}`} title={WORK_TITLES[workType]}>
      {WORK_TYPE_LABELS[workType]}
    </span>
  );
}

// Most boards don't publish employment type, so unknown is common and kept.
export function EmploymentBadge({type}: {type: EmploymentType | null}) {
  if (type === null) {
    return (
      <span className="badge badge-muted" title="The board doesn't say">
        type unknown
      </span>
    );
  }
  if (type === 'full_time') return null;
  return <span className="badge badge-employment">{EMPLOYMENT_LABELS[type]}</span>;
}
