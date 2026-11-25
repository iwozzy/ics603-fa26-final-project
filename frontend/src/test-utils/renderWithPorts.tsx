import { FollowingStore } from '../application/following-store';
import { FollowPerson } from '../application/use-cases/follow-person';
import { UnfollowPerson } from '../application/use-cases/unfollow-person';
import { ListFollowing } from '../application/use-cases/list-following';
import { FakeSessions, snapshot } from './fakes/following';
import { FollowingContext } from '../adapters/inbound/ui/FollowingContext';
import type { PropsWithChildren, ReactElement } from 'react';
import { render } from '@testing-library/react-native';
import type { PeopleSearchRepository } from '../application/ports/people-search-repository';
import { SearchPeople } from '../application/use-cases/search-people';
import { PeopleSearchContext } from '../adapters/inbound/ui/PeopleSearchContext';
export function portsWrapper(repository: PeopleSearchRepository) {
  const searchPeople = new SearchPeople(repository);
  const repositoryFollowing = { unfollow: async () => {}, list: async () => snapshot(), follow: async () => snapshot() };
  const followingStore = new FollowingStore(new ListFollowing(repositoryFollowing), new FollowPerson(repositoryFollowing), new UnfollowPerson(repositoryFollowing), new FakeSessions());
  followingStore.start();
  return function Wrapper({ children }: PropsWithChildren) { return <PeopleSearchContext.Provider value={{ searchPeople }}><FollowingContext.Provider value={followingStore}>{children}</FollowingContext.Provider></PeopleSearchContext.Provider>; };
}
export function renderWithPorts(element: ReactElement, repository: PeopleSearchRepository) { return render(element, { wrapper: portsWrapper(repository) }); }
