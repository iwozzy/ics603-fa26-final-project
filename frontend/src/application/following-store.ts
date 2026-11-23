import { personKey, type FollowingSnapshot } from '../domain/following';
import type { PersonSummary } from '../domain/people';
import type { GuestSessionRepository } from './ports/guest-session-repository';
import type { FollowPerson } from './use-cases/follow-person';
import type { ListFollowing } from './use-cases/list-following';

export interface FollowingViewState {
  readonly confirmed: FollowingSnapshot | null;
  readonly pending: readonly PersonSummary[];
  readonly people: readonly PersonSummary[];
  readonly phase: 'idle' | 'loading' | 'ready' | 'failed';
  readonly canFollow: boolean;
}
export const initialFollowingState: FollowingViewState = { confirmed: null, pending: [], people: [], phase: 'idle', canFollow: false };

export class FollowingStore {
  private state = initialFollowingState;
  private readonly listeners = new Set<() => void>();
  private active = false;
  private epoch = 0;
  private revision = 0;
  private unsubscribeIdentity?: () => void;
  private reading?: { controller: AbortController; promise: Promise<void> };
  private sending?: { controller: AbortController; epoch: number };
  private queue: PersonSummary[] = [];
  constructor(private readonly list: ListFollowing, private readonly follow: FollowPerson, private readonly sessions: GuestSessionRepository) {}
  getSnapshot = (): FollowingViewState => this.state;
  subscribe = (listener: () => void): (() => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };

  start(): void {
    if (this.active) return;
    this.active = true;
    this.unsubscribeIdentity = this.sessions.subscribeIdentityCreated(() => {
      this.abandon();
      this.publish(null, [], 'idle');
      void this.refresh();
    });
    void this.refresh();
  }
  stop(): void {
    this.active = false;
    this.unsubscribeIdentity?.(); this.unsubscribeIdentity = undefined;
    this.abandon();
    this.publish(this.state.confirmed, [], this.state.confirmed ? 'ready' : 'idle');
  }
  private abandon(): void {
    this.epoch++;
    this.revision++;
    this.reading?.controller.abort(); this.reading = undefined;
    this.sending?.controller.abort(); this.sending = undefined;
    this.queue = [];
  }
  refresh = (): Promise<void> => {
    if (!this.active) return Promise.resolve();
    if (this.reading) return this.reading.promise;
    const epoch = this.epoch, revision = this.revision;
    const generation = this.sessions.identityGeneration;
    const controller = new AbortController();
    this.publish(this.state.confirmed, this.state.pending, 'loading');
    const current = () => this.active && !controller.signal.aborted && this.epoch === epoch && this.sessions.identityGeneration === generation;
    const promise = this.list.execute(controller.signal).then(snapshot => {
      if (current() && revision === this.revision) this.publish(snapshot, this.state.pending, 'ready');
    }, () => {
      if (current() && revision === this.revision) this.publish(this.state.confirmed, this.state.pending, 'failed');
    }).finally(() => {
      if (this.reading?.controller === controller) {
        this.reading = undefined;
        // An obsolete read must settle loading without changing confirmed data.
        if (current() && this.state.phase === 'loading') this.publish(this.state.confirmed, this.state.pending, this.state.confirmed ? 'ready' : 'failed');
      }
    });
    this.reading = { controller, promise };
    return promise;
  };
  requestFollow = (person: PersonSummary): boolean => {
    if (!this.active || !this.state.canFollow || this.state.people.some(p => personKey(p) === personKey(person))) return false;
    this.revision++;
    this.queue.push(person);
    this.publish(this.state.confirmed, [...this.state.pending, person], this.state.phase);
    void this.sendNext();
    return true;
  };
  private async sendNext(): Promise<void> {
    if (!this.active || this.sending || !this.queue.length) return;
    const person = this.queue.shift()!;
    const epoch = this.epoch, generation = this.sessions.identityGeneration;
    const controller = new AbortController();
    const sending = { controller, epoch };
    this.sending = sending;
    const current = () => this.active && this.epoch === epoch && this.sessions.identityGeneration === generation && !controller.signal.aborted;
    try {
      await this.sessions.ensure(controller.signal);
      if (!current()) return;
      const snapshot = await this.follow.execute(person, controller.signal);
      if (current()) {
        this.revision++;
        this.publish(snapshot, this.state.pending.filter(p => personKey(p) !== personKey(person)), 'ready');
      }
    } catch {
      if (current()) {
        this.revision++;
        this.publish(this.state.confirmed, this.state.pending.filter(p => personKey(p) !== personKey(person)), this.state.confirmed ? 'ready' : 'failed');
      }
    } finally {
      if (this.sending === sending) { this.sending = undefined; void this.sendNext(); }
    }
  }
  private publish(confirmed: FollowingSnapshot | null, pending: readonly PersonSummary[], phase: FollowingViewState['phase']): void {
    const merged = new Map<string, PersonSummary>();
    for (const person of [...pending].reverse()) merged.set(personKey(person), person);
    for (const person of confirmed?.people ?? []) if (!merged.has(personKey(person))) merged.set(personKey(person), person);
    const people = [...merged.values()];
    this.state = { confirmed, pending, people, phase, canFollow: confirmed !== null && people.length < confirmed.limit };
    for (const listener of this.listeners) listener();
  }
}
