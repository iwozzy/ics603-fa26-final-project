import type { PersonSummary } from './people';
export type PersonIdentity = Pick<PersonSummary, 'provider' | 'providerId'>;
export interface FollowingSnapshot { readonly people: readonly PersonSummary[]; readonly limit: number; }
export function personKey(person: PersonIdentity): string { return person.provider + ':' + person.providerId; }
