import type { FollowingRepository } from '../../../application/ports/following-repository';
import type { GuestSessionRepository } from '../../../application/ports/guest-session-repository';
import { FollowingFailed } from '../../../domain/errors';
import type { FollowingSnapshot, PersonIdentity } from '../../../domain/following';
import { zFollowPersonRequest } from './generated/zod.gen';
import { mapFollowingSnapshot } from './following-mappers';
import { withDeadline } from './transport';

export class HttpFollowingRepository implements FollowingRepository {
  constructor(private readonly fetchImpl: typeof fetch, private readonly sessions: GuestSessionRepository) {}
  async list(signal: AbortSignal): Promise<FollowingSnapshot> {
    try { return await this.request(signal, { method: 'GET', cache: 'no-store' }); }
    catch {
      // The next ordinary read can bootstrap a missing cookie; this read does not retry.
      if (!signal.aborted) this.sessions.invalidate();
      throw new FollowingFailed();
    }
  }
  async follow(identity: PersonIdentity, signal: AbortSignal): Promise<FollowingSnapshot> {
    try {
      const body = zFollowPersonRequest.parse({ provider: identity.provider, provider_id: identity.providerId });
      return await this.request(signal, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    } catch { throw new FollowingFailed(); }
  }
  private async request(signal: AbortSignal, init: RequestInit): Promise<FollowingSnapshot> {
    try {
      return await withDeadline(signal, async combined => {
        await this.sessions.ensure(combined);
        if (combined.aborted) throw new FollowingFailed();
        const response = await this.fetchImpl('/api/v1/following', { ...init, credentials: 'same-origin', signal: combined });
        if (!response.ok) throw new FollowingFailed();
        return mapFollowingSnapshot(await response.json());
      });
    } catch { throw new FollowingFailed(); }
  }
}
