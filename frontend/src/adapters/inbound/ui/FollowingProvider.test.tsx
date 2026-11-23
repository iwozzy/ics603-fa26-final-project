import { act, render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import { FollowingProvider } from './FollowingProvider';
import { useFollowing } from './useFollowing';
import { FollowingStore } from '../../../application/following-store';
import { FollowPerson } from '../../../application/use-cases/follow-person';
import { ListFollowing } from '../../../application/use-cases/list-following';
import { DeferredFollowing, FakeSessions, snapshot } from '../../../test-utils/fakes/following';
function Consumer() { const { state } = useFollowing(); return <Text>{state.phase}</Text>; }

test('provider starts after render and aborts its owned work on unmount', async () => {
  const fake = new DeferredFollowing();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), new FakeSessions());
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
