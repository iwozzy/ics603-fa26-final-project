import { FollowingStore } from './following-store';
import { ListFollowing } from './use-cases/list-following';
import { FollowPerson } from './use-cases/follow-person';
import { DeferredFollowing, FakeSessions, person, snapshot } from '../test-utils/fakes/following';
const flushPromises = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function harness() {
  const fake = new DeferredFollowing();
  const sessions = new FakeSessions();
  const store = new FollowingStore(new ListFollowing(fake), new FollowPerson(fake), sessions);
  return { fake, sessions, store };
}
async function ready(...ids: number[]) {
  const h = harness(); h.store.start(); h.fake.listCalls[0].resolve(snapshot(...ids)); await flushPromises(); return h;
}

test('construction performs no I/O and unknown/inactive state rejects follows', () => {
  const { store, fake } = harness();
  expect(fake.listCalls).toHaveLength(0);
  expect(store.requestFollow(person())).toBe(false);
  expect(store.getSnapshot()).toBe(store.getSnapshot());
  store.start();
  expect(store.getSnapshot().canFollow).toBe(false);
  expect(store.requestFollow(person())).toBe(false);
  store.stop();
});

test('pending_third_hides_actions_and_rejection_releases_slot', async () => {
  const { store, fake } = await ready(1, 2);
  expect(store.requestFollow(person(3))).toBe(true);
  expect(store.getSnapshot().canFollow).toBe(false);
  expect(store.requestFollow(person(4))).toBe(false);
  await flushPromises(); fake.followCalls[0].reject(new Error('cap')); await flushPromises();
  expect(store.getSnapshot().canFollow).toBe(true);
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([1, 2]);
  expect(fake.listCalls).toHaveLength(1);
  store.stop();
});

test('duplicate_identity_has_one_pending_entry', async () => {
  const { store, fake } = await ready();
  expect(store.requestFollow(person(1))).toBe(true);
  expect(store.requestFollow({ ...person(1), name: 'Duplicate' })).toBe(false);
  expect(store.getSnapshot().pending).toHaveLength(1);
  await flushPromises(); expect(fake.followCalls).toHaveLength(1); store.stop();
});

test('mutations_send_sequentially_and_preserve_other_pending_entries', async () => {
  const { store, fake } = await ready();
  for (const i of [1, 2, 3]) expect(store.requestFollow(person(i))).toBe(true);
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([3, 2, 1]);
  await flushPromises(); expect(fake.followCalls).toHaveLength(1);
  fake.followCalls[0].resolve(snapshot(1)); await flushPromises();
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([3, 2, 1]);
  expect(fake.followCalls).toHaveLength(2);
  fake.followCalls[1].reject(new Error('failed')); await flushPromises();
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([3, 1]);
  expect(fake.followCalls).toHaveLength(3);
  fake.followCalls[2].resolve(snapshot(3, 1)); await flushPromises();
  expect(store.getSnapshot().pending).toHaveLength(0);
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([3, 1]); store.stop();
});

test('old_read_cannot_replace_newer_mutation_snapshot', async () => {
  const { store, fake } = await ready();
  const read = store.refresh();
  store.requestFollow(person(1)); await flushPromises();
  fake.followCalls[0].resolve(snapshot(1)); await flushPromises();
  fake.listCalls[1].resolve(snapshot()); await read;
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([1]); store.stop();
});

test('initial_failure_is_unknown_but_refresh_failure_preserves_confirmed', async () => {
  const { store, fake } = harness(); store.start();
  fake.listCalls[0].reject(new Error('offline')); await flushPromises();
  expect(store.getSnapshot()).toMatchObject({ phase: 'failed', confirmed: null, canFollow: false, people: [] });
  const retry = store.refresh(); fake.listCalls[1].resolve(snapshot(1)); await retry;
  const refresh = store.refresh(); fake.listCalls[2].reject(new Error('offline')); await refresh;
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([1]);
  expect(store.getSnapshot().canFollow).toBe(true); store.stop();
});

test('lost_response_rolls_back_without_get_then_manual_retry_succeeds', async () => {
  const { store, fake } = await ready(1, 2);
  const readsBeforeFailure = fake.listCalls.length;
  store.requestFollow(person(3)); await flushPromises();
  fake.followCalls[0].reject(new Error('lost response')); await flushPromises();
  expect(store.getSnapshot().pending).toHaveLength(0);
  expect(fake.listCalls).toHaveLength(readsBeforeFailure);
  expect(store.requestFollow(person(3))).toBe(true); await flushPromises();
  fake.followCalls[1].resolve(snapshot(3, 2, 1)); await flushPromises();
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([3, 2, 1]); store.stop();
});

test('navigation_subscribers_do_not_own_mutation_lifetime', async () => {
  const { store, fake } = await ready();
  const unsubscribe = store.subscribe(() => {});
  store.requestFollow(person()); await flushPromises(); unsubscribe();
  expect(fake.followCalls[0].signal.aborted).toBe(false);
  fake.followCalls[0].resolve(snapshot(4139)); await flushPromises();
  expect(store.getSnapshot().people).toHaveLength(1); store.stop();
});

test('new guest discards queue and ignores old mutation and read responses', async () => {
  const { store, fake, sessions } = await ready();
  const oldRead = store.refresh();
  store.requestFollow(person(1)); store.requestFollow(person(2)); await flushPromises();
  sessions.createGuest();
  expect(fake.followCalls[0].signal.aborted).toBe(true);
  expect(store.getSnapshot()).toMatchObject({ confirmed: null, pending: [], canFollow: false });
  fake.followCalls[0].resolve(snapshot(1)); fake.listCalls[1].resolve(snapshot(1)); await oldRead; await flushPromises();
  expect(fake.followCalls).toHaveLength(1);
  expect(fake.listCalls).toHaveLength(3);
  fake.listCalls[2].resolve(snapshot()); await flushPromises();
  expect(store.getSnapshot().people).toEqual([]); store.stop();
});

test('new guest during queued readiness prevents dispatch and loads once', async () => {
  const { store, fake, sessions } = await ready(1);
  let finish!: () => void;
  sessions.ensureImpl = () => new Promise<void>(resolve => { finish = resolve; });
  store.requestFollow(person(2)); store.requestFollow(person(3)); await flushPromises();
  sessions.createGuest(); finish(); await flushPromises();
  expect(fake.followCalls).toHaveLength(0);
  expect(fake.listCalls).toHaveLength(2);
  fake.listCalls[1].resolve(snapshot()); await flushPromises();
  expect(store.getSnapshot().people).toEqual([]); store.stop();
});

test('initial guest notification restarts read exactly once and readiness invalidation preserves data', async () => {
  const { store, fake, sessions } = harness(); store.start(); sessions.createGuest();
  fake.listCalls[0].resolve(snapshot(99)); fake.listCalls[1].resolve(snapshot(1)); await flushPromises();
  expect(fake.listCalls).toHaveLength(2);
  sessions.invalidate();
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([1]); store.stop();
});

test('deduplicated reads and start stop start ignore abandoned work', async () => {
  const { store, fake } = harness(); store.start(); store.start();
  const one = store.refresh(), two = store.refresh();
  expect(fake.listCalls).toHaveLength(1); store.stop();
  expect(fake.listCalls[0].signal.aborted).toBe(true);
  store.start(); fake.listCalls[0].resolve(snapshot(99)); await Promise.all([one, two]);
  expect(store.getSnapshot().people).toEqual([]);
  fake.listCalls[1].resolve(snapshot(1)); await flushPromises();
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([1]); store.stop();
});
