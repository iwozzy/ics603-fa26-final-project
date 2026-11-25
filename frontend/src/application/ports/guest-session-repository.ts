export interface GuestSessionRepository {
  ensure(signal: AbortSignal): Promise<void>;
  invalidate(): void;
  readonly identityGeneration: number;
  subscribeIdentityCreated(listener: (generation: number) => void): () => void;
}
