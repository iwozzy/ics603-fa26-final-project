import { personKey, type FollowingSnapshot } from '../domain/following';
import type { PersonSummary } from '../domain/people';
import type { GuestSessionRepository } from './ports/guest-session-repository';
import type { FollowPerson } from './use-cases/follow-person';
import type { ListFollowing } from './use-cases/list-following';
import type { UnfollowPerson } from './use-cases/unfollow-person';

interface FollowingIntent { readonly id: number; readonly kind: 'follow' | 'unfollow'; readonly person: PersonSummary; }

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
  private identityGeneration: number;
  private unsubscribeIdentity?: () => void;
  private reading?: { controller: AbortController; promise: Promise<void>; revision: number };
  private sending?: { controller: AbortController; epoch: number };
  private intents: FollowingIntent[] = [];
  private nextIntentId = 0;
  constructor(private readonly list: ListFollowing, private readonly follow: FollowPerson, private readonly unfollow: UnfollowPerson, private readonly sessions: GuestSessionRepository) { this.identityGeneration = sessions.identityGeneration; }
  getSnapshot = (): FollowingViewState => this.state;
  subscribe = (listener: () => void): (() => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };

  start(): void {
    if (this.active) return;
    if (this.identityGeneration !== this.sessions.identityGeneration) {
      this.identityGeneration = this.sessions.identityGeneration;
      this.abandon();
      this.publish(null, 'idle');
    }
    this.active = true;
    this.unsubscribeIdentity = this.sessions.subscribeIdentityCreated(generation => {
      this.identityGeneration = generation;
      this.abandon();
      this.publish(null, 'idle');
      void this.refresh();
    });
    void this.refresh();
  }
  stop(): void {
    this.active = false;
    this.unsubscribeIdentity?.(); this.unsubscribeIdentity = undefined;
    this.abandon();
    this.publish(this.state.confirmed, this.state.confirmed ? 'ready' : 'idle');
  }
  private abandon(): void {
    this.epoch++;
    this.revision++;
    this.reading?.controller.abort(); this.reading = undefined;
    this.sending?.controller.abort(); this.sending = undefined;
    this.intents = [];
  }
  refresh = (): Promise<void> => {
    if (!this.active) return Promise.resolve();
    if (this.reading?.revision === this.revision) return this.reading.promise;
    this.reading?.controller.abort();
    this.reading = undefined;
    const epoch = this.epoch, revision = this.revision;
    const generation = this.sessions.identityGeneration;
    const controller = new AbortController();
    this.publish(this.state.confirmed, 'loading');
    const current = () => this.active && !controller.signal.aborted && this.epoch === epoch && this.sessions.identityGeneration === generation;
    const promise = this.list.execute(controller.signal).then(snapshot => {
      if (current() && revision === this.revision) this.publish(snapshot, 'ready');
    }, () => {
      if (current() && revision === this.revision) this.publish(this.state.confirmed, 'failed');
    }).finally(() => {
      if (this.reading?.controller === controller) {
        this.reading = undefined;
        // An obsolete read must settle loading without changing confirmed data.
        if (current() && this.state.phase === 'loading') this.publish(this.state.confirmed, this.state.confirmed ? 'ready' : 'failed');
      }
    });
    this.reading = { controller, promise, revision };
    return promise;
  };
  requestFollow = (person: PersonSummary): boolean => {
    if (!this.active || !this.state.canFollow || this.state.people.some(p => personKey(p) === personKey(person))) return false;
    return this.accept('follow', person);
  };
  requestUnfollow = (person: PersonSummary): boolean => {
    if (!this.active || !this.state.confirmed || !this.state.people.some(p => personKey(p) === personKey(person))) return false;
    return this.accept('unfollow', person);
  };
  private accept(kind: FollowingIntent['kind'], person: PersonSummary): boolean {
    this.revision++;
    this.intents.push({ id: this.nextIntentId++, kind, person });
    this.publish(this.state.confirmed, this.state.phase);
    void this.sendNext();
    return true;
  }
  private async sendNext(): Promise<void> {
    if (!this.active || this.sending || !this.intents.length) return;
    const intent = this.intents[0];
    const epoch = this.epoch, generation = this.sessions.identityGeneration;
    const controller = new AbortController();
    const sending = { controller, epoch };
    this.sending = sending;
    const current = () => this.active && this.epoch === epoch && this.sessions.identityGeneration === generation && !controller.signal.aborted;
    try {
      await this.sessions.ensure(controller.signal);
      if (!current()) return;
      let confirmed: FollowingSnapshot | null;
      if (intent.kind === 'follow') {
        confirmed = await this.follow.execute(intent.person, controller.signal);
      } else {
        await this.unfollow.execute(intent.person, controller.signal);
        const previous = this.state.confirmed;
        confirmed = previous && { ...previous, people: previous.people.filter(p => personKey(p) !== personKey(intent.person)) };
      }
      if (current()) this.settle(intent.id, confirmed);
    } catch {
      if (current()) this.settle(intent.id, this.state.confirmed);
    } finally {
      if (this.sending === sending) { this.sending = undefined; void this.sendNext(); }
    }
  }
  private settle(id: number, confirmed: FollowingSnapshot | null): void {
    this.revision++;
    this.intents = this.intents.filter(intent => intent.id !== id);
    this.publish(confirmed, confirmed ? 'ready' : 'failed');
  }
  private publish(confirmed: FollowingSnapshot | null, phase: FollowingViewState['phase']): void {
    let people = [...(confirmed?.people ?? [])];
    const additions = new Map<string, PersonSummary>();
    for (const intent of this.intents) {
      const key = personKey(intent.person);
      if (intent.kind === 'unfollow') {
        people = people.filter(p => personKey(p) !== key);
        additions.delete(key);
      } else {
        if (!people.some(p => personKey(p) === key)) people.unshift(intent.person);
        additions.set(key, intent.person);
      }
    }
    const pending = [...additions.values()];
    this.state = { confirmed, pending, people, phase, canFollow: confirmed !== null && people.length < confirmed.limit };
    for (const listener of this.listeners) listener();
  }
}
