import { act, fireEvent, render, screen, within } from '@testing-library/react-native';
import { Platform } from 'react-native';
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
  expect(screen.getAllByRole('button', { name: 'Unfollow' })).toHaveLength(3);
  await view.unmount(); store.stop();
});


const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
const pointer = (pointerType = 'touch', clientX = 0) => ({ pointerType, clientX, clientY: 0, pointerId: 1 });
async function loaded(...ids: number[]) {
  const fake = new DeferredFollowing();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), new UnfollowPerson(fake), new FakeSessions());
  store.start(); fake.listCalls[0].resolve(snapshot(...ids)); await flush();
  const view = await render(<FollowingContext.Provider value={store}><FollowingScreen /></FollowingContext.Provider>);
  await act(() => { fake.listCalls.at(-1)!.resolve(snapshot(...ids)); });
  return { fake, store, ...view };
}
beforeEach(() => { jest.replaceProperty(Platform, 'OS', 'web'); });
afterEach(() => { jest.restoreAllMocks(); });

test('unfollow shares hidden styling, hover and focus reveal and rolls back in original order', async () => {
  const h = await loaded(3, 2, 1);
  const action = within(screen.getByTestId('following-person-tmdb:2')).getByRole('button', { name: 'Unfollow' });
  expect(action).toHaveStyle({ opacity: 0, pointerEvents: 'none', borderWidth: 2, borderColor: '#c3c7cc', borderRadius: 10, paddingVertical: 9, paddingHorizontal: 14 });
  await fireEvent(screen.getByText('Person 2'), 'pointerEnter', pointer('mouse'));
  expect(action).toHaveStyle({ opacity: 1 });
  await fireEvent(screen.getByText('Person 2'), 'pointerLeave', pointer('mouse'));
  expect(action).toHaveStyle({ opacity: 0 });
  await fireEvent(action, 'focus');
  // A preceding mouse hover keeps mouse modality; a keyboard-focused fresh row reveals.
  const keyboard = within(screen.getByTestId('following-person-tmdb:3')).getByRole('button');
  await fireEvent(keyboard, 'focus'); expect(keyboard).toHaveStyle({ opacity: 1, borderColor: '#4279b2' });
  await fireEvent.press(keyboard);
  expect(screen.queryByText('Person 3')).toBeNull();
  await act(flush); h.fake.unfollowCalls[0].reject(new Error('lost response')); await act(flush);
  expect(screen.getAllByText(/Person/).map(n => n.props.children)).toEqual(['Person 3', 'Person 2', 'Person 1']);
  await h.unmount(); h.store.stop();
});

test('unfollow first hidden-action touch only reveals; second submits once and final row is blank', async () => {
  const h = await loaded(1);
  const button = screen.getByRole('button', { name: 'Unfollow' });
  await fireEvent(button, 'pointerDown', pointer()); await fireEvent(button, 'pointerUp', pointer()); await fireEvent.press(button);
  await act(flush); expect(h.fake.unfollowCalls).toHaveLength(0); expect(button).toHaveStyle({ opacity: 1 });
  await fireEvent(button, 'pointerDown', pointer()); await fireEvent(button, 'pointerUp', pointer()); await fireEvent.press(button);
  expect(screen.queryByText(/./)).toBeNull(); await act(flush); expect(h.fake.unfollowCalls).toHaveLength(1);
  h.fake.unfollowCalls[0].resolve(); await act(flush); expect(screen.queryByRole('button')).toBeNull();
  await h.unmount(); h.store.stop();
});

test('unfollow touch selection switches and cancelled or moved gestures never remove', async () => {
  const h = await loaded(2, 1);
  const first = screen.getByText('Person 2'), second = screen.getByText('Person 1');
  const a = within(screen.getByTestId('following-person-tmdb:2')).getByRole('button');
  const b = within(screen.getByTestId('following-person-tmdb:1')).getByRole('button');
  await fireEvent(first, 'pointerDown', pointer()); await fireEvent(first, 'pointerUp', pointer());
  expect(a).toHaveStyle({ opacity: 1 });
  await fireEvent(second, 'pointerDown', pointer()); await fireEvent(second, 'pointerUp', pointer());
  expect(a).toHaveStyle({ opacity: 0 }); expect(b).toHaveStyle({ opacity: 1 });
  for (const cancel of [true, false]) {
    await fireEvent(a, 'pointerDown', pointer());
    await fireEvent(a, cancel ? 'pointerCancel' : 'pointerMove', pointer('touch', 30));
    await fireEvent(a, 'pointerUp', pointer('touch', 30)); await fireEvent.press(a);
  }
  await act(flush); expect(h.fake.unfollowCalls).toHaveLength(0);
  await fireEvent(b, 'pointerDown', pointer()); await fireEvent(b, 'pointerUp', pointer()); await fireEvent.press(b);
  await act(flush); h.fake.unfollowCalls[0].reject(new Error('failed')); await act(flush);
  for (const button of screen.getAllByRole('button')) expect(button).toHaveStyle({ opacity: 0 });
  await h.unmount(); h.store.stop();
});
