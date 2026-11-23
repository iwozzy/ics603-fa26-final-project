import { useState, type PropsWithChildren } from 'react';
import { PeopleSearchContext } from '../adapters/inbound/ui/PeopleSearchContext';
import { FollowingProvider } from '../adapters/inbound/ui/FollowingProvider';
import { createContainer } from './container';
export function Providers({ children }: PropsWithChildren) {
  const [container] = useState(() => createContainer(globalThis.fetch.bind(globalThis)));
  return <PeopleSearchContext.Provider value={container}><FollowingProvider store={container.followingStore}>{children}</FollowingProvider></PeopleSearchContext.Provider>;
}
