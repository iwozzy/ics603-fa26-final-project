import { act, render, screen } from '@testing-library/react-native';
import { Platform, Text } from 'react-native';
import { FollowingProvider } from './FollowingProvider';
import { useFollowing } from './useFollowing';
import { FollowingStore } from '../../../application/following-store';
import { FollowPerson } from '../../../application/use-cases/follow-person';
import { UnfollowPerson } from '../../../application/use-cases/unfollow-person';
import { ListFollowing } from '../../../application/use-cases/list-following';
import { DeferredFollowing, FakeSessions, snapshot } from '../../../test-utils/fakes/following';
function Consumer() { const { state } = useFollowing(); return <Text>{state.phase}</Text>; }

test('browser focus and visibility changes preserve local follows without refreshing', async () => {
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
  const browserWindow = new EventTarget();
  const browserDocument = Object.assign(new EventTarget(), { visibilityState: 'visible' });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: browserWindow });
  Object.defineProperty(globalThis, 'document', { configurable: true, value: browserDocument });
  jest.replaceProperty(Platform, 'OS', 'web');
  const fake = new DeferredFollowing();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), new UnfollowPerson(fake), new FakeSessions());
  let view: Awaited<ReturnType<typeof render>> | undefined;
  try {
    view = await render(<FollowingProvider store={store}><Consumer /></FollowingProvider>);
    await act(async () => { fake.listCalls[0].resolve(snapshot(1)); });
    for (const target of [browserWindow, browserDocument]) {
      await act(() => { target.dispatchEvent(new Event(target === browserWindow ? 'focus' : 'visibilitychange')); });
      expect(fake.listCalls).toHaveLength(1);
      expect(store.getSnapshot().people.map(person => person.providerId)).toEqual([1]);
      expect(screen.getByText('ready')).toBeTruthy();
    }
  } finally {
    await view?.unmount();
    jest.restoreAllMocks();
    if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow); else Reflect.deleteProperty(globalThis, 'window');
    if (originalDocument) Object.defineProperty(globalThis, 'document', originalDocument); else Reflect.deleteProperty(globalThis, 'document');
  }
});

test('provider starts after render and aborts its owned work on unmount', async () => {
  const fake = new DeferredFollowing();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), new UnfollowPerson(fake), new FakeSessions());
  expect(fake.listCalls).toHaveLength(0);
  const view = await render(<FollowingProvider store={store}><Consumer /></FollowingProvider>);
  expect(screen.getByText('loading')).toBeTruthy();
  await act(async () => { fake.listCalls[0].resolve(snapshot()); });
  expect(screen.getByText('ready')).toBeTruthy();
  let request!: Promise<void>;
  await act(() => { request = store.refresh(); });
  await view.unmount();
  expect(fake.listCalls[1].signal.aborted).toBe(true);
  fake.listCalls[1].resolve(snapshot()); await request;
});
