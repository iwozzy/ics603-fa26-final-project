import { mapSearchResult } from './mappers';
import { HttpGuestSessionRepository } from './guest-session-repository';
import { HttpPeopleSearchRepository } from './people-search-repository';

const payload = { query: 'Tom', people: [{ provider: 'tmdb', provider_id: 4139, name: 'Tom', known_for_department: null, profile_image_url: null, known_for: ['Alien'], id: 42 }] };
function response(status: number, body: unknown = payload): Response {
  return { ok: status === 200, status, headers: new Headers({ 'X-Lumiere-Guest-Created': 'false' }), json: async () => body } as Response;
}
function harness(searchResponse = response(200)) {
  const fetcher = jest.fn<ReturnType<typeof fetch>, [input: RequestInfo | URL, init?: RequestInit]>().mockImplementation(async (url) => url === '/api/v1/guest-session' ? response(200) : searchResponse);
  const sessions = new HttpGuestSessionRepository(fetcher);
  return { fetcher, sessions, repository: new HttpPeopleSearchRepository(fetcher, sessions) };
}
const signal = () => new AbortController().signal;

test('encodes once, uses cookie transport and platform cache, strips ids', async () => {
  const { repository, fetcher } = harness();
  const result = await repository.search("Timothée O'Neil & 李😀", signal());
  const [url, options] = fetcher.mock.calls[1];
  expect(url).toBe('/api/v1/people/search?query=' + encodeURIComponent("Timothée O'Neil & 李😀"));
  expect(options?.credentials).toBe('same-origin');
  expect(options?.cache).toBeUndefined();
  expect(options?.headers).toBeUndefined();
  expect(result.people[0]).toEqual({ provider: 'tmdb', providerId: 4139, name: 'Tom', knownForDepartment: null, profileImageUrl: null, knownFor: ['Alien'] });
  expect(result.people[0]).not.toHaveProperty('id');
});

test('test_repeated_calls_use_transport_without_result_cache', async () => {
  const { repository, fetcher } = harness();
  await repository.search('Tom', signal());
  await repository.search('Tom', signal());
  expect(fetcher.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/people/search'))).toHaveLength(2);
  expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/guest-session')).toHaveLength(1);
});

test.each(['500', 'bad_json', 'bad_schema', 'abort'])('test_500_bad_json_bad_schema_abort_reject_without_retry %s', async kind => {
  const bad = kind === '500' ? response(500) : kind === 'bad_schema' ? response(200, { people: [] }) : response(200);
  if (kind === 'bad_json') bad.json = async () => { throw new Error('bad JSON'); };
  const { repository, fetcher } = harness(bad);
  const controller = new AbortController();
  if (kind === 'abort') controller.abort();
  await expect(repository.search('Tom', controller.signal)).rejects.toThrow();
  const calls = fetcher.mock.calls.filter(([url]) => String(url).startsWith('/api/v1/people/search'));
  expect(calls).toHaveLength(kind === 'abort' ? 0 : 1);
  if (kind !== 'abort') {
    await expect(repository.search('Tom', signal())).rejects.toThrow();
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/guest-session')).toHaveLength(2);
  }
});

test('test_bootstrap_is_coalesced_and_reused', async () => {
  const { sessions, fetcher } = harness();
  await Promise.all([sessions.ensure(signal()), sessions.ensure(signal())]);
  await sessions.ensure(signal());
  expect(fetcher).toHaveBeenCalledTimes(1);
  sessions.invalidate();
  await sessions.ensure(signal());
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test('bootstrap failure never dispatches search', async () => {
  const fetcher = jest.fn(async () => response(500));
  const repository = new HttpPeopleSearchRepository(fetcher, new HttpGuestSessionRepository(fetcher));
  await expect(repository.search('Tom', signal())).rejects.toThrow();
  expect(fetcher.mock.calls).toHaveLength(1);
});

test('cancelling one bootstrap waiter leaves another submission usable', async () => {
  let finish!: (response: Response) => void;
  const fetcher = jest.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
  const sessions = new HttpGuestSessionRepository(fetcher);
  const a = new AbortController();
  const first = sessions.ensure(a.signal);
  const second = sessions.ensure(signal()).then(() => true, () => false);
  a.abort();
  await expect(first).rejects.toThrow();
  finish(response(200));
  expect(await second).toBe(true);
  await sessions.ensure(signal());
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test('accepts a response query containing 200 non-BMP code points', async () => {
  const { repository } = harness(response(200, { query: '😀'.repeat(200), people: [] }));
  await expect(repository.search('😀'.repeat(200), signal())).resolves.toEqual({ query: '😀'.repeat(200), people: [] });
});

function payloadWithId(id: number) { return { ...payload, people: [{ ...payload.people[0], provider_id: id }] }; }
test('retains exact safe provider identity and rejects unsafe numbers', () => {
  expect(mapSearchResult(payloadWithId(Number.MAX_SAFE_INTEGER)).people[0].providerId).toBe(Number.MAX_SAFE_INTEGER);
  for (const id of [Number.MAX_SAFE_INTEGER + 1, 0, -1, 1.5]) {
    expect(() => mapSearchResult(payloadWithId(id))).toThrow();
  }
});
