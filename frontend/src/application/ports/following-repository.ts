import type { FollowingSnapshot, PersonIdentity } from '../../domain/following';
export interface FollowingRepository {
  list(signal: AbortSignal): Promise<FollowingSnapshot>;
  follow(identity: PersonIdentity, signal: AbortSignal): Promise<FollowingSnapshot>;
}
