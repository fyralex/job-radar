import {act, renderHook} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {useActionError} from '../hooks/useActionError';

describe('useActionError', () => {
  it('keeps the server message of a failed action', async () => {
    const {result} = renderHook(() => useActionError());
    expect(result.current.error).toBeNull();
    let ok = true;
    await act(async () => {
      ok = await result.current.run(
        Promise.resolve({error: {status: 404, data: {error: 'no such board'}}}),
      );
    });
    expect(ok).toBe(false);
    expect(result.current.error).toBe('no such board');
  });

  it('describes a network failure', async () => {
    const {result} = renderHook(() => useActionError());
    await act(async () => {
      await result.current.run(Promise.resolve({error: {status: 'FETCH_ERROR', error: 'offline'}}));
    });
    expect(result.current.error).toBe('FETCH_ERROR');
  });

  it('clears the message after a success', async () => {
    const {result} = renderHook(() => useActionError());
    await act(async () => {
      await result.current.run(Promise.resolve({error: {status: 500, data: {}}}));
    });
    expect(result.current.error).toBe('HTTP 500');
    let ok = false;
    await act(async () => {
      ok = await result.current.run(Promise.resolve({}));
    });
    expect(ok).toBe(true);
    expect(result.current.error).toBeNull();
  });
});
