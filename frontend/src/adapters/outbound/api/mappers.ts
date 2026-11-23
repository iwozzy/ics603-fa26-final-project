import * as z from 'zod';
import type { PersonResponse } from './generated/types.gen';
import { normalizeQuery, type PersonSummary, type SearchResult } from '../../../domain/people';
import { zSearchPeopleResponse } from './generated/zod.gen';

// OpenAPI lengths count code points; JS/Zod string max counts UTF-16 units.
const responseSchema = zSearchPeopleResponse.extend({ query: z.string().refine(value => {
  try { return normalizeQuery(value) === value; } catch { return false; }
}) });

export function mapSearchResult(value: unknown): SearchResult {
  const dto = responseSchema.parse(value);
  return { query: dto.query, people: dto.people.map(mapPerson) };
}

export function mapPerson(person: PersonResponse): PersonSummary {
  return { provider: person.provider, providerId: person.provider_id, name: person.name, knownForDepartment: person.known_for_department, profileImageUrl: person.profile_image_url, knownFor: person.known_for };
}
