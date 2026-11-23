import { useEffect, type PropsWithChildren } from 'react';
import { AppState, Platform } from 'react-native';
import type { FollowingStore } from '../../../application/following-store';
import { FollowingContext } from './FollowingContext';
export function FollowingProvider({ store, children }: PropsWithChildren<{ store: FollowingStore }>) {
  useEffect(() => {
    store.start();
    let cleanup: () => void;
    if (Platform.OS === 'web' && typeof window !== 'undefined' && typeof document !== 'undefined') {
      const refresh = () => { if (document.visibilityState === 'visible') void store.refresh(); };
      window.addEventListener('focus', refresh); document.addEventListener('visibilitychange', refresh);
      cleanup = () => { window.removeEventListener('focus', refresh); document.removeEventListener('visibilitychange', refresh); };
    } else {
      const subscription = AppState.addEventListener('change', state => { if (state === 'active') void store.refresh(); });
      cleanup = () => subscription.remove();
    }
    return () => { cleanup(); store.stop(); };
  }, [store]);
  return <FollowingContext.Provider value={store}>{children}</FollowingContext.Provider>;
}
