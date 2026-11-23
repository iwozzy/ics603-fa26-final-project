import { useContext, useSyncExternalStore } from 'react';
import { initialFollowingState } from '../../../application/following-store';
import { FollowingContext } from './FollowingContext';
const serverSnapshot = () => initialFollowingState;
export function useFollowing() {
  const store = useContext(FollowingContext);
  if (!store) throw new Error('FollowingContext is required');
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, serverSnapshot);
  return { state, follow: store.requestFollow, refresh: store.refresh };
}
