import type { PersonIdentity } from '../../domain/following';
import type { FollowingRepository } from '../ports/following-repository';
export class FollowPerson {
  constructor(private readonly repository: FollowingRepository) {}
  execute(identity: PersonIdentity, signal: AbortSignal) { return this.repository.follow(identity, signal); }
}
