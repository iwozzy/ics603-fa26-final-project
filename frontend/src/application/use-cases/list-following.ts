import type { FollowingRepository } from '../ports/following-repository';
export class ListFollowing {
  constructor(private readonly repository: FollowingRepository) {}
  execute(signal: AbortSignal) { return this.repository.list(signal); }
}
