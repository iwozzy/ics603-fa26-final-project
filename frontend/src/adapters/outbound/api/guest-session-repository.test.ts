import { HttpGuestSessionRepository } from './guest-session-repository';
const signal = () => new AbortController().signal;
const response = (created: string | null) => ({ ok: true, headers: new Headers(created === null ? {} : { 'X-Lumiere-Guest-Created': created }) }) as Response;

test('creation notifies once; readiness invalidation and returning guest preserve generation', async () => {
  const fetcher = jest.fn(async () => response('true'));
  const sessions = new HttpGuestSessionRepository(fetcher);
  const listener = jest.fn();
  const unsubscribe = sessions.subscribeIdentityCreated(listener);
  expect(sessions.identityGeneration).toBe(0);
  await Promise.all([sessions.ensure(signal()), sessions.ensure(signal())]);
  expect(listener.mock.calls).toEqual([[1]]);
  sessions.invalidate();
  expect(sessions.identityGeneration).toBe(1);
  fetcher.mockImplementation(async () => response('false'));
  await sessions.ensure(signal());
  expect(listener.mock.calls).toEqual([[1]]);
  unsubscribe();
  sessions.invalidate();
  fetcher.mockImplementation(async () => response('true'));
  await sessions.ensure(signal());
  expect(sessions.identityGeneration).toBe(2);
  expect(listener.mock.calls).toEqual([[1]]);
});

test('superseded bootstrap cannot publish readiness or a creation event', async () => {
  const calls: ((r: Response) => void)[] = [];
  const fetcher = jest.fn(() => new Promise<Response>(resolve => calls.push(resolve)));
  const sessions = new HttpGuestSessionRepository(fetcher);
  const listener = jest.fn();
  sessions.subscribeIdentityCreated(listener);
  const old = sessions.ensure(signal());
  sessions.invalidate();
  const current = sessions.ensure(signal());
  calls[0](response('true'));
  await expect(old).rejects.toThrow();
  expect(listener).not.toHaveBeenCalled();
  calls[1](response('false'));
  await current;
  expect(sessions.identityGeneration).toBe(0);
  await sessions.ensure(signal());
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test.each([null, '', 'TRUE', '1'])('missing or malformed creation header %s fails bootstrap', async header => {
  const sessions = new HttpGuestSessionRepository(async () => response(header));
  await expect(sessions.ensure(signal())).rejects.toThrow();
  expect(sessions.identityGeneration).toBe(0);
});
