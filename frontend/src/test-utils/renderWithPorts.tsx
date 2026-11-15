import type { PropsWithChildren, ReactElement } from 'react';
import { render } from '@testing-library/react-native';
import type { PeopleSearchRepository } from '../application/ports/people-search-repository';
import { SearchPeople } from '../application/use-cases/search-people';
import { PeopleSearchContext } from '../adapters/inbound/ui/PeopleSearchContext';
export function portsWrapper(repository: PeopleSearchRepository) {
  const searchPeople = new SearchPeople(repository);
  return function Wrapper({ children }: PropsWithChildren) { return <PeopleSearchContext.Provider value={{ searchPeople }}>{children}</PeopleSearchContext.Provider>; };
}
export function renderWithPorts(element: ReactElement, repository: PeopleSearchRepository) { return render(element, { wrapper: portsWrapper(repository) }); }
