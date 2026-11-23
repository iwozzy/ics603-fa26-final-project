import { UnfollowPerson } from './unfollow-person';
import { FollowPerson } from './follow-person';
import { ListFollowing } from './list-following';
import type { PersonIdentity } from '../../domain/following';

test('use cases delegate identity and cancellation and propagate failures', async () => {
  const signal = new AbortController().signal;
  const identity: PersonIdentity = { provider: 'tmdb', providerId: 4139 };
  const snapshot = { people: [], limit: 3 };
  const repository = { unfollow: jest.fn(async (_identity: PersonIdentity, _signal: AbortSignal): Promise<void> => {}), list: jest.fn(async (_signal: AbortSignal) => snapshot), follow: jest.fn(async (_identity: PersonIdentity, _signal: AbortSignal) => snapshot) };
  expect(await new ListFollowing(repository).execute(signal)).toBe(snapshot);
  expect(repository.list).toHaveBeenCalledWith(signal);
  expect(await new FollowPerson(repository).execute(identity, signal)).toBe(snapshot);
  expect(repository.follow).toHaveBeenCalledWith(identity, signal);
  expect(await new UnfollowPerson(repository).execute(identity, signal)).toBeUndefined();
  expect(repository.unfollow).toHaveBeenCalledWith(identity, signal);
  repository.unfollow.mockRejectedValueOnce(new Error('delete'));
  await expect(new UnfollowPerson(repository).execute(identity, signal)).rejects.toThrow('delete');
  repository.follow.mockRejectedValueOnce(new Error('save'));
  await expect(new FollowPerson(repository).execute(identity, signal)).rejects.toThrow('save');
});
