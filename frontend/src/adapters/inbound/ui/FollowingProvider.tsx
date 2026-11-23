import { useEffect, type PropsWithChildren } from 'react';
import type { FollowingStore } from '../../../application/following-store';
import { FollowingContext } from './FollowingContext';
export function FollowingProvider({ store, children }: PropsWithChildren<{ store: FollowingStore }>) {
  useEffect(() => {
    store.start();
    return () => { store.stop(); };
  }, [store]);
  return <FollowingContext.Provider value={store}>{children}</FollowingContext.Provider>;
}
