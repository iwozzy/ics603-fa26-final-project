import type { SearchResult } from '../../domain/people';
export interface PeopleSearchRepository { search(query: string, signal: AbortSignal): Promise<SearchResult>; }
