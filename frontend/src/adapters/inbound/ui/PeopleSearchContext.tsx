import { createContext } from 'react';
import type { SearchPeople } from '../../../application/use-cases/search-people';
export const PeopleSearchContext = createContext<{ searchPeople: SearchPeople } | null>(null);
