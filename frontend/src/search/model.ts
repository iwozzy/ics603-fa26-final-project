/** Transient recognition data owned by the client search workflow. */
export interface ProviderRef {
  provider: string;
  entityType: string;
  id: string;
}

export interface SearchPerson {
  providerRef: ProviderRef;
  name: string;
  portraitUrl: string | null;
  department: string | null;
  knownFor: string[];
}
