import { InvalidQuery } from './errors';

export interface PersonSummary { readonly name: string; readonly department: string | null; readonly profileImageUrl: string | null; readonly knownFor: readonly string[]; }
export interface SearchResult { readonly query: string; readonly people: readonly PersonSummary[]; }
export function normalizeQuery(raw: string): string { const query = raw.trim(); if (Array.from(query).length < 1 || Array.from(query).length > 200) throw new InvalidQuery(); return query; }
