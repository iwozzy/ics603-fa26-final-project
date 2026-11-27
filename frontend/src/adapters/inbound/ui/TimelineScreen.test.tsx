import { act, fireEvent, screen } from '@testing-library/react-native';
import type { ComponentRef } from 'react';
import { FlatList, type View, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import * as viewportModule from './useTimelineViewport';
import { renderTimeline } from '../../../test-utils/renderTimeline';
import * as listModule from './TimelineList';
import TimelineScreen from './TimelineScreen';

let mockFocused = true;
jest.mock('expo-router', () => ({
  useFocusEffect: (effect: () => void | (() => void)) => {
    const React = jest.requireActual<typeof import('react')>('react');
    const focused = mockFocused;
    React.useEffect(() => { if (focused) return effect(); }, [effect, focused]);
  },
}));
beforeEach(() => { mockFocused = true; });
afterEach(() => jest.restoreAllMocks());
const movie = { id: 13, title: 'A movie', releaseDate: '2022-08-03', overview: null, posterImageUrl: null };
const page = { items: [movie], olderCursor: null, newerCursor: 'future', asOf: '2026-11-26', anchorIndex: null };

test.each(['loading', 'error', 'empty'])('%s leaves the timeline content blank', async phase => {
  const { repository } = await renderTimeline();
  if (phase === 'error') await act(() => repository.calls[0].reject(new Error('offline')));
  if (phase === 'empty') await act(() => repository.calls[0].resolve({ ...page, items: [] }));
  expect(screen.queryByRole('progressbar')).toBeNull();
  expect(screen.queryByRole('button')).toBeNull();
  expect(screen.queryByText(/./)).toBeNull();
});

test.each([{ items: [] }, { items: [movie] }])('mount callbacks are passive and a top drag pages once for %j', async ({ items }) => {
  const listRender = jest.spyOn(FlatList.prototype, 'render');
  const { repository } = await renderTimeline();
  await act(() => repository.calls[0].resolve({ ...page, items }));
  const mountedList = listRender.mock.contexts[0] as FlatList;
  await act(() => mountedList.props.onStartReached!({ distanceFromStart: 0 }));
  expect(repository.calls.map(call => call.query)).toEqual([{ mode: 'initial' }]);
  const list = screen.getByTestId('timeline-gestures');
  await fireEvent(list, 'touchStart', { nativeEvent: { pageY: 40 } });
  await fireEvent(list, 'touchMove', { nativeEvent: { pageY: 80 } });
  expect(repository.calls.map(call => call.query)).toEqual([
    { mode: 'initial' }, { mode: 'page', direction: 'newer', cursor: 'future' },
  ]);
  await act(() => repository.calls[1].reject(new Error('offline')));
  await fireEvent(list, 'touchMove', { nativeEvent: { pageY: 100 } });
  expect(repository.calls).toHaveLength(2);
  await fireEvent(list, 'touchMove', { nativeEvent: { pageY: 60 } });
  await fireEvent(list, 'touchMove', { nativeEvent: { pageY: 100 } });
  expect(repository.calls).toHaveLength(3);
});

test('each focus enters once and discarded guest and focus callbacks cannot move a shared movie', async () => {
  const renderList = jest.spyOn(listModule, 'TimelineList');
  const { repository, sessions, store, view } = await renderTimeline();
  await act(() => repository.calls[0].resolve(page));
  const oldGuest = renderList.mock.calls.at(-1)![0];
  await act(() => sessions.createGuest());
  await act(() => repository.calls[1].resolve(page));
  const anchor = { id: 13, releaseDate: '2022-08-03', offset: -17 };
  await act(() => oldGuest.onAnchor(anchor, true));
  expect(store.getSnapshot().anchor).toBeNull();
  const current = renderList.mock.calls.at(-1)![0];
  await act(() => current.onAnchor(anchor, false));
  const leave = jest.spyOn(store, 'leave');
  mockFocused = false;
  await view.rerender(<TimelineScreen />);
  expect(leave).toHaveBeenCalledTimes(1);
  mockFocused = true;
  await view.rerender(<TimelineScreen />);
  expect(repository.calls.map(call => call.query)).toEqual([
    { mode: 'initial' }, { mode: 'initial' }, { mode: 'anchor', anchor: { id: 13, releaseDate: '2022-08-03' } },
  ]);
  await act(() => current.onAnchor({ ...anchor, offset: -90 }, true));
  expect(repository.calls[2].signal.aborted).toBe(false);
  expect(store.getSnapshot().anchor).toEqual(anchor);
});

test('route return keeps the mounted list and cached movie while refresh is pending', async () => {
  const listRender = jest.spyOn(FlatList.prototype, 'render');
  const renderList = jest.spyOn(listModule, 'TimelineList');
  const { repository, store, sessions, view } = await renderTimeline();
  await act(() => repository.calls[0].resolve(page));
  const mountedList = listRender.mock.contexts.at(-1);
  const anchor = { id: movie.id, releaseDate: movie.releaseDate, offset: -17 };
  await act(() => store.rememberAnchor(anchor));

  mockFocused = false;
  await view.rerender(<TimelineScreen />);
  expect(screen.getByRole('header', { name: movie.title })).toBeTruthy();
  const inactive = renderList.mock.calls.at(-1)![0];
  await act(() => inactive.onAnchor({ ...anchor, offset: -90 }, true));
  await act(() => inactive.onLoad('newer'));
  expect(store.getSnapshot().anchor).toEqual(anchor);
  expect(repository.calls).toHaveLength(1);

  mockFocused = true;
  await view.rerender(<TimelineScreen />);
  expect(repository.calls[1].query).toEqual({ mode: 'anchor', anchor: { id: movie.id, releaseDate: movie.releaseDate } });
  expect(store.getSnapshot().phase).toBe('loading');
  expect(screen.getByRole('header', { name: movie.title })).toBeTruthy();
  expect(listRender.mock.contexts.at(-1)).toBe(mountedList);
  await act(() => inactive.onAnchor({ ...anchor, offset: -90 }, true));
  expect(store.getSnapshot().anchor).toEqual(anchor);
  expect(repository.calls[1].signal.aborted).toBe(false);

  await act(() => repository.calls[1].resolve(page));
  expect(listRender.mock.contexts.at(-1)).toBe(mountedList);
  await act(() => sessions.createGuest());
  expect(listRender.mock.contexts.at(-1)).not.toBe(mountedList);
  expect(screen.queryByRole('header', { name: movie.title })).toBeNull();
});

test('reentry seeks the retained movie even when it lies far beyond the first virtualized batch', async () => {
  const scrollToIndex = jest.spyOn(FlatList.prototype, 'scrollToIndex');
  const { repository, store, view } = await renderTimeline();
  const items = Array.from({ length: 200 }, (_, index) => ({ ...movie, id: index + 1, title: 'Film ' + (index + 1) }));
  await act(() => repository.calls[0].resolve({ ...page, items }));
  await act(() => store.rememberAnchor({ releaseDate: movie.releaseDate, id: 41, offset: -13 }));
  mockFocused = false;
  await view.rerender(<TimelineScreen />);
  mockFocused = true;
  await view.rerender(<TimelineScreen />);
  // The native test host does not execute scrolling or measure row positions.
  // Movie 41 is index 159 in the store's descending-ID order.
  expect(scrollToIndex).toHaveBeenCalledWith({ index: 159, animated: false });
  expect(repository.calls[1].query).toEqual({ mode: 'anchor', anchor: { id: 41, releaseDate: movie.releaseDate } });
});

test('returning accepts a fresh edge gesture even when its cursor was latched on the previous visit', async () => {
  const { repository, view } = await renderTimeline();
  await act(() => repository.calls[0].resolve(page));
  const region = screen.getByTestId('timeline-gestures');
  await fireEvent(region, 'touchStart', { nativeEvent: { pageY: 50 } });
  await fireEvent(region, 'touchMove', { nativeEvent: { pageY: 70 } });
  await act(() => repository.calls[1].resolve(page));

  mockFocused = false;
  await view.rerender(<TimelineScreen />);
  mockFocused = true;
  await view.rerender(<TimelineScreen />);
  await act(() => repository.calls[2].resolve(page));
  await fireEvent(screen.getByTestId('timeline-gestures'), 'touchStart', { nativeEvent: { pageY: 50 } });
  await fireEvent(screen.getByTestId('timeline-gestures'), 'touchMove', { nativeEvent: { pageY: 70 } });
  expect(repository.calls).toHaveLength(4);
  expect(repository.calls[3].query).toEqual({ mode: 'page', direction: 'newer', cursor: 'future' });
});

test.each(['current', 'queued'])('a %s touch move from a previous visit cannot page after returning', async delivery => {
  const { repository, view } = await renderTimeline();
  await act(() => repository.calls[0].resolve(page));
  const region = screen.getByTestId('timeline-gestures');
  const oldMove = region.props.onTouchMove as (event: { nativeEvent: { pageY: number } }) => void;
  await fireEvent(region, 'touchStart', { nativeEvent: { pageY: 50 } });
  mockFocused = false;
  await view.rerender(<TimelineScreen />);
  mockFocused = true;
  await view.rerender(<TimelineScreen />);
  await act(() => repository.calls[1].resolve(page));

  if (delivery === 'queued') await act(() => oldMove({ nativeEvent: { pageY: 70 } }));
  else await fireEvent(screen.getByTestId('timeline-gestures'), 'touchMove', { nativeEvent: { pageY: 70 } });
  expect(repository.calls).toHaveLength(2);

  await fireEvent(screen.getByTestId('timeline-gestures'), 'touchStart', { nativeEvent: { pageY: 50 } });
  await fireEvent(screen.getByTestId('timeline-gestures'), 'touchMove', { nativeEvent: { pageY: 70 } });
  expect(repository.calls).toHaveLength(3);
  expect(repository.calls[2].query).toEqual({ mode: 'page', direction: 'newer', cursor: 'future' });
});

test('layout of an accepted short newer page cannot consume another cursor without fresh intent', async () => {
  const listRender = jest.spyOn(FlatList.prototype, 'render');
  const { repository } = await renderTimeline();
  await act(() => repository.calls[0].resolve({ ...page, items: [] }));
  const region = screen.getByTestId('timeline-gestures');
  await fireEvent(region, 'touchStart', { nativeEvent: { pageY: 50 } });
  await fireEvent(region, 'touchMove', { nativeEvent: { pageY: 70 } });
  await act(() => repository.calls[1].resolve({ ...page, newerCursor: 'next' }));
  const list = listRender.mock.contexts.at(-1) as FlatList;
  await act(() => list.props.onStartReached!({ distanceFromStart: 0 }));
  expect(repository.calls).toHaveLength(2);
});


function scrollEvent(y: number, height: number, content: number) {
  return { nativeEvent: { contentOffset: { y }, layoutMeasurement: { height }, contentSize: { height: content } } } as NativeSyntheticEvent<NativeScrollEvent>;
}

test.each(['touch', 'scroll'])('opposite %s intent reopens a failed edge when slight overflow cannot leave its threshold', async input => {
  const listRender = jest.spyOn(FlatList.prototype, 'render');
  const { repository } = await renderTimeline();
  await act(() => repository.calls[0].resolve(page));
  const list = listRender.mock.contexts.at(-1) as FlatList;
  await act(() => list.props.onScroll!(scrollEvent(0, 800, 850)));
  const region = screen.getByTestId('timeline-gestures');
  await fireEvent(region, 'touchStart', { nativeEvent: { pageY: 40 } });
  await fireEvent(region, 'touchMove', { nativeEvent: { pageY: 80 } });
  await act(() => repository.calls[1].reject(new Error('offline')));
  await fireEvent(region, 'touchMove', { nativeEvent: { pageY: 120 } });
  expect(repository.calls).toHaveLength(2);
  if (input === 'touch') {
    await fireEvent(region, 'touchMove', { nativeEvent: { pageY: 60 } });
    await fireEvent(region, 'touchMove', { nativeEvent: { pageY: 100 } });
  } else {
    await act(() => list.props.onScroll!(scrollEvent(50, 800, 850)));
    await act(() => list.props.onScroll!(scrollEvent(0, 800, 850)));
  }
  expect(repository.calls.map(call => call.query)).toEqual([
    { mode: 'initial' }, { mode: 'page', direction: 'newer', cursor: 'future' }, { mode: 'page', direction: 'newer', cursor: 'future' },
  ]);
});

test('real movement into a virtualized gap cancels the old refresh and settles at the later measured movie', async () => {
  jest.useFakeTimers();
  try {
    const viewportRender = jest.spyOn(viewportModule, 'useTimelineViewport');
    const listRender = jest.spyOn(FlatList.prototype, 'render');
    const { repository, store, view } = await renderTimeline();
    const next = { ...movie, id: 12 };
    await act(() => repository.calls[0].resolve({ ...page, items: [movie, next] }));
    await act(() => store.rememberAnchor({ id: movie.id, releaseDate: movie.releaseDate, offset: -10 }));
    mockFocused = false;
    await view.rerender(<TimelineScreen />);
    mockFocused = true;
    await view.rerender(<TimelineScreen />);
    expect(repository.calls[1].signal.aborted).toBe(false);
    const list = listRender.mock.contexts.at(-1) as FlatList;
    const region = screen.getByTestId('timeline-gestures');
    await fireEvent(region, 'touchStart', { nativeEvent: { pageY: 80 } });
    await fireEvent(region, 'touchMove', { nativeEvent: { pageY: 40 } });
    await act(() => list.props.onScroll!(scrollEvent(460, 400, 2000)));
    expect(repository.calls[1].signal.aborted).toBe(true);
    expect(store.getSnapshot().anchor).toBeNull();
    await act(() => jest.advanceTimersByTime(250));
    expect(repository.calls).toHaveLength(2);
    const viewport = viewportRender.mock.results.at(-1)!.value;
    const box = (top: number, height: number) => ({ getBoundingClientRect: () => ({ top, height }) }) as unknown as ComponentRef<typeof View>;
    viewport.viewportRef.current = box(20, 400);
    viewport.setRow(next.id, box(-8, 160));
    await act(() => list.props.onContentSizeChange!(600, 2000));
    await act(() => jest.advanceTimersByTime(250));
    expect(repository.calls.map(call => call.query)).toEqual([
      { mode: 'initial' }, { mode: 'anchor', anchor: { id: movie.id, releaseDate: movie.releaseDate } },
      { mode: 'anchor', anchor: { id: next.id, releaseDate: next.releaseDate } },
    ]);
  } finally { jest.useRealTimers(); }
});
