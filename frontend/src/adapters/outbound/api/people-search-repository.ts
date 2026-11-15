import type { GuestSessionRepository } from '../../../application/ports/guest-session-repository';
import type { PeopleSearchRepository } from '../../../application/ports/people-search-repository';
import { SearchFailed } from '../../../domain/errors';
import type { SearchResult } from '../../../domain/people';
import { mapSearchResult } from './mappers';
import { withDeadline } from './transport';

export class HttpPeopleSearchRepository implements PeopleSearchRepository {
  constructor(private readonly fetchImpl: typeof fetch, private readonly sessions: GuestSessionRepository) {}
  async search(query: string, signal: AbortSignal): Promise<SearchResult> {
    try {
      return await withDeadline(signal, async combined => {
        await this.sessions.ensure(combined);
        if (combined.aborted) throw new SearchFailed();
        const response = await this.fetchImpl('/api/v1/people/search?query=' + encodeURIComponent(query), { credentials: 'same-origin', signal: combined });
        if (!response.ok) throw new SearchFailed();
        return mapSearchResult(await response.json());
      });
    } catch {
      if (!signal.aborted) this.sessions.invalidate();
      throw new SearchFailed();
    }
  }
}
