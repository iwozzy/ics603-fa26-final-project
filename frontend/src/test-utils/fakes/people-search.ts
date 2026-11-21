import type { PeopleSearchRepository } from '../../application/ports/people-search-repository';
import type { SearchResult } from '../../domain/people';
export class DeferredRepository implements PeopleSearchRepository {
  readonly calls: { query: string; signal: AbortSignal; resolve(value: SearchResult): void; reject(error: Error): void }[] = [];
  search(query: string, signal: AbortSignal): Promise<SearchResult> { return new Promise((resolve, reject) => { this.calls.push({ query, signal, resolve, reject }); }); }
}
export function result(query: string): SearchResult { return { query, people: [{ provider: 'tmdb', providerId: 4139, name: query, knownForDepartment: null, profileImageUrl: null, knownFor: [] }] }; }
