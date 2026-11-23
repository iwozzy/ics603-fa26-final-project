import type { FollowingRepository } from '../ports/following-repository';
import type { PersonIdentity } from '../../domain/following';

export class UnfollowPerson {
  constructor(private readonly repository: FollowingRepository) {}
  execute(identity: PersonIdentity, signal: AbortSignal): Promise<void> {
    return this.repository.unfollow(identity, signal);
  }
}
