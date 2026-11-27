import type { MovieSummary, TimelineAnchor, TimelinePage } from '../domain/timeline';
import { DeferredFollowing, FakeSessions, person, snapshot } from '../test-utils/fakes/following';
import { DeferredTimeline } from '../test-utils/fakes/timeline';
import { FollowingStore } from './following-store';
import { initialTimelineState, TimelineStore } from './timeline-store';
import { FollowPerson } from './use-cases/follow-person';
import { ListFollowing } from './use-cases/list-following';
import { ListTimeline } from './use-cases/list-timeline';
import { UnfollowPerson } from './use-cases/unfollow-person';

const saved: TimelineAnchor = { releaseDate: '2022-08-03', id: 123, offset: -37 };

function movie(id: number, releaseDate: string): MovieSummary {
  return { id, title: 'Movie ' + id, releaseDate, overview: null, posterImageUrl: null };
}

const savedMovie = movie(123, '2022-08-03');
const olderMovie = movie(34, '2001-09-26');
const newerMovie = movie(567, '2026-12-31');

function page(items: readonly MovieSummary[], fields: Partial<Omit<TimelinePage, 'items'>> = {}): TimelinePage {
  return { items, asOf: null, olderCursor: null, newerCursor: null, anchorIndex: null, ...fields };
}

function initial(items: readonly MovieSummary[] = [savedMovie, olderMovie]): TimelinePage {
  return page(items, { asOf: '2026-11-26', newerCursor: 'newer-1', olderCursor: 'older-1' });
}

function harness() {
  const sessions = new FakeSessions();
  const repository = new DeferredTimeline();
  const store = new TimelineStore(new ListTimeline(repository), sessions);
  return { store, repository, sessions };
}

async function ready(result = initial()) {
  const fixture = harness();
  const entering = fixture.store.enter();
  fixture.repository.calls[0].resolve(result);
  await entering;
  return fixture;
}

test('construction_and_start_do_not_fetch_and_initial_entry_is_past_only', async () => {
  const { store, repository } = harness();
  const listener = jest.fn();
  const unsubscribe = store.subscribe(listener);
  expect(store.getSnapshot()).toBe(initialTimelineState);
  store.start();
  store.start();
  expect(repository.calls).toHaveLength(0);
  const first = store.enter();
  const second = store.enter();
  expect(store.getSnapshot().phase).toBe('loading');
  expect(repository.calls.map(call => call.query)).toEqual([{ mode: 'initial' }]);
  repository.calls[0].resolve(initial());
  await Promise.all([first, second]);
  expect(listener).toHaveBeenCalled();
  expect(store.getSnapshot()).toMatchObject({ phase: 'ready', items: [savedMovie, olderMovie] });
  unsubscribe();
  listener.mockClear();
  store.leave(saved);
  expect(listener).not.toHaveBeenCalled();
});

test('test_return_uses_one_anchor_request_not_all_cached_pages', async () => {
  const { store, repository } = await ready();
  const older = store.load('older');
  repository.calls[1].resolve(page([movie(8, '1995-01-01')], { olderCursor: 'older-2' }));
  await older;
  const newer = store.load('newer');
  repository.calls[2].resolve(page([newerMovie], { newerCursor: 'newer-2' }));
  await newer;
  store.leave(saved);
  const retainedItems = store.getSnapshot().items;
  const callsBeforeReturn = repository.calls.length;

  const returning = store.enter();
  expect(repository.calls.at(-1)?.query).toEqual({ mode: 'anchor', anchor: { releaseDate: '2022-08-03', id: 123 } });
  expect(repository.calls.length - callsBeforeReturn).toBe(1);
  expect(store.getSnapshot().items).toEqual(retainedItems);
  const cachedRestoration = store.getSnapshot().restoration!;
  expect(cachedRestoration.anchor).toEqual(saved);
  const movedMovie = movie(123, '2022-08-04');
  repository.calls[3].resolve(page([movedMovie], { asOf: '2026-11-27', anchorIndex: null }));
  await returning;
  expect(store.getSnapshot()).toMatchObject({
    items: [movedMovie], asOf: '2026-11-27', olderCursor: null, newerCursor: null,
    anchor: { ...saved, releaseDate: '2022-08-04' },
  });
  const refreshedRestoration = store.getSnapshot().restoration!;
  expect(refreshedRestoration.revision).toBeGreaterThan(cachedRestoration.revision);
  expect(refreshedRestoration.anchor).toEqual({ ...saved, releaseDate: '2022-08-04' });
});

