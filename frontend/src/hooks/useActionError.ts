import {useCallback, useState} from 'react';
import {errorText} from '../errors';

type Outcome = {error?: Parameters<typeof errorText>[0]};

// Runs a mutation and keeps its error message for the component to show, so
// a failed delete isn't silent. A later success clears the message.
export function useActionError(): {
  error: string | null;
  run: (action: Promise<Outcome>) => Promise<boolean>;
} {
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async (action: Promise<Outcome>) => {
    const result = await action;
    setError(result.error ? errorText(result.error) : null);
    return !result.error;
  }, []);
  return {error, run};
}
