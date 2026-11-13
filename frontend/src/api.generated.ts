/**
 * @maxItems 7
 */
export type Results =
  | []
  | [PersonResponse]
  | [PersonResponse, PersonResponse]
  | [PersonResponse, PersonResponse, PersonResponse]
  | [PersonResponse, PersonResponse, PersonResponse, PersonResponse]
  | [PersonResponse, PersonResponse, PersonResponse, PersonResponse, PersonResponse]
  | [PersonResponse, PersonResponse, PersonResponse, PersonResponse, PersonResponse, PersonResponse]
  | [PersonResponse, PersonResponse, PersonResponse, PersonResponse, PersonResponse, PersonResponse, PersonResponse];
export type Provider = "tmdb";
export type EntityType = "person";
export type Id = string;
export type Name = string;
export type PortraitUrl = string | null;
export type Department = string | null;
/**
 * @maxItems 3
 */
export type KnownFor = [] | [string] | [string, string] | [string, string, string];

export interface SearchResponse {
  results: Results;
}
export interface PersonResponse {
  provider_ref: ProviderRefResponse;
  name: Name;
  portrait_url: PortraitUrl;
  department: Department;
  known_for: KnownFor;
}
export interface ProviderRefResponse {
  provider: Provider;
  entity_type: EntityType;
  id: Id;
}
