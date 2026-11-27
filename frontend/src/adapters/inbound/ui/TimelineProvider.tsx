import { useEffect, useMemo, type PropsWithChildren } from 'react';
import { TimelineContext, type TimelineServices } from './TimelineContext';

export function TimelineProvider({ store, sessions, children }: PropsWithChildren<TimelineServices>) {
  useEffect(() => {
    store.start();
    return () => store.stop();
  }, [store]);
  const services = useMemo(() => ({ store, sessions }), [store, sessions]);
  return <TimelineContext.Provider value={services}>{children}</TimelineContext.Provider>;
}
