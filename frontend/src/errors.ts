import type {SerializedError} from '@reduxjs/toolkit';
import type {FetchBaseQueryError} from '@reduxjs/toolkit/query';

// The backend answers errors as {"error": "..."}; show that text when present.
export function errorText(error: FetchBaseQueryError | SerializedError | undefined): string {
  if (!error) return '';
  if ('status' in error) {
    const data = error.data as {error?: unknown} | undefined;
    if (data && typeof data.error === 'string') return data.error;
    return typeof error.status === 'number' ? `HTTP ${error.status}` : String(error.status);
  }
  return error.message ?? 'Something went wrong';
}
