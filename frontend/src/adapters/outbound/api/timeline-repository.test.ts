import { TimelineFailed } from '../../../domain/errors';
import type { TimelineQuery } from '../../../domain/timeline';
import { HttpGuestSessionRepository } from './guest-session-repository';
import { HttpTimelineRepository } from './timeline-repository';

const bootstrap = () => new Response(null, { headers: { 'X-Lumiere-Guest-Created': 'false' } });
const movie = {
  id: Number.MAX_SAFE_INTEGER,
  title: 'Bullet Train',
  overview: null,
  poster_image_url: null,
  release_date: '2022-08-03',
};
const initialPage = {
  items: [movie],
  older_cursor: 'older-edge',
  newer_cursor: null,
  as_of: '2026-11-26',
  anchor_index: null as number | null,
};
const cursorPage = {
  items: [],
  older_cursor: null,
  newer_cursor: null,
  as_of: null,
  anchor_index: null,
};
const pageResponse = (body: unknown = initialPage) => new Response(JSON.stringify(body));
const signal = () => new AbortController().signal;

function makeRepository() {
  const fetcher = jest.fn<ReturnType<typeof fetch>, Parameters<typeof fetch>>();
  const sessions = new HttpGuestSessionRepository(fetcher);
  return { fetcher, sessions, repository: new HttpTimelineRepository(fetcher, sessions) };
}

const cases: { query: TimelineQuery; params: Record<string, string>; payload: typeof initialPage | typeof cursorPage }[] = [
  { query: { mode: 'initial' }, params: {}, payload: initialPage },
  { query: { mode: 'initial', limit: 20 }, params: { limit: '20' }, payload: initialPage },
  {
    query: { mode: 'page', direction: 'older', cursor: 'older-edge', limit: 1 },
    params: { cursor: 'older-edge', direction: 'older', limit: '1' },
    payload: cursorPage,
  },
  {
    query: { mode: 'page', direction: 'newer', cursor: 'future-boundary' },
    params: { cursor: 'future-boundary', direction: 'newer' },
    payload: cursorPage,
  },
  {
    query: { mode: 'anchor', anchor: { releaseDate: '2022-08-03', id: Number.MAX_SAFE_INTEGER }, limit: 100 },
    params: { anchor_date: '2022-08-03', anchor_id: '9007199254740991', limit: '100' },
    payload: { ...initialPage, anchor_index: 0 },
  },
];

test.each(cases)('encodes the timeline query $query', async ({ query, params, payload }) => {
  const { fetcher, repository } = makeRepository();
  fetcher.mockResolvedValueOnce(bootstrap()).mockResolvedValueOnce(pageResponse(payload));

  const page = await repository.list(query, signal());

  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls[0]).toEqual(['/api/v1/guest-session', expect.objectContaining({ method: 'POST' })]);
  const [input, init] = fetcher.mock.calls[1];
  const url = new URL(String(input), 'https://example.test');
  expect(url.pathname).toBe('/api/v1/timeline');
  expect(Object.fromEntries(url.searchParams)).toEqual(params);
  expect(init).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store' });
  expect(page).toMatchObject({ asOf: payload.as_of, anchorIndex: payload.anchor_index });
});

test('escapes cursors as opaque values', async () => {
  const { fetcher, repository } = makeRepository();
  fetcher.mockResolvedValueOnce(bootstrap()).mockResolvedValueOnce(pageResponse(cursorPage));
  await repository.list({ mode: 'page', direction: 'older', cursor: 'opaque+/%&=' }, signal());

  const [input] = fetcher.mock.calls[1];
  const url = new URL(String(input), 'https://example.test');
  expect(url.searchParams.get('cursor')).toBe('opaque+/%&=');
});