test('departure_without_a_fresh_measurement_restores_the_last_saved_anchor', async () => {
  const { store, repository } = await ready();
  store.rememberAnchor(saved);
  store.leave(null);

  const returning = store.enter();
  expect(repository.calls[1].query).toEqual({ mode: 'anchor', anchor: { releaseDate: '2022-08-03', id: 123 } });
  expect(store.getSnapshot()).toMatchObject({
    items: [savedMovie, olderMovie], anchor: saved, restoration: { anchor: saved },
  });
  repository.calls[1].resolve(page([savedMovie], { asOf: '2026-11-27', anchorIndex: 0 }));
  await returning;
  expect(store.getSnapshot()).toMatchObject({ items: [savedMovie], restoration: { anchor: saved } });
});

test('empty_past_can_page_into_the_future_using_its_newer_cursor', async () => {
  const { store, repository } = await ready(page([], { asOf: '2026-11-26', newerCursor: 'future' }));
  await store.load('older');
  expect(repository.calls).toHaveLength(1);
  const newer = store.load('newer');
  expect(repository.calls[1].query).toEqual({ mode: 'page', direction: 'newer', cursor: 'future' });
  repository.calls[1].resolve(page([newerMovie]));
  await newer;
  expect(store.getSnapshot().items).toEqual([newerMovie]);
});

test('empty_retained_window_refreshes_with_an_initial_request', async () => {
  const { store, repository } = await ready(page([], { asOf: '2026-11-26', newerCursor: 'future' }));
  store.leave(null);
  const returning = store.enter();
  expect(repository.calls[1].query).toEqual({ mode: 'initial' });
  expect(store.getSnapshot().newerCursor).toBe('future');
  repository.calls[1].resolve(initial());
  await returning;
  expect(store.getSnapshot().items).toEqual([savedMovie, olderMovie]);
});

test.each([
  ['disappeared anchor uses the next older row', [newerMovie, olderMovie, movie(8, '1995-01-01')], 1, { releaseDate: '2001-09-26', id: 34, offset: 0 }],
  ['no older neighborhood uses the last row', [newerMovie, movie(456, '2025-01-01')], null, { releaseDate: '2025-01-01', id: 456, offset: 0 }],
  ['empty result clears the anchor', [], null, null],
] as const)('%s', async (_name, items, anchorIndex, expectedAnchor) => {
  const { store, repository } = await ready();
  store.leave(saved);

  const returning = store.enter();
  repository.calls[1].resolve(page(items, { anchorIndex, asOf: '2026-11-26' }));
  await returning;
  expect(store.getSnapshot()).toMatchObject({ items, anchor: expectedAnchor, restoration: { anchor: expectedAnchor } });
});

test('refresh_failure_preserves_items_edges_and_reading_position', async () => {
  const { store, repository } = await ready();
  store.leave(saved);
  const returning = store.enter();
  const retained = store.getSnapshot();
  repository.calls[1].reject(new Error('offline'));
  await returning;
  expect(store.getSnapshot()).toEqual({ ...retained, phase: 'failed' });

  const newer = store.load('newer');
  expect(repository.calls[2].query).toEqual({ mode: 'page', direction: 'newer', cursor: 'newer-1' });
  repository.calls[2].resolve(page([newerMovie]));
  await newer;
});

test('initial_failure_is_blank_and_retries_only_on_another_entry', async () => {
  const { store, repository } = harness();
  const entering = store.enter();
  repository.calls[0].reject(new Error('offline'));
  await entering;
  expect(store.getSnapshot()).toEqual({ ...initialTimelineState, phase: 'failed' });
  await store.enter();
  await store.settleScroll();
  expect(repository.calls).toHaveLength(1);
  store.leave(null);
  const returning = store.enter();
  expect(repository.calls[1].query).toEqual({ mode: 'initial' });
  repository.calls[1].resolve(initial());
  await returning;
});

test('paging_reorders_a_movie_with_a_changed_date_without_duplicating_it', async () => {
  const { store, repository } = await ready();
  const movedMovie = movie(123, '1995-01-01');
  const sameDay = movie(80, '2001-09-26');
  const older = store.load('older');
  repository.calls[1].resolve(page([sameDay, movedMovie], { olderCursor: 'older-2' }));
  await older;
  expect(store.getSnapshot().items).toEqual([sameDay, olderMovie, movedMovie]);
  expect(store.getSnapshot().asOf).toBe('2026-11-26');
});

