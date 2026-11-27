import { useState, type PropsWithChildren } from 'react';
import { PeopleSearchContext } from '../adapters/inbound/ui/PeopleSearchContext';
import { FollowingProvider } from '../adapters/inbound/ui/FollowingProvider';
import { TimelineProvider } from '../adapters/inbound/ui/TimelineProvider';
import { createContainer } from './container';
export function Providers({ children }: PropsWithChildren) {
  const [container] = useState(() => createContainer(globalThis.fetch.bind(globalThis)));
  return <PeopleSearchContext.Provider value={container}>
    <FollowingProvider store={container.followingStore}>
      <TimelineProvider store={container.timelineStore} sessions={container.sessions}>{children}</TimelineProvider>
    </FollowingProvider>
  </PeopleSearchContext.Provider>;
}
