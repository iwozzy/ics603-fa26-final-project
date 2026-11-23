import { FollowPerson } from './follow-person';
import { ListFollowing } from './list-following';
import type { PersonIdentity } from '../../domain/following';

test('use cases delegate identity and cancellation and propagate failures', async () => {
  const signal = new AbortController().signal;
  const identity: PersonIdentity = { provider: 'tmdb', providerId: 4139 };
  const snapshot = { people: [], limit: 3 };
  const repository = { list: jest.fn(async (_signal: AbortSignal) => snapshot), follow: jest.fn(async (_identity: PersonIdentity, _signal: AbortSignal) => snapshot) };
  expect(await new ListFollowing(repository).execute(signal)).toBe(snapshot);
  expect(repository.list).toHaveBeenCalledWith(signal);
  expect(await new FollowPerson(repository).execute(identity, signal)).toBe(snapshot);
  expect(repository.follow).toHaveBeenCalledWith(identity, signal);
  repository.follow.mockRejectedValueOnce(new Error('save'));
  await expect(new FollowPerson(repository).execute(identity, signal)).rejects.toThrow('save');
});