test.each(['newer', 'older'] as const)('one request per edge and concurrent directions when %s resolves first', async first => {
  const { store, repository } = await ready();
  const older = store.load('older');
  const newer = store.load('newer');
  const repeatedOlder = store.load('older');
  const repeatedNewer = store.load('newer');
  expect(repository.calls.slice(1).map(call => call.query)).toEqual([
    { mode: 'page', direction: 'older', cursor: 'older-1' },
    { mode: 'page', direction: 'newer', cursor: 'newer-1' },
  ]);
  expect(store.getSnapshot()).toMatchObject({ fetchingOlder: true, fetchingNewer: true });
  const oldest = movie(4, '1989-08-09');
  if (first === 'newer') {
    repository.calls[2].resolve(page([newerMovie], { newerCursor: 'newer-2' }));
    await newer;
    expect(store.getSnapshot()).toMatchObject({ fetchingOlder: true, fetchingNewer: false });
    repository.calls[1].resolve(page([oldest], { olderCursor: 'older-2' }));
  } else {
    repository.calls[1].resolve(page([oldest], { olderCursor: 'older-2' }));
    await older;
    expect(store.getSnapshot()).toMatchObject({ fetchingOlder: false, fetchingNewer: true });
    repository.calls[2].resolve(page([newerMovie], { newerCursor: 'newer-2' }));
  }
  await Promise.all([older, newer, repeatedOlder, repeatedNewer]);
  expect(store.getSnapshot()).toMatchObject({
    items: [newerMovie, savedMovie, olderMovie, oldest], olderCursor: 'older-2', newerCursor: 'newer-2',
    fetchingOlder: false, fetchingNewer: false, asOf: '2026-11-26',
  });
});

test('an_empty_page_disables_only_its_own_edge', async () => {
  const { store, repository } = await ready();
  const newer = store.load('newer');
  repository.calls[1].resolve(page([]));
  await newer;
  await store.load('newer');
  expect(repository.calls).toHaveLength(2);
  expect(store.getSnapshot()).toMatchObject({
    items: [savedMovie, olderMovie], olderCursor: 'older-1', newerCursor: null, asOf: '2026-11-26',
  });
});

test('paging_failure_keeps_the_failed_edge_for_a_later_explicit_retry', async () => {
  const { store, repository } = await ready();
  const older = store.load('older');
  repository.calls[1].reject(new Error('offline'));
  await older;
  expect(store.getSnapshot()).toMatchObject({
    items: [savedMovie, olderMovie], olderCursor: 'older-1', newerCursor: 'newer-1', fetchingOlder: false,
  });
  expect(repository.calls).toHaveLength(2);
  const retry = store.load('older');
  expect(repository.calls[2].query).toEqual({ mode: 'page', direction: 'older', cursor: 'older-1' });
  repository.calls[2].resolve(page([]));
  await retry;
});

test('prepending_requests_restoration_with_the_latest_visible_movie_and_offset', async () => {
  const { store, repository } = await ready();
  store.rememberAnchor(saved);
  const newer = store.load('newer');
  store.rememberAnchor({ releaseDate: '2001-09-26', id: 34, offset: 18 }, true);
  repository.calls[1].resolve(page([newerMovie]));
  await newer;
  expect(store.getSnapshot().restoration?.anchor).toEqual({ releaseDate: '2001-09-26', id: 34, offset: 18 });
});

test('departure_aborts_both_edges_refuses_hidden_paging_and_ignores_late_replies', async () => {
  const { store, repository } = await ready();
  const oldOlder = store.load('older');
  const oldNewer = store.load('newer');
  store.leave(saved);
  await store.load('older');
  await store.load('newer');
  expect(repository.calls).toHaveLength(3);
  expect(repository.calls[1].signal.aborted).toBe(true);
  expect(repository.calls[2].signal.aborted).toBe(true);
  expect(store.getSnapshot()).toMatchObject({
    items: [savedMovie, olderMovie], anchor: saved, fetchingOlder: false, fetchingNewer: false,
  });

  const returning = store.enter();
  repository.calls[3].resolve(page([savedMovie], {
    asOf: '2026-11-27', anchorIndex: 0, olderCursor: 'older-1',
  }));
  await returning;
  const current = store.load('older');
  repository.calls[1].resolve(page([olderMovie]));
  repository.calls[2].reject(new Error('stale'));
  await Promise.all([oldOlder, oldNewer]);
  expect(store.getSnapshot()).toMatchObject({
    items: [savedMovie], fetchingOlder: true, olderCursor: 'older-1', asOf: '2026-11-27',
  });
  repository.calls[4].resolve(page([]));
  await current;
});

