import type { FollowingSnapshot, PersonIdentity } from '../../domain/following';
export interface FollowingRepository {
  list(signal: AbortSignal): Promise<FollowingSnapshot>;
  unfollow(identity: PersonIdentity, signal: AbortSignal): Promise<void>;
  follow(identity: PersonIdentity, signal: AbortSignal): Promise<FollowingSnapshot>;
}
