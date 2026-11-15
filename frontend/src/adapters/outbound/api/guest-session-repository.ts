import type { GuestSessionRepository } from '../../../application/ports/guest-session-repository';
import { SearchFailed } from '../../../domain/errors';
import { cancellable, withDeadline } from './transport';

export class HttpGuestSessionRepository implements GuestSessionRepository {
  private ready = false;
  private generation = 0;
  private pending: Promise<void> | undefined;
  constructor(private readonly fetchImpl: typeof fetch) {}

  async ensure(signal: AbortSignal): Promise<void> {
    if (signal.aborted) throw new SearchFailed();
    if (this.ready) return;
    if (!this.pending) {
      const generation = this.generation;
      this.pending = withDeadline(undefined, async sharedSignal => {
        const response = await this.fetchImpl('/api/v1/guest-session', { method: 'POST', credentials: 'same-origin', signal: sharedSignal });
        if (!response.ok) throw new SearchFailed();
        if (generation === this.generation) this.ready = true;
      }).finally(() => { if (generation === this.generation) this.pending = undefined; });
    }
    await cancellable(this.pending, signal);
  }

  invalidate(): void { this.ready = false; this.generation++; this.pending = undefined; }
}
