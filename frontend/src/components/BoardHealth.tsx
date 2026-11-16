import type {Board} from '../datatypes';
import {runLabel} from '../lib';

// A board's last few scrapes as dots (green ok, red failed; oldest first),
// then the latest outcome in words. Hover or a screen reader gives each
// run's time and count or error.
export function BoardHealth({
  board,
}: {
  board: Pick<Board, 'recent_runs' | 'last_status' | 'last_count' | 'last_error'>;
}) {
  return (
    <span className="health">
      {board.recent_runs.length > 0 && (
        <span className="health-dots" role="list" aria-label="Recent refreshes, oldest first">
          {board.recent_runs.map((run) => {
            const label = runLabel(run);
            return (
              <span
                key={run.started_at}
                role="listitem"
                className={run.status === 'ok' ? 'dot dot-ok' : 'dot dot-error'}
                title={label}
                aria-label={label}
              />
            );
          })}
        </span>
      )}
      {board.last_status === 'error' ? (
        <span className="error" title={board.last_error ?? ''}>
          failed
        </span>
      ) : board.last_status === 'ok' ? (
        <span>{`${board.last_count ?? 0} postings`}</span>
      ) : (
        <span className="muted">not yet</span>
      )}
    </span>
  );
}
