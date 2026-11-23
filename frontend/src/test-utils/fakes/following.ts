import type { FollowingRepository } from '../../application/ports/following-repository';
import type { GuestSessionRepository } from '../../application/ports/guest-session-repository';
import type { FollowingSnapshot, PersonIdentity } from '../../domain/following';
import type { PersonSummary } from '../../domain/people';
export const person = (providerId = 4139): PersonSummary => ({ provider: 'tmdb', providerId, name: 'Person ' + providerId, knownForDepartment: null, profileImageUrl: null, knownFor: [] });
export const snapshot = (...ids: number[]): FollowingSnapshot => ({ people: ids.map(person), limit: 3 });
interface Deferred { signal: AbortSignal; resolve(value: FollowingSnapshot): void; reject(error: Error): void; }
export class DeferredFollowing implements FollowingRepository {
  readonly listCalls: Deferred[] = [];
  readonly followCalls: (Deferred & { identity: PersonIdentity })[] = [];
  list(signal: AbortSignal): Promise<FollowingSnapshot> { return new Promise((resolve, reject) => this.listCalls.push({ signal, resolve, reject })); }
  follow(identity: PersonIdentity, signal: AbortSignal): Promise<FollowingSnapshot> { return new Promise((resolve, reject) => this.followCalls.push({ identity, signal, resolve, reject })); }
}
export class FakeSessions implements GuestSessionRepository {
  identityGeneration = 0;
  private readonly listeners = new Set<(generation: number) => void>();
  ensureImpl: (signal: AbortSignal) => Promise<void> = async () => {};
  ensure(signal: AbortSignal): Promise<void> { return this.ensureImpl(signal); }
  invalidate(): void {}
  subscribeIdentityCreated(listener: (generation: number) => void): () => void { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  createGuest(): void { this.identityGeneration++; for (const listener of this.listeners) listener(this.identityGeneration); }
}
