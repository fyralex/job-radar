import {useState} from 'react';

// A per-browser UI preference (selected tab, a toggle). Storage can be
// unavailable (private windows), so every access is guarded and the default
// is used instead.
export function useLocalPreference<T>(key: string, fallback: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = window.localStorage.getItem(key);
      return stored === null ? fallback : (JSON.parse(stored) as T);
    } catch {
      return fallback;
    }
  });
  const update = (next: T) => {
    setValue(next);
    try {
      window.localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // Not persisted; the in-memory value still applies.
    }
  };
  return [value, update];
}
