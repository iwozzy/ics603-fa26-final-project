import Ajv from 'ajv';
import type { SearchResponse } from '../api.generated';
import schema from '../api.schema.json';
import type { PeopleSearch } from './workflow';

const validate = new Ajv({ strict: false }).compile<SearchResponse>(schema);

export const httpPeopleSearch: PeopleSearch = {
  start(name) {
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 8000);
    const result = (async () => {
      try {
        const response = await fetch(
          `/api/people/search?query=${encodeURIComponent(name)}`,
          {
            signal: controller.signal,
            // Keep default browser HTTP caching; no application query cache.
          },
        );
        if (!response.ok) throw new Error('Search unavailable');
        const body: unknown = await response.json();
        if (!validate(body)) throw new Error('Invalid search response');
        const ids = body.results.map(
          (row) =>
            `${row.provider_ref.provider}/${row.provider_ref.entity_type}/${row.provider_ref.id}`,
        );
        if (new Set(ids).size !== ids.length)
          throw new Error('Invalid search response');
        return body.results.map((person) => ({
          providerRef: {
            provider: person.provider_ref.provider,
            entityType: person.provider_ref.entity_type,
            id: person.provider_ref.id,
          },
          name: person.name,
          portraitUrl: person.portrait_url,
          department: person.department,
          knownFor: [...person.known_for],
        }));
      } finally {
        clearTimeout(deadline);
      }
    })();
    return { result, cancel: () => controller.abort() };
  },
};
