import { FollowingFailed } from '../../../domain/errors';
import { FakeSessions } from '../../../test-utils/fakes/following';
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

test('failed ordinary list marks readiness stale so the next list can discover a new guest', async () => {
  let bootstraps = 0, gets = 0;
  const fetcher = jest.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
    if (url === '/api/v1/guest-session') {
      bootstraps++;
      return { ...response(), headers: new Headers({ 'X-Lumiere-Guest-Created': bootstraps > 1 ? 'true' : 'false' }) };
    }
    gets++;
    return gets === 2 ? response({}, false) : response(gets > 2 ? { people: [], limit: 3 } : payload);
  });
  const sessions = new HttpGuestSessionRepository(fetcher);
  const created = jest.fn(); sessions.subscribeIdentityCreated(created);
  const repository = new HttpFollowingRepository(fetcher, sessions);
  expect((await repository.list(signal())).people).toHaveLength(1);
  await expect(repository.list(signal())).rejects.toThrow();
  expect(bootstraps).toBe(1); expect(created).not.toHaveBeenCalled();
  expect(await repository.list(signal())).toEqual({ people: [], limit: 3 });
  expect(bootstraps).toBe(2); expect(created.mock.calls).toEqual([[1]]);
  expect(gets).toBe(3);
});


test('unfollow sends identity-only DELETE and accepts empty 204 without parsing', async () => {
  const json = jest.fn(() => { throw new Error('must not parse'); });
  const fetcher = jest.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => ({ ok: true, status: 204, json }) as unknown as Response);
  const repository = new HttpFollowingRepository(fetcher, new FakeSessions());
  const controller = new AbortController();
  await expect(repository.unfollow({ provider: 'tmdb', providerId: 4139 }, controller.signal)).resolves.toBeUndefined();
  expect(fetcher.mock.calls).toHaveLength(1);
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/following');
  expect(fetcher.mock.calls[0][1]).toMatchObject({ method: 'DELETE', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{"provider":"tmdb","provider_id":4139}', signal: expect.anything() });
  expect(json).not.toHaveBeenCalled();
});

test.each([200, 202, 500])('unfollow rejects status %s without retry, GET, or readiness invalidation', async status => {
  const sessions = new FakeSessions();
  const invalidate = jest.spyOn(sessions, 'invalidate');
  const fetcher = jest.fn(async () => ({ ok: status < 400, status }) as Response);
  const repository = new HttpFollowingRepository(fetcher, sessions);
  await expect(repository.unfollow({ provider: 'tmdb', providerId: 4139 }, signal())).rejects.toBeInstanceOf(FollowingFailed);
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(invalidate).not.toHaveBeenCalled();
});

test.each([0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, true, '4139'])('unfollow rejects invalid identity %s before dispatch', async id => {
  const fetcher = jest.fn();
  await expect(new HttpFollowingRepository(fetcher, new FakeSessions()).unfollow({ provider: 'tmdb', providerId: id as number }, signal())).rejects.toBeInstanceOf(FollowingFailed);
  expect(fetcher).not.toHaveBeenCalled();
});

test('unfollow bootstrap failure prevents DELETE', async () => {
  const sessions = new FakeSessions();
  sessions.ensureImpl = async () => { throw new Error('bootstrap'); };
  const fetcher = jest.fn();
  await expect(new HttpFollowingRepository(fetcher, sessions).unfollow({ provider: 'tmdb', providerId: 1 }, signal())).rejects.toBeInstanceOf(FollowingFailed);
  expect(fetcher).not.toHaveBeenCalled();
});

test('unfollow cancellation during bootstrap prevents DELETE', async () => {
  let release!: () => void;
  const sessions = new FakeSessions();
  sessions.ensureImpl = () => new Promise(resolve => { release = resolve; });
  const fetcher = jest.fn();
  const controller = new AbortController();
  const request = new HttpFollowingRepository(fetcher, sessions).unfollow({ provider: 'tmdb', providerId: 1 }, controller.signal);
  controller.abort(); release();
  await expect(request).rejects.toBeInstanceOf(FollowingFailed);
  expect(fetcher).not.toHaveBeenCalled();
});

test('unfollow deadline aborts transport and fails without retry', async () => {
  jest.useFakeTimers();
  try {
    const fetcher = jest.fn((_url: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init!.signal!.addEventListener('abort', () => reject(new Error('aborted')));
    }));
    const request = new HttpFollowingRepository(fetcher, new FakeSessions()).unfollow({ provider: 'tmdb', providerId: 1 }, signal());
    const assertion = expect(request).rejects.toBeInstanceOf(FollowingFailed);
    await jest.advanceTimersByTimeAsync(8000);
    await assertion;
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1]!.signal!.aborted).toBe(true);
  } finally { jest.useRealTimers(); }
});