test.each([
  ['HTTP', () => new Response(null, { status: 500 })],
  ['JSON', () => new Response('{')],
  ['schema', () => pageResponse({ ...initialPage, items: [{ ...movie, id: true }] })],
] as const)('translates a %s failure and only bootstraps again on the next operation', async (_failure, fail) => {
  const { fetcher, repository } = makeRepository();
  fetcher
    .mockResolvedValueOnce(bootstrap())
    .mockResolvedValueOnce(fail())
    .mockResolvedValueOnce(bootstrap())
    .mockResolvedValueOnce(pageResponse());

  await expect(repository.list({ mode: 'initial' }, signal())).rejects.toBeInstanceOf(TimelineFailed);
  expect(fetcher.mock.calls.map(([input]) => input)).toEqual(['/api/v1/guest-session', '/api/v1/timeline']);

  await expect(repository.list({ mode: 'initial' }, signal())).resolves.toMatchObject({ asOf: '2026-11-26' });
  expect(fetcher.mock.calls.map(([input]) => input)).toEqual([
    '/api/v1/guest-session', '/api/v1/timeline', '/api/v1/guest-session', '/api/v1/timeline',
  ]);
});

test('translates a failed bootstrap without issuing the timeline GET', async () => {
  const { fetcher, repository } = makeRepository();
  fetcher.mockResolvedValueOnce(new Response(null, { status: 500 }));

  await expect(repository.list({ mode: 'initial' }, signal())).rejects.toBeInstanceOf(TimelineFailed);
  expect(fetcher.mock.calls.map(([input]) => input)).toEqual(['/api/v1/guest-session']);
});

test('cancels during bootstrap without issuing the timeline GET or restarting the shared bootstrap', async () => {
  const { fetcher, repository, sessions } = makeRepository();
  let finishBootstrap!: (value: Response) => void;
  fetcher.mockImplementationOnce(() => new Promise(resolve => { finishBootstrap = resolve; }));
  const controller = new AbortController();
  const request = repository.list({ mode: 'initial' }, controller.signal);

  controller.abort();
  await expect(request).rejects.toBeInstanceOf(TimelineFailed);
  const anotherCaller = sessions.ensure(signal());
  finishBootstrap(bootstrap());
  await anotherCaller;
  expect(fetcher.mock.calls.map(([input]) => input)).toEqual(['/api/v1/guest-session']);
});

test('propagates abort to fetch and rejects a JSON body that arrives after cancellation', async () => {
  const { fetcher, repository } = makeRepository();
  let finishJson!: (body: unknown) => void;
  let jsonStarted!: () => void;
  const readingJson = new Promise<void>(resolve => { jsonStarted = resolve; });
  const response = pageResponse();
  jest.spyOn(response, 'json').mockImplementation(() => new Promise(resolve => {
    finishJson = resolve;
    jsonStarted();
  }));
  fetcher.mockResolvedValueOnce(bootstrap()).mockResolvedValueOnce(response).mockResolvedValueOnce(pageResponse());
  const controller = new AbortController();
  const request = repository.list({ mode: 'initial' }, controller.signal);

  await readingJson;
  controller.abort();
  const [, init] = fetcher.mock.calls[1];
  expect(init?.signal?.aborted).toBe(true);
  finishJson(initialPage);
  await expect(request).rejects.toBeInstanceOf(TimelineFailed);

  await expect(repository.list({ mode: 'initial' }, signal())).resolves.toMatchObject({ asOf: '2026-11-26' });
  expect(fetcher.mock.calls.map(([input]) => input)).toEqual([
    '/api/v1/guest-session', '/api/v1/timeline', '/api/v1/timeline',
  ]);
});

test('enforces the eight-second deadline even when fetch ignores abort', async () => {
  jest.useFakeTimers();
  try {
    const { fetcher, repository } = makeRepository();
    let finishFetch!: (value: Response) => void;
    fetcher.mockResolvedValueOnce(bootstrap())
      .mockImplementationOnce(() => new Promise(resolve => { finishFetch = resolve; }));
    const request = repository.list({ mode: 'initial' }, signal());
    const rejected = expect(request).rejects.toBeInstanceOf(TimelineFailed);

    await jest.advanceTimersByTimeAsync(7999);
    const [, init] = fetcher.mock.calls[1];
    expect(init?.signal?.aborted).toBe(false);
    await jest.advanceTimersByTimeAsync(1);
    await rejected;
    expect(init?.signal?.aborted).toBe(true);
    finishFetch(pageResponse());
    expect(fetcher).toHaveBeenCalledTimes(2);
  } finally {
    jest.useRealTimers();
  }
});
