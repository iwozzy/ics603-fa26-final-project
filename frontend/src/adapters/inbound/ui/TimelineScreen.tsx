import { useCallback, useRef, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { TimelineList, type TimelineListHandle } from './TimelineList';
import { useTimeline } from './useTimeline';

export default function TimelineScreen() {
  const { state, store, sessions } = useTimeline();
  const viewport = useRef<TimelineListHandle>(null);
  const entry = useRef(0);
  const [visibleEntry, setVisibleEntry] = useState(0);
  useFocusEffect(useCallback(() => {
    setVisibleEntry(++entry.current);
    void store.enter();
    return () => {
      const anchor = viewport.current?.captureAnchor() ?? null;
      ++entry.current;
      store.leave(anchor);
      setVisibleEntry(0);
    };
  }, [store]));

  const guest = sessions.identityGeneration;
  const active = useCallback(() => entry.current === visibleEntry && guest === sessions.identityGeneration,
    [guest, sessions, visibleEntry]);
  if (!visibleEntry) return null;
  return <TimelineList ref={viewport} key={visibleEntry + '/' + guest} state={state} active={active}
    onAnchor={(anchor, userMoved) => { if (active()) store.rememberAnchor(anchor, userMoved); }}
    onLoad={direction => { if (active()) void store.load(direction); }}
    onScrollSettled={() => { if (active()) void store.settleScroll(); }} />;
}
