import { act, render, screen } from '@testing-library/react-native';
import FollowingScreen from './FollowingScreen';
import { FollowingContext } from './FollowingContext';
import { FollowingStore } from '../../../application/following-store';
import { FollowPerson } from '../../../application/use-cases/follow-person';
import { UnfollowPerson } from '../../../application/use-cases/unfollow-person';
import { ListFollowing } from '../../../application/use-cases/list-following';
import { DeferredFollowing, FakeSessions, snapshot } from '../../../test-utils/fakes/following';
jest.mock('expo-router', () => ({ useFocusEffect: (effect: () => void) => { const React = jest.requireActual<typeof import('react')>('react'); React.useEffect(effect, [effect]); } }));

test.each(['loading', 'empty', 'failed'])('Following content remains blank during %s', async kind => {
  const fake = new DeferredFollowing();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), new UnfollowPerson(fake), new FakeSessions());
  store.start();
  const view = await render(<FollowingContext.Provider value={store}><FollowingScreen /></FollowingContext.Provider>);
  expect(fake.listCalls).toHaveLength(1);
  if (kind !== 'loading') await act(() => { if (kind === 'empty') fake.listCalls[0].resolve(snapshot()); else fake.listCalls[0].reject(new Error('offline')); });
  expect(screen.queryByRole('progressbar')).toBeNull();
  expect(screen.queryByText(/./)).toBeNull();
  expect(screen.queryByRole('button')).toBeNull();
  await view.unmount(); store.stop();
});

test('Following preserves server ordering and confirmed rows on refresh failure', async () => {
  const fake = new DeferredFollowing();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), new UnfollowPerson(fake), new FakeSessions());
  store.start(); fake.listCalls[0].resolve(snapshot(3, 2, 1)); await Promise.resolve();
  const view = await render(<FollowingContext.Provider value={store}><FollowingScreen /></FollowingContext.Provider>);
  expect(screen.getAllByText(/Person/).map(node => node.props.children)).toEqual(['Person 3', 'Person 2', 'Person 1']);
  expect(screen.getByLabelText('Person 3 silhouette')).toBeTruthy();
  await act(() => fake.listCalls.at(-1)!.reject(new Error('refresh failed')));
  expect(screen.getAllByText(/Person/)).toHaveLength(3);
  expect(screen.queryByText('Unfollow')).toBeNull();
  await view.unmount(); store.stop();
});
