import { act, fireEvent, screen } from '@testing-library/react-native';
import { FlatList } from 'react-native';
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

test('reentry renders the retained movie even when it lies far beyond the first virtualized batch', async () => {
  const { repository, store, view } = await renderTimeline();
  const items = Array.from({ length: 200 }, (_, index) => ({ ...movie, id: index + 1, title: 'Film ' + (index + 1) }));
  await act(() => repository.calls[0].resolve({ ...page, items }));
  await act(() => store.rememberAnchor({ releaseDate: movie.releaseDate, id: 41, offset: -13 }));
  mockFocused = false;
  await view.rerender(<TimelineScreen />);
  mockFocused = true;
  await view.rerender(<TimelineScreen />);
  expect(screen.getByRole('header', { name: 'Film 41' })).toBeTruthy();
  expect(screen.queryByRole('header', { name: 'Film 100' })).toBeNull();
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
