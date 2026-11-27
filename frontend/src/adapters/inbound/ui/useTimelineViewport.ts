import { useCallback, useLayoutEffect, useMemo, useRef, useState, type ComponentRef } from 'react';
import type { FlatList, NativeScrollEvent, View } from 'react-native';
import type { TimelineViewState } from '../../../application/timeline-store';
import type { MovieSummary, TimelineAnchor } from '../../../domain/timeline';

type RowNode = ComponentRef<typeof View>;
type Box = { top: number; height: number };
// RN host views and RN Web host nodes expose synchronous window coordinates.
function bounds(view: RowNode | null | undefined): Box | undefined {
  return view?.getBoundingClientRect?.();
}

const alwaysActive = () => true;
export function useTimelineViewport(items: readonly MovieSummary[], restoration: TimelineViewState['restoration'], active = alwaysActive) {
  const viewportRef = useRef<RowNode>(null);
  const listRef = useRef<FlatList<MovieSummary>>(null);
  const rows = useRef(new Map<number, RowNode>());
  const movies = useMemo(() => new Map(items.map(movie => [movie.id, movie])), [items]);
  const scroll = useRef({ y: 0, height: 0, content: 0 });
  const target = useRef<TimelineAnchor | null>(null);
  const commandedY = useRef<number | null>(null);
  const measuredNode = useRef<RowNode | undefined>(undefined);
  const indexSeek = useRef<'seeking' | 'aligned' | null>(null);
  const [footerHeight, setFooterHeight] = useState(0);
  const setRow = useCallback((id: number, node: RowNode | null) => {
    if (node) rows.current.set(id, node);
    else rows.current.delete(id);
  }, []);

  const captureAnchor = useCallback((): TimelineAnchor | null => {
    if (target.current) return target.current;
    const viewport = bounds(viewportRef.current);
    if (!viewport || !viewport.height) return null;
    let first: TimelineAnchor | null = null;
    for (const [id, row] of rows.current) {
      const rect = bounds(row);
      const movie = movies.get(id);
      if (!movie || !rect?.height) continue;
      const offset = rect.top - viewport.top;
      if (offset + rect.height > 0 && offset < viewport.height && (!first || offset < first.offset)) {
        first = { id, releaseDate: movie.releaseDate, offset };
      }
    }
    return first;
  }, [movies]);

  const correct = useCallback(() => {
    const anchor = target.current;
    const viewport = bounds(viewportRef.current);
    if (!active() || !anchor || !viewport?.height || !listRef.current) return false;
    const rowNode = rows.current.get(anchor.id);
    const row = bounds(rowNode);
    if (!row?.height) return false;
    const newHost = rowNode !== measuredNode.current;
    measuredNode.current = rowNode;
    const delta = row.top - viewport.top - anchor.offset;
    if (Math.abs(delta) < 0.5) {
      // An index seek can finish layout before its scroll notification arrives.
      if (indexSeek.current === 'seeking') indexSeek.current = 'aligned';
      return true;
    }
    indexSeek.current = null;
    const node = listRef.current.getScrollableNode();
    const y = typeof node?.scrollTop === 'number' ? node.scrollTop : scroll.current.y;
    const offset = Math.max(0, y + delta);
    const content = typeof node?.scrollHeight === 'number' ? node.scrollHeight : scroll.current.content;
    // A last-row fallback may need trailing space to align its top with the viewport.
    if (content > 0 && offset + viewport.height > content + 1) {
      setFooterHeight(footerHeight + Math.ceil(offset + viewport.height - content));
      return true;
    }
    if (newHost || commandedY.current !== offset) {
      commandedY.current = offset;
      listRef.current.scrollToOffset({ offset, animated: false });
    }
    return true;
  }, [active, footerHeight]);

  const correction = useRef(correct);
  useLayoutEffect(() => { correction.current = correct; });
  useLayoutEffect(() => {
    target.current = restoration?.anchor ?? null;
    measuredNode.current = undefined;
    indexSeek.current = null;
    if (!target.current) {
      commandedY.current = null;
      return;
    }
    // A retained-window correction may deliver its scroll event after refresh replaces the data.
    const index = items.findIndex(movie => movie.id === target.current?.id);
    if (index < 0) return;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    function locate() {
      if (!active() || !target.current || correction.current() || attempts >= 6) return;
      ++attempts;
      indexSeek.current = 'seeking';
      listRef.current?.scrollToIndex({ index, animated: false });
      timer = setTimeout(locate, 75);
    }
    locate();
    return () => { clearTimeout(timer); target.current = null; };
  }, [active, restoration, items]);

  const onScrollToIndexFailed = useCallback(({ index, averageItemLength }: { index: number; averageItemLength: number }) => {
    if (active() && target.current && indexSeek.current === 'seeking') {
      listRef.current?.scrollToOffset({ offset: averageItemLength * index, animated: false });
    }
  }, [active]);
  const onUserIntent = useCallback(() => {
    indexSeek.current = null;
    target.current = null;
    commandedY.current = null;
  }, []);
  const updateScroll = useCallback((event: NativeScrollEvent) => {
    const before = scroll.current.y;
    const y = Math.max(0, event.contentOffset.y);
    scroll.current = { y, height: event.layoutMeasurement.height, content: event.contentSize.height };
    const programmatic = indexSeek.current === 'seeking' || (commandedY.current !== null && Math.abs(y - commandedY.current) <= 1);
    const delta = y - before;
    // Virtualization can unmount the anchor, briefly shrink the content, and clamp scrollTop.
    // Its replacement host row needs a fresh correction even if the desired offset is identical.
    if (delta && !programmatic && target.current && commandedY.current !== null && measuredNode.current
      && measuredNode.current !== rows.current.get(target.current.id)) {
      indexSeek.current = 'seeking';
      correction.current();
      return 0;
    }
    if (delta && !programmatic && target.current && (indexSeek.current === 'aligned' || commandedY.current !== null)) {
      const row = bounds(rows.current.get(target.current.id));
      const region = bounds(viewportRef.current);
      if (indexSeek.current === 'aligned') {
        indexSeek.current = null;
        if (row && region && Math.abs(row.top - region.top - target.current.offset) < 1) return 0;
      }
      // FlatList may finish its own initialScrollIndex alignment after our measured correction.
      if (commandedY.current !== null && row && region && Math.abs(row.top - region.top) < 1) {
        commandedY.current = null;
        correction.current();
        return 0;
      }
    }
    if (delta && !programmatic) onUserIntent();
    return programmatic ? 0 : delta;
  }, [onUserIntent]);
  const onViewportHeight = (height: number) => { scroll.current.height = height; };
  const onContentHeight = (height: number) => { scroll.current.content = height; };
  const onRowLayout = useCallback(() => { correction.current(); }, []);
  return { listRef, viewportRef, captureAnchor, setRow, onRowLayout, onScrollToIndexFailed,
    updateScroll, scroll, onViewportHeight, onContentHeight, onUserIntent, footerHeight };
}
