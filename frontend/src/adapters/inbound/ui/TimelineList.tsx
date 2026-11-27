import { useCallback, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState, type Ref } from 'react';
import { FlatList, StyleSheet, View, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import type { TimelineViewState } from '../../../application/timeline-store';
import type { MovieSummary, TimelineAnchor } from '../../../domain/timeline';
import { MovieRow } from './MovieRow';
import { createTimelineGestures, type TimelineDirection } from './timeline-gestures';
import { useTimelineViewport } from './useTimelineViewport';
import { useThemedStyles, type ThemeColors } from './theme';

export interface TimelineListHandle { captureAnchor(): TimelineAnchor | null }
interface Props {
  ref?: Ref<TimelineListHandle>;
  state: TimelineViewState;
  active(): boolean;
  onAnchor(anchor: TimelineAnchor | null, userMoved: boolean): void;
  onScrollSettled(): void;
  onLoad(direction: TimelineDirection): void;
}

const edgeThreshold = 0.12;
const movieKey = (movie: MovieSummary) => String(movie.id);

export function TimelineList({ ref, state, active, onAnchor, onScrollSettled, onLoad }: Props) {
  const styles = useThemedStyles(createStyles);
  const viewport = useTimelineViewport(state.items, state.restoration, active);
  const [initialWindow] = useState(() => ({
    revision: state.restoration?.revision, index: state.items.findIndex(movie => movie.id === state.restoration?.anchor?.id),
  }));
  const intent = useRef<TimelineDirection | null>(null);
  const latched = useRef<Partial<Record<TimelineDirection, string>>>({});
  const awaitingMeasurement = useRef(false);
  const settle = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useLayoutEffect(() => {
    // Focus changes retain the list, but each visit starts with fresh gesture state.
    intent.current = null;
    latched.current = {};
    awaitingMeasurement.current = false;
    clearTimeout(settle.current);
    settle.current = undefined;
  }, [active]);
  const { listRef, viewportRef, scroll, captureAnchor, setRow, onRowLayout } = viewport;
  useImperativeHandle(ref, () => ({ captureAnchor: () => active() ? captureAnchor() : null }), [active, captureAnchor]);
  function remember(userMoved: boolean) {
    if (!active()) return;
    const anchor = captureAnchor();
    if (userMoved || anchor) onAnchor(anchor, userMoved);
    if (userMoved) awaitingMeasurement.current = !anchor;
    if (anchor && awaitingMeasurement.current) {
      awaitingMeasurement.current = false;
      if (settle.current === undefined) onScrollSettled();
    }
  }
  function nearEdge(direction: TimelineDirection) {
    const { y, height, content } = scroll.current;
    return direction === 'newer' ? y <= height * edgeThreshold : content - height - y <= height * edgeThreshold;
  }
  function requestEdge(direction: TimelineDirection) {
    if (!active() || intent.current !== direction || state.phase === 'loading' || !nearEdge(direction)) return;
    const newer = direction === 'newer';
    const cursor = newer ? state.newerCursor : state.olderCursor;
    if (!cursor || latched.current[direction] === cursor || (newer ? state.fetchingNewer : state.fetchingOlder)) return;
    intent.current = null;
    latched.current[direction] = cursor;
    remember(false);
    onLoad(direction);
  }
  function scheduleSettle() {
    clearTimeout(settle.current);
    settle.current = setTimeout(() => {
      settle.current = undefined;
      intent.current = null;
      if (active() && !awaitingMeasurement.current) onScrollSettled();
    }, 160);
  }
  function onIntent(direction: TimelineDirection, userMoved = false) {
    if (!active()) return;
    viewport.onUserIntent();
    if (userMoved) remember(true);
    intent.current = direction;
    // On a short scroll range every offset is near both edges. Opposite intent leaves the edge.
    const { content, height } = scroll.current;
    if (content - height <= height * edgeThreshold) {
      delete latched.current[direction === 'newer' ? 'older' : 'newer'];
    }
    requestEdge(direction);
    scheduleSettle();
  }
  const latestIntent = useRef(onIntent);
  useLayoutEffect(() => { latestIntent.current = onIntent; });
  // The adapter stores this callback and invokes it only from native or browser events.
  // eslint-disable-next-line react-hooks/refs
  const gestures = useMemo(() => createTimelineGestures(direction => {
    if (active()) latestIntent.current(direction);
  }), [active]);
  useLayoutEffect(() => {
    const detach = gestures.attach(listRef.current?.getScrollableNode());
    return () => { detach(); clearTimeout(settle.current); };
  }, [gestures, listRef]);

  function onScroll({ nativeEvent }: NativeSyntheticEvent<NativeScrollEvent>) {
    if (!active()) return;
    const delta = viewport.updateScroll(nativeEvent);
    if (!nearEdge('newer')) delete latched.current.newer;
    if (!nearEdge('older')) delete latched.current.older;
    if (delta) onIntent(delta < 0 ? 'newer' : 'older', true);
  }

  const latestLayout = useRef(() => {});
  useLayoutEffect(() => {
    latestLayout.current = () => {
      if (!active()) return;
      onRowLayout();
      remember(false);
    };
  });
  const layout = useCallback(() => latestLayout.current(), []);
  const renderItem = useCallback(({ item }: { item: MovieSummary }) =>
    <View collapsable={false} ref={node => setRow(item.id, node)} onLayout={layout} testID={'timeline-row-' + item.id}>
      <MovieRow movie={item} />
    </View>, [layout, setRow]);
  return <View testID="timeline-gestures" ref={viewportRef} collapsable={false} style={styles.region} {...gestures.touchHandlers}>
    <FlatList ref={listRef} data={state.items} renderItem={renderItem} keyExtractor={movieKey}
      initialScrollIndex={initialWindow.revision === state.restoration?.revision && initialWindow.index > 0 ? initialWindow.index : undefined}
      role="region" accessibilityLabel="Movie timeline" style={styles.region} scrollEventThrottle={16} onScroll={onScroll}
      onLayout={event => { viewport.onViewportHeight(event.nativeEvent.layout.height); layout(); }}
      onContentSizeChange={(_width, height) => { viewport.onContentHeight(height); layout(); }}
      onViewableItemsChanged={layout} onScrollToIndexFailed={viewport.onScrollToIndexFailed}
      onStartReached={() => requestEdge('newer')} onEndReached={() => requestEdge('older')}
      onStartReachedThreshold={edgeThreshold} onEndReachedThreshold={edgeThreshold}
      ListFooterComponent={viewport.footerHeight ? <View style={{ height: viewport.footerHeight }} /> : undefined} />
  </View>;
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({ region: { flex: 1, minHeight: 0, backgroundColor: colors.background } });
