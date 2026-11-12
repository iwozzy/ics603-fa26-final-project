import type { SearchPeople } from '../../application/search-people';
import type { components } from './generated/api';

type SearchResponse = components['schemas']['SearchResponse'];

class SearchFailure extends Error {
  constructor(readonly kind: 'http' | 'transport' | 'timeout') {
    super('People search failed');
  }
}

export function createPeopleSearch(
  baseUrl: string,
  fetcher: typeof fetch = fetch,
): SearchPeople {
  return async (query) => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const deadline = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        reject(new SearchFailure('timeout'));
        abort.abort();
      }, 12_000);
    });
    try {
      const operation = async () => {
        const response = await fetcher(
          `${baseUrl}/api/people/search?query=${encodeURIComponent(query)}`,
          { signal: abort.signal },
        );
        if (!response.ok) throw new SearchFailure('http');
        const data: SearchResponse = await response.json();
        return data.results.map((person) => ({
          name: person.name,
          portraitUrl: person.portrait_url,
          department: person.department,
          knownFor: person.known_for,
        }));
      };
      return await Promise.race([operation(), deadline]);
    } catch (error) {
      throw error instanceof SearchFailure
        ? error
        : new SearchFailure('transport');
    } finally {
      clearTimeout(timer!);
    }
  };
}
