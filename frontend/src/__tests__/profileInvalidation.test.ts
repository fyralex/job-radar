// @vitest-environment node
// Runs in Node, not jsdom, so RTK Query's Request and AbortSignal come from
// the same runtime; the API base URL is made absolute for Node's fetch.
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

const POSTINGS = {postings: [], failures: [], scraped_at: null, refreshing: false};

describe('profile changes refetch postings', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv('VITE_API_URL', 'http://jobradar.test');
    fetchMock = vi.fn(async (request: Request) => {
      const body = request.url.endsWith('/api/profiles') && request.method === 'POST'
        ? {id: 9, name: 'New'}
        : request.url.includes('/api/profiles/')
          ? null
          : POSTINGS;
      return new Response(body === null ? null : JSON.stringify(body), {
        status: body === null ? 204 : 200,
        headers: {'Content-Type': 'application/json'},
      });
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  const postingsFetches = () =>
    fetchMock.mock.calls.filter(([r]) => (r as Request).url.includes('/api/postings')).length;

  it.each([
    ['adding', async (api: typeof import('../redux/api').api, store: ReturnType<typeof import('../redux/store').makeStore>) =>
      store.dispatch(
        api.endpoints.createProfile.initiate({
          name: 'New',
          include_terms: ['x'],
          exclude_terms: [],
          seniority_terms: [],
          advanced: false,
          enabled: true,
        }),
      )],
    ['deleting', async (api: typeof import('../redux/api').api, store: ReturnType<typeof import('../redux/store').makeStore>) =>
      store.dispatch(api.endpoints.deleteProfile.initiate(9))],
  ])('%s a profile refetches postings', async (_name, change) => {
    const {api} = await import('../redux/api');
    const {makeStore} = await import('../redux/store');
    const store = makeStore();
    const sub = store.dispatch(api.endpoints.getPostings.initiate({}));
    await sub;
    expect(postingsFetches()).toBe(1);

    await change(api, store);
    await vi.waitFor(() => expect(postingsFetches()).toBe(2));
    sub.unsubscribe();
  });
});
