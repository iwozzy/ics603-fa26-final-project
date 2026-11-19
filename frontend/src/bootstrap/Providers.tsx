import { useState, type PropsWithChildren } from 'react';
import { PeopleSearchContext } from '../adapters/inbound/ui/PeopleSearchContext';
import { createContainer } from './container';
export function Providers({ children }: PropsWithChildren) {
  const [container] = useState(() => createContainer(globalThis.fetch.bind(globalThis)));
  return <PeopleSearchContext.Provider value={container}>{children}</PeopleSearchContext.Provider>;
}
