import { act, fireEvent, render, screen, within } from '@testing-library/react-native';
import { Platform } from 'react-native';
import { SearchResults } from './SearchResults';
import { FollowingContext } from './FollowingContext';
import { FollowingStore } from '../../../application/following-store';
import { FollowPerson } from '../../../application/use-cases/follow-person';
import { UnfollowPerson } from '../../../application/use-cases/unfollow-person';
import { ListFollowing } from '../../../application/use-cases/list-following';
import { DeferredFollowing, FakeSessions, person, snapshot } from '../../../test-utils/fakes/following';

beforeEach(() => { jest.replaceProperty(Platform, 'OS', 'web'); });
afterEach(() => { jest.restoreAllMocks(); });
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
async function setup(ids = [1, 2, 3, 4], saved: number[] | null = []) {
  const fake = new DeferredFollowing();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), new UnfollowPerson(fake), new FakeSessions());
  store.start();
  if (saved) { fake.listCalls[0].resolve(snapshot(...saved)); await flush(); }
  const view = await render(<FollowingContext.Provider value={store}><SearchResults people={ids.map(person)} resultSetKey="Tom" /></FollowingContext.Provider>);
  return { store, fake, ...view };
}
const pointer = (pointerType = 'touch', clientX = 0, clientY = 0) => ({ pointerType, clientX, clientY, pointerId: 1 });
async function tap(name: string) { const node = screen.getByText(name); await fireEvent(node, 'pointerDown', pointer()); await fireEvent(node, 'pointerUp', pointer()); }

test('keyboard focus reveals action and following status after activation', async () => {
  const { fake, store, unmount } = await setup();
  const row = screen.getByTestId('search-result-0');
  const action = within(row).getByRole('button', { name: 'Follow +' });
  expect(action).toHaveStyle({ opacity: 0, pointerEvents: 'none' });
  await fireEvent(action, 'focus');
  expect(action).toHaveStyle({ opacity: 1, borderColor: '#4279b2' });
  await fireEvent.press(action);
  expect(within(row).getByText('Following')).toBeTruthy();
  await act(flush);
  expect(fake.followCalls).toHaveLength(1);
  await unmount(); store.stop();
});

test('mouse follow hides its pending and saved status when leaving the row', async () => {
  const { fake, store, unmount } = await setup();
  try {
    const name = screen.getByText('Person 1');
    const row = within(screen.getByTestId('search-result-0'));
    await fireEvent(name, 'pointerEnter', pointer('mouse'));
    const action = row.getByRole('button', { name: 'Follow +' });
    await fireEvent(action, 'pointerDown', pointer('mouse'));
    await fireEvent(action, 'focus');
    await fireEvent.press(action);
    await fireEvent(name, 'pointerLeave', pointer('mouse'));
    expect(row.getByRole('status')).toHaveStyle({ opacity: 0, pointerEvents: 'none' });
    await act(flush);
    await act(async () => { fake.followCalls[0].resolve(snapshot(1)); });
    expect(row.getByRole('status')).toHaveStyle({ opacity: 0 });
    await fireEvent(name, 'pointerEnter', pointer('mouse'));
    expect(row.getByRole('status')).toHaveStyle({ opacity: 1, borderColor: '#c3c7cc' });
  } finally { await unmount(); store.stop(); }
});

test('previously followed person reveals an outlined status on hover', async () => {
  const { store, unmount } = await setup([1], [1]);
  try {
    const status = screen.getByRole('status');
    expect(status).toHaveStyle({ opacity: 0 });
    await fireEvent(screen.getByText('Person 1'), 'pointerEnter', pointer('mouse'));
    expect(status).toHaveStyle({ opacity: 1, borderWidth: 2, borderColor: '#c3c7cc' });
    await fireEvent(screen.getByText('Person 1'), 'pointerLeave', pointer('mouse'));
    expect(status).toHaveStyle({ opacity: 0 });
  } finally { await unmount(); store.stop(); }
});

