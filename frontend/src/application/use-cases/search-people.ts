import { normalizeQuery, type SearchResult } from '../../domain/people';
import type { PeopleSearchRepository } from '../ports/people-search-repository';
export class SearchPeople {
  constructor(private readonly repository: PeopleSearchRepository) {}
  async execute(rawQuery: string, signal: AbortSignal): Promise<SearchResult> { return this.repository.search(normalizeQuery(rawQuery), signal); }
}
