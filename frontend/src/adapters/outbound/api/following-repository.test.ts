import { HttpFollowingRepository } from './following-repository';
import { HttpGuestSessionRepository } from './guest-session-repository';
import { mapFollowingSnapshot } from './following-mappers';

const payload = { limit: 3, people: [{ provider: 'tmdb', provider_id: 4139, name: 'Tom', known_for_department: null, profile_image_url: null, known_for: ['Alien'] }] };
const signal = () => new AbortController().signal;
const response = (body: unknown = payload, ok = true) => ({ ok, headers: new Headers({ 'X-Lumiere-Guest-Created': 'false' }), json: async () => body }) as Response;

test('following transport sends identity only and maps stored summaries', async () => {
  const fetcher = jest.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => response());
  const sessions = new HttpGuestSessionRepository(fetcher);
  const repository = new HttpFollowingRepository(fetcher, sessions);
  const listed = await repository.list(signal());
  const followed = await repository.follow({ provider: 'tmdb', providerId: 4139 }, signal());
  expect(listed).toEqual({ limit: 3, people: [{ provider: 'tmdb', providerId: 4139, name: 'Tom', knownForDepartment: null, profileImageUrl: null, knownFor: ['Alien'] }] });
  expect(followed).toEqual(listed);
  const [, get] = fetcher.mock.calls[1];
  expect(get).toMatchObject({ method: 'GET', credentials: 'same-origin', cache: 'no-store' });
  const [url, post] = fetcher.mock.calls[2];
  expect(url).toBe('/api/v1/following');
  expect(post).toMatchObject({ method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' } });
  expect(JSON.parse(post!.body as string)).toEqual({ provider: 'tmdb', provider_id: 4139 });
});

test.each(['500', 'bad_json', 'bad_schema'])('follow failure %s never retries or reconciles or invalidates readiness', async kind => {
  const fetcher = jest.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
    if (url === '/api/v1/guest-session') return response();
    if (kind === 'bad_json') return { ...response(), json: async () => { throw new Error('JSON'); } };
    return response(kind === 'bad_schema' ? {} : payload, kind !== '500');
  });
  const sessions = new HttpGuestSessionRepository(fetcher);
  const repository = new HttpFollowingRepository(fetcher, sessions);
  await expect(repository.follow({ provider: 'tmdb', providerId: 4139 }, signal())).rejects.toThrow();
  await sessions.ensure(signal());
  expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/api/v1/guest-session', '/api/v1/following']);
});

test('rejects unsafe request identities before HTTP and validates response safe integers', async () => {
  const fetcher = jest.fn(async () => response());
  const repository = new HttpFollowingRepository(fetcher, new HttpGuestSessionRepository(fetcher));
  for (const id of [0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    await expect(repository.follow({ provider: 'tmdb', providerId: id }, signal())).rejects.toThrow();
    expect(() => mapFollowingSnapshot({ ...payload, people: [{ ...payload.people[0], provider_id: id }] })).toThrow();
  }
  expect(fetcher).not.toHaveBeenCalled();
  expect(mapFollowingSnapshot({ ...payload, people: [{ ...payload.people[0], provider_id: Number.MAX_SAFE_INTEGER }] }).people[0].providerId).toBe(Number.MAX_SAFE_INTEGER);
});

test('aborted work cannot dispatch after bootstrap', async () => {
  let finish!: (r: Response) => void;
  const fetcher = jest.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
  const repository = new HttpFollowingRepository(fetcher, new HttpGuestSessionRepository(fetcher));
  const controller = new AbortController();
  const request = repository.list(controller.signal);
  controller.abort();
  finish(response());
  await expect(request).rejects.toThrow();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
