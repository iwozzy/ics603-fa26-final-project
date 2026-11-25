import type { GuestSessionRepository } from '../../../application/ports/guest-session-repository';
import { SearchFailed } from '../../../domain/errors';
import { cancellable, withDeadline } from './transport';

export class HttpGuestSessionRepository implements GuestSessionRepository {
  private ready = false;
  private identityVersion = 0;
  private readonly listeners = new Set<(generation: number) => void>();
  get identityGeneration(): number { return this.identityVersion; }
  subscribeIdentityCreated(listener: (generation: number) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }
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
        const created = response.headers.get('X-Lumiere-Guest-Created');
        if (created !== 'true' && created !== 'false') throw new SearchFailed();
        if (generation !== this.generation) throw new SearchFailed();
        this.ready = true;
        if (created === 'true') {
          this.identityVersion++;
          for (const listener of this.listeners) listener(this.identityVersion);
        }
      }).finally(() => { if (generation === this.generation) this.pending = undefined; });
    }
    await cancellable(this.pending, signal);
  }

  invalidate(): void { this.ready = false; this.generation++; this.pending = undefined; }
}
