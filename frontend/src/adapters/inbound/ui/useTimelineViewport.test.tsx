import { act, renderHook } from '@testing-library/react-native';
import type { ComponentRef } from 'react';
import type { FlatList, View } from 'react-native';
import type { MovieSummary } from '../../../domain/timeline';
import type { TimelineViewState } from '../../../application/timeline-store';
import { useTimelineViewport } from './useTimelineViewport';

const movie = (id: number) => ({ id, releaseDate: '2022-08-03', title: String(id), overview: null, posterImageUrl: null });
const box = (top: number, height: number) => ({ getBoundingClientRect: () => ({ top, height }) }) as unknown as ComponentRef<typeof View>;

test('prepend with simultaneous row resize restores the measured movie relative to the viewport', async () => {
  let items = [movie(3), movie(2), movie(1)];
  let restoration: TimelineViewState['restoration'] = null;
  const hook = await renderHook(() => useTimelineViewport(items, restoration));
  const viewport = hook.result.current;
  const scrollToOffset = jest.fn();
  viewport.listRef.current = { scrollToOffset, getScrollableNode: () => ({ scrollTop: 130 }) } as unknown as FlatList<MovieSummary>;
  viewport.viewportRef.current = box(60, 400);
  viewport.setRow(3, box(-70, 110));
  viewport.setRow(2, box(40, 90));
  viewport.setRow(1, box(130, 90));
  const anchor = viewport.captureAnchor();
  expect(anchor).toEqual({ id: 2, releaseDate: '2022-08-03', offset: -20 });
  items = [movie(4), ...items];
  viewport.setRow(2, box(280, 120));
  restoration = { revision: 1, anchor };
  await hook.rerender(undefined);
  expect(scrollToOffset).toHaveBeenCalledWith({ offset: 370, animated: false });
  await act(() => hook.result.current.onRowLayout());
  expect(scrollToOffset).toHaveBeenCalledTimes(1);
});

test('an unmeasured index gets bounded approximate recovery until its row can be measured', async () => {
  jest.useFakeTimers();
  try {
    const items = Array.from({ length: 50 }, (_, i) => movie(i + 1));
    let restoration: TimelineViewState['restoration'] = null;
    const hook = await renderHook(() => useTimelineViewport(items, restoration));
    const viewport = hook.result.current;
    const scrollToOffset = jest.fn();
    const scrollToIndex = jest.fn(() => viewport.onScrollToIndexFailed({ index: 40, averageItemLength: 100 }));
    viewport.listRef.current = { scrollToIndex, scrollToOffset, getScrollableNode: () => ({ scrollTop: 0 }) } as unknown as FlatList<MovieSummary>;
    viewport.viewportRef.current = box(0, 400);
    restoration = { revision: 4, anchor: { id: 41, releaseDate: '2022-08-03', offset: -9 } };
    await hook.rerender(undefined);
    await act(() => jest.runAllTimers());
    expect(scrollToIndex.mock.calls.length).toBeGreaterThan(0);
    expect(scrollToIndex.mock.calls.length).toBeLessThanOrEqual(6);
    expect(scrollToOffset).toHaveBeenCalledWith({ offset: 4000, animated: false });
    viewport.setRow(41, box(4110, 95));
    await act(() => hook.result.current.onRowLayout());
    expect(scrollToOffset).toHaveBeenLastCalledWith({ offset: 4119, animated: false });
  } finally { jest.useRealTimers(); }
});

test('a deliberate scroll can interrupt an outstanding virtualized seek before its row mounts', async () => {
  const items = [movie(10), movie(9)];
  let restoration: TimelineViewState['restoration'] = null;
  const hook = await renderHook(() => useTimelineViewport(items, restoration));
  hook.result.current.listRef.current = { scrollToIndex: jest.fn() } as unknown as FlatList<MovieSummary>;
  hook.result.current.viewportRef.current = box(100, 500);
  hook.result.current.setRow(10, box(90, 200));
  restoration = { revision: 3, anchor: { id: 9, releaseDate: '2022-08-03', offset: -7 } };
  await hook.rerender(undefined);
  hook.result.current.onUserIntent();
  expect(hook.result.current.captureAnchor()).toEqual({ id: 10, releaseDate: '2022-08-03', offset: -10 });
});

test('a second programmatic index alignment still corrects a nonzero movie offset', async () => {
  const items = [movie(3), movie(2)];
  let restoration: TimelineViewState['restoration'] = null;
  const hook = await renderHook(() => useTimelineViewport(items, restoration));
  const viewport = hook.result.current;
  const node = { scrollTop: 550 };
  const scrollToOffset = jest.fn();
  viewport.listRef.current = { scrollToOffset, getScrollableNode: () => node } as unknown as FlatList<MovieSummary>;
  viewport.viewportRef.current = box(80, 400);
  viewport.setRow(2, box(80, 190));
  restoration = { revision: 5, anchor: { id: 2, releaseDate: '2022-08-03', offset: -15 } };
  await hook.rerender(undefined);
  expect(scrollToOffset).toHaveBeenCalledWith({ offset: 565, animated: false });
  // FlatList can align initialScrollIndex to the row top after measuring its first batch.
  const event = { contentOffset: { y: 550 }, layoutMeasurement: { height: 400 }, contentSize: { height: 2000 } };
  expect(viewport.updateScroll(event as import('react-native').NativeScrollEvent)).toBe(0);
  expect(scrollToOffset).toHaveBeenCalledTimes(2);
});

test('a queued index retry cannot scroll after the route or guest lifetime ends', async () => {
  jest.useFakeTimers();
  try {
    let active = true;
    const items = [movie(3)];
    let restoration: TimelineViewState['restoration'] = null;
    const hook = await renderHook(() => useTimelineViewport(items, restoration, () => active));
    const scrollToIndex = jest.fn();
    hook.result.current.listRef.current = { scrollToIndex } as unknown as FlatList<MovieSummary>;
    restoration = { revision: 9, anchor: { id: 3, releaseDate: '2022-08-03', offset: 0 } };
    await hook.rerender(undefined);
    expect(scrollToIndex).toHaveBeenCalledTimes(1);
    active = false;
    await act(() => jest.runAllTimers());
    expect(scrollToIndex).toHaveBeenCalledTimes(1);
  } finally { jest.useRealTimers(); }
});
