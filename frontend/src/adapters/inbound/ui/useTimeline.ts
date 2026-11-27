import { useContext, useSyncExternalStore } from 'react';
import { initialTimelineState } from '../../../application/timeline-store';
import { TimelineContext } from './TimelineContext';

const serverSnapshot = () => initialTimelineState;

export function useTimeline() {
  const services = useContext(TimelineContext);
  if (!services) throw new Error('TimelineContext is required');
  const { store, sessions } = services;
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, serverSnapshot);
  return { state, store, sessions };
}