test('touch first tap reveals only its row; second action tap submits and duplicate identity shares status', async () => {
  const { fake, store, unmount } = await setup([1, 1, 2]);
  await tap('Person 2');
  expect(within(screen.getByTestId('search-result-2')).getByRole('button')).toHaveStyle({ opacity: 1 });
  const firstName = within(screen.getByTestId('search-result-0')).getByText('Person 1');
  await fireEvent(firstName, 'pointerDown', pointer()); await fireEvent(firstName, 'pointerUp', pointer());
  expect(within(screen.getByTestId('search-result-2')).getByRole('button')).toHaveStyle({ opacity: 0 });
  expect(within(screen.getByTestId('search-result-1')).getByRole('button')).toHaveStyle({ opacity: 0 });
  await act(flush); expect(fake.followCalls).toHaveLength(0);
  const button = within(screen.getByTestId('search-result-0')).getByRole('button');
  await fireEvent(button, 'pointerDown', pointer()); await fireEvent(button, 'pointerUp', pointer()); await fireEvent.press(button);
  await act(flush); expect(fake.followCalls).toHaveLength(1);
  expect(screen.getAllByText('Following')).toHaveLength(2);
  await unmount(); store.stop();
});

test('moved and cancelled gestures do not select or follow', async () => {
  const { store, fake, unmount } = await setup();
  const node = screen.getByText('Person 1');
  await fireEvent(node, 'pointerDown', pointer()); await fireEvent(node, 'pointerMove', pointer('touch', 30)); await fireEvent(node, 'pointerUp', pointer('touch', 30));
  expect(within(screen.getByTestId('search-result-0')).getByRole('button')).toHaveStyle({ opacity: 0 });
  await fireEvent(node, 'pointerDown', pointer()); await fireEvent(node, 'pointerCancel', pointer()); await fireEvent(node, 'pointerUp', pointer());
  expect(within(screen.getByTestId('search-result-0')).getByRole('button')).toHaveStyle({ opacity: 0 });
  expect(fake.followCalls).toHaveLength(0); await unmount(); store.stop();
});

test('unknown and third pending state hide remaining actions; failure releases slot without GET', async () => {
  const unknown = await setup([1], null);
  expect(screen.queryByRole('button')).toBeNull(); await unknown.unmount(); unknown.store.stop();
  const h = await setup([1, 2, 3, 4], [1, 2]);
  await tap('Person 3');
  const button = within(screen.getByTestId('search-result-2')).getByRole('button');
  await fireEvent(button, 'pointerDown', pointer()); await fireEvent(button, 'pointerUp', pointer()); await fireEvent.press(button);
  expect(screen.queryByRole('button')).toBeNull();
  await act(flush); h.fake.followCalls[0].reject(new Error('failed')); await act(flush);
  expect(within(screen.getByTestId('search-result-2')).getByRole('button')).toBeTruthy();
  expect(h.fake.listCalls).toHaveLength(1); await h.unmount(); h.store.stop();
});

test('first touch on hidden action cannot follow and result replacement clears selection', async () => {
  const h = await setup([1]);
  const action = within(screen.getByTestId('search-result-0')).getByRole('button');
  await fireEvent(action, 'pointerDown', pointer()); await fireEvent(action, 'pointerUp', pointer()); await fireEvent.press(action);
  await act(flush); expect(h.fake.followCalls).toHaveLength(0);
  expect(action).toHaveStyle({ opacity: 1 });
  await h.rerender(<FollowingContext.Provider value={h.store}><SearchResults people={[person(2)]} resultSetKey="Other" /></FollowingContext.Provider>);
  expect(within(screen.getByTestId('search-result-0')).getByRole('button')).toHaveStyle({ opacity: 0 });
  await h.unmount(); h.store.stop();
});

jest.mock('expo-router', () => ({ useFocusEffect: (effect: () => void) => { const React = jest.requireActual<typeof import('react')>('react'); React.useEffect(effect, [effect]); } }));
