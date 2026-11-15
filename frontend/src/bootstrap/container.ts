import { SearchPeople } from '../application/use-cases/search-people';
import { HttpGuestSessionRepository } from '../adapters/outbound/api/guest-session-repository';
import { HttpPeopleSearchRepository } from '../adapters/outbound/api/people-search-repository';
export function createContainer(fetchImpl: typeof fetch) {
  const sessions = new HttpGuestSessionRepository(fetchImpl);
  return { searchPeople: new SearchPeople(new HttpPeopleSearchRepository(fetchImpl, sessions)) };
}