test('movement_cancels_obsolete_refresh_and_allows_only_one_replacement_per_entry', async () => {
  const { store, repository } = await ready();
  store.leave(saved);
  const returning = store.enter();
  store.rememberAnchor({ ...saved, offset: -48 }, true);
  const latest = { releaseDate: '2001-09-26', id: 34, offset: 14 };
  store.rememberAnchor(latest, true);
  expect(repository.calls[1].signal.aborted).toBe(true);
  repository.calls[1].resolve(page([newerMovie], { asOf: '2026-11-27' }));
  await returning;
  expect(store.getSnapshot()).toMatchObject({ items: [savedMovie, olderMovie], anchor: latest });

  const paging = store.load('older');
  expect(repository.calls[2].query).toEqual({ mode: 'page', direction: 'older', cursor: 'older-1' });
  const replacement = store.settleScroll();
  const repeatedSettle = store.settleScroll();
  expect(repository.calls[2].signal.aborted).toBe(true);
  expect(repository.calls[3].query).toEqual({ mode: 'anchor', anchor: { releaseDate: '2001-09-26', id: 34 } });
  store.rememberAnchor({ ...latest, offset: 22 }, true);
  expect(repository.calls[3].signal.aborted).toBe(true);
  repository.calls[2].resolve(page([newerMovie]));
  repository.calls[3].resolve(page([newerMovie], { asOf: '2026-11-27' }));
  await Promise.all([paging, replacement, repeatedSettle]);
  await store.settleScroll();
  expect(repository.calls).toHaveLength(4);
  expect(store.getSnapshot()).toMatchObject({
    items: [savedMovie, olderMovie], asOf: '2026-11-26', anchor: { ...latest, offset: 22 },
  });

  store.leave({ ...latest, offset: 22 });
  const nextEntry = store.enter();
  expect(repository.calls[4].query).toEqual({ mode: 'anchor', anchor: { releaseDate: '2001-09-26', id: 34 } });
  store.rememberAnchor(saved, true);
  const nextReplacement = store.settleScroll();
  expect(repository.calls[5].query).toEqual({ mode: 'anchor', anchor: { releaseDate: '2022-08-03', id: 123 } });
  repository.calls[4].reject(new Error('stale'));
  repository.calls[5].resolve(page([savedMovie], { asOf: '2026-11-27', anchorIndex: 0 }));
  await Promise.all([nextEntry, nextReplacement]);
  expect(store.getSnapshot()).toMatchObject({ items: [savedMovie], restoration: { anchor: saved } });
});

test('programmatic_anchor_measurement_keeps_refresh_running', async () => {
  const { store, repository } = await ready();
  store.leave(saved);
  const returning = store.enter();
  store.rememberAnchor(saved);
  await store.settleScroll();
  expect(repository.calls).toHaveLength(2);
  expect(repository.calls[1].signal.aborted).toBe(false);
  repository.calls[1].resolve(page([savedMovie], { asOf: '2026-11-27', anchorIndex: 0 }));
  await returning;
  expect(store.getSnapshot().restoration?.anchor).toEqual(saved);
});

test('visible_guest_creation_clears_cache_and_rejects_responses_for_the_old_guest', async () => {
  const { store, repository, sessions } = await ready();
  store.rememberAnchor(saved);
  const older = store.load('older');
  const newer = store.load('newer');
  sessions.createGuest();
  expect(repository.calls[1].signal.aborted).toBe(true);
  expect(repository.calls[2].signal.aborted).toBe(true);
  expect(repository.calls[3].query).toEqual({ mode: 'initial' });
  expect(store.getSnapshot()).toEqual({ ...initialTimelineState, phase: 'loading' });
  repository.calls[1].resolve(page([olderMovie]));
  repository.calls[2].resolve(page([newerMovie]));
  await Promise.all([older, newer]);
  expect(store.getSnapshot()).toEqual({ ...initialTimelineState, phase: 'loading' });
  repository.calls[3].resolve(page([movie(111, '2003-01-01')], { asOf: '2026-11-26' }));
  await Promise.resolve();
  expect(store.getSnapshot().items.map(item => item.id)).toEqual([111]);
});

test('guest_bootstrap_during_the_first_entry_restarts_the_initial_read_once', async () => {
  const { store, repository, sessions } = harness();
  const entering = store.enter();
  sessions.createGuest();
  expect(repository.calls.map(call => call.query)).toEqual([{ mode: 'initial' }, { mode: 'initial' }]);
  expect(repository.calls[0].signal.aborted).toBe(true);
  repository.calls[0].resolve(initial());
  await entering;
  expect(store.getSnapshot().items).toEqual([]);
  repository.calls[1].resolve(page([olderMovie], { asOf: '2026-11-26' }));
  await Promise.resolve();
  expect(store.getSnapshot().items).toEqual([olderMovie]);
});

test('late_viewport_measurements_cannot_restore_an_anchor_for_an_old_guest', async () => {
  const { store, repository, sessions } = await ready();
  store.rememberAnchor(saved);
  sessions.createGuest();
  store.rememberAnchor(saved, true);
  expect(store.getSnapshot().anchor).toBeNull();
  repository.calls[1].resolve(page([olderMovie], { asOf: '2026-11-26' }));
  await Promise.resolve();
  store.leave(saved);
  expect(store.getSnapshot().anchor).toBeNull();
  const returning = store.enter();
  expect(repository.calls[2].query).toEqual({ mode: 'initial' });
  repository.calls[2].resolve(page([olderMovie], { asOf: '2026-11-26' }));
  await returning;
});

test('guest_creation_while_hidden_clears_cache_without_fetching', async () => {
  const { store, repository, sessions } = await ready();
  store.leave(saved);
  sessions.createGuest();
  expect(repository.calls).toHaveLength(1);
  expect(store.getSnapshot()).toBe(initialTimelineState);
  const returning = store.enter();
  expect(repository.calls[1].query).toEqual({ mode: 'initial' });
  repository.calls[1].resolve(page([], { asOf: '2026-11-26' }));
  await returning;
});

test('stop_restart_clears_cache_if_the_guest_generation_changed_while_unsubscribed', async () => {
  const { store, repository, sessions } = await ready();
  store.rememberAnchor(saved);
  const paging = store.load('newer');
  store.stop();
  expect(repository.calls[1].signal.aborted).toBe(true);
  expect(store.getSnapshot().items).toEqual([savedMovie, olderMovie]);
  sessions.createGuest();
  expect(store.getSnapshot()).toBe(initialTimelineState);
  store.start();
  expect(store.getSnapshot()).toBe(initialTimelineState);
  expect(repository.calls).toHaveLength(2);
  repository.calls[1].resolve(page([newerMovie]));
  await paging;
  expect(store.getSnapshot()).toBe(initialTimelineState);
  const entering = store.enter();
  expect(repository.calls[2].query).toEqual({ mode: 'initial' });
  repository.calls[2].resolve(page([], { asOf: '2026-11-26' }));
  await entering;
});

test('subscriptions_timers_and_following_changes_do_not_refresh_the_route', async () => {
  jest.useFakeTimers();
  try {
    const { store, repository, sessions } = await ready();
    const unsubscribe = store.subscribe(() => {});
    unsubscribe();
    const unsubscribeRemount = store.subscribe(() => {});
    const following = new DeferredFollowing();
    const followingStore = new FollowingStore(
      new ListFollowing(following), new FollowPerson(following), new UnfollowPerson(following), sessions,
    );
    followingStore.start();
    following.listCalls[0].resolve(snapshot());
    await Promise.resolve();
    expect(followingStore.requestFollow(person(19))).toBe(true);
    await Promise.resolve();
    following.followCalls[0].resolve(snapshot(19));
    await Promise.resolve();
    expect(followingStore.getSnapshot().confirmed?.people).toEqual([person(19)]);
    jest.advanceTimersByTime(60_000);
    await store.enter();
    expect(repository.calls).toHaveLength(1);
    unsubscribeRemount();
    followingStore.stop();
  } finally {
    jest.useRealTimers();
  }
});
