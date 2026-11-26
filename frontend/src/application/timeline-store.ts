import type { MovieSummary, TimelineAnchor, TimelinePage, TimelineQuery } from '../domain/timeline';
import type { GuestSessionRepository } from './ports/guest-session-repository';
import type { ListTimeline } from './use-cases/list-timeline';

export interface TimelineViewState {
  readonly items: readonly MovieSummary[];
  readonly olderCursor: string | null;
  readonly newerCursor: string | null;
  readonly asOf: string | null;
  readonly anchor: TimelineAnchor | null;
  readonly phase: 'idle' | 'loading' | 'ready' | 'failed';
  readonly fetchingOlder: boolean;
  readonly fetchingNewer: boolean;
  readonly restoration: { readonly revision: number; readonly anchor: TimelineAnchor | null } | null;
}

export const initialTimelineState: TimelineViewState = {
  items: [],
  olderCursor: null,
  newerCursor: null,
  asOf: null,
  anchor: null,
  phase: 'idle',
  fetchingOlder: false,
  fetchingNewer: false,
  restoration: null,
};

type Direction = 'older' | 'newer';

interface TimelineRead {
  readonly controller: AbortController;
  readonly generation: number;
  readonly windowRevision: number;
}

function orderedMovies(pages: readonly TimelinePage[]): MovieSummary[] {
  // Apply pages in completion order so the latest copy wins when a movie changes date.
  const movies = new Map<number, MovieSummary>();
  for (const page of pages) {
    for (const movie of page.items) movies.set(movie.id, movie);
  }
  return [...movies.values()].sort((left, right) => {
    if (left.releaseDate === right.releaseDate) return right.id - left.id;
    return left.releaseDate > right.releaseDate ? -1 : 1;
  });
}

function locateAnchor(items: readonly MovieSummary[], previous: TimelineAnchor): TimelineAnchor | null {
  const movie = items.find(item => item.id === previous.id);
  return movie ? { id: movie.id, releaseDate: movie.releaseDate, offset: previous.offset } : null;
}

function refreshedAnchor(page: TimelinePage, previous: TimelineAnchor): TimelineAnchor | null {
  const surviving = locateAnchor(page.items, previous);
  if (surviving) return surviving;
  const fallback = page.anchorIndex === null ? page.items.at(-1) : page.items[page.anchorIndex];
  return fallback ? { id: fallback.id, releaseDate: fallback.releaseDate, offset: 0 } : null;
}

export class TimelineStore {
  private state = initialTimelineState;
  private readonly listeners = new Set<() => void>();
  private pages: TimelinePage[] = [];
  private identityGeneration: number;
  private unsubscribeIdentity?: () => void;
  private visible = false;
  private windowRevision = 0;
  private restorationRevision = 0;
  private scrollReplacement: 'none' | 'pending' | 'used' = 'none';
  private refreshRead?: TimelineRead & { anchor: TimelineAnchor | null };
  private pagingReads: Partial<Record<Direction, TimelineRead>> = {};

  constructor(private readonly list: ListTimeline, private readonly sessions: GuestSessionRepository) {
    this.identityGeneration = sessions.identityGeneration;
  }

  getSnapshot = (): TimelineViewState =>
    this.identityGeneration === this.sessions.identityGeneration ? this.state : initialTimelineState;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  start(): void {
    if (this.unsubscribeIdentity) return;
    this.unsubscribeIdentity = this.sessions.subscribeIdentityCreated(generation => this.resetIdentity(generation));
    if (this.identityGeneration !== this.sessions.identityGeneration) {
      this.resetIdentity(this.sessions.identityGeneration);
    }
  }

  stop(): void {
    this.unsubscribeIdentity?.();
    this.unsubscribeIdentity = undefined;
    this.leave(this.state.anchor);
  }

  async enter(): Promise<void> {
    // A route can enter before its provider's effect starts the store.
    this.start();
    if (this.visible) return;
    this.visible = true;
    const anchor = this.state.items.length ? this.state.anchor : null;
    await this.refresh(anchor, anchor ? this.nextRestoration(anchor) : null);
  }

  leave(anchor: TimelineAnchor | null): void {
    if (!this.visible) return;
    this.visible = false;
    this.scrollReplacement = 'none';
    this.cancelReads();
    this.publish({
      anchor: anchor && (locateAnchor(this.state.items, anchor) ?? this.state.anchor),
      phase: this.pages.length ? 'ready' : 'idle',
      fetchingOlder: false,
      fetchingNewer: false,
      restoration: null,
    });
  }

  rememberAnchor(measurement: TimelineAnchor | null, userMoved = false): void {
    if (!this.visible) return;
    const anchor = measurement && locateAnchor(this.state.items, measurement);
    // A measurement can arrive after the rows have been replaced or the guest has changed.
    if (measurement && !anchor) return;
    if (userMoved && this.refreshRead?.anchor) {
      this.cancelReads();
      if (this.scrollReplacement === 'none') this.scrollReplacement = 'pending';
      this.publish({ anchor, phase: 'ready', restoration: null });
      return;
    }

    const current = this.state.anchor;
    const sameAnchor = current?.id === anchor?.id && current?.releaseDate === anchor?.releaseDate
      && current?.offset === anchor?.offset;
    if (sameAnchor && (!userMoved || !this.state.restoration)) return;
    this.publish({ anchor, restoration: userMoved ? null : this.state.restoration });
  }

  async settleScroll(): Promise<void> {
    if (!this.visible || this.scrollReplacement !== 'pending' || !this.state.anchor) return;
    this.scrollReplacement = 'used';
    await this.refresh(this.state.anchor, this.state.restoration);
  }

  async load(direction: Direction): Promise<void> {
    if (!this.visible || this.refreshRead || this.pagingReads[direction]) return;
    const edge = direction === 'older' ? 'olderCursor' : 'newerCursor';
    const fetching = direction === 'older' ? 'fetchingOlder' : 'fetchingNewer';
    const cursor = this.state[edge];
    if (cursor === null) return;

    const read = this.createRead();
    this.pagingReads[direction] = read;
    const current = () => this.isCurrent(read) && this.pagingReads[direction] === read && this.state[edge] === cursor;
    this.publish({ [fetching]: true });
    if (!current()) return;

    let page: TimelinePage;
    try {
      page = await this.list.execute({ mode: 'page', direction, cursor }, read.controller.signal);
    } catch {
      if (current()) {
        delete this.pagingReads[direction];
        this.publish({ [fetching]: false });
      }
      return;
    }
    if (!current()) return;

    delete this.pagingReads[direction];
    this.pages.push(page);
    const items = orderedMovies(this.pages);
    const anchor = this.state.anchor && locateAnchor(items, this.state.anchor);
    const restoration = direction === 'newer' && page.items.length && anchor
      ? this.nextRestoration(anchor)
      : this.state.restoration;
    this.publish({ items, anchor, restoration, [edge]: page[edge], [fetching]: false });
  }

  private async refresh(anchor: TimelineAnchor | null, restoration: TimelineViewState['restoration']): Promise<void> {
    this.cancelReads();
    const read = { ...this.createRead(), anchor };
    this.refreshRead = read;
    const current = () => this.isCurrent(read) && this.refreshRead === read;
    this.publish({ phase: 'loading', restoration, fetchingOlder: false, fetchingNewer: false });
    if (!current()) return;

    let page: TimelinePage;
    try {
      const query: TimelineQuery = anchor
        ? { mode: 'anchor', anchor: { releaseDate: anchor.releaseDate, id: anchor.id } }
        : { mode: 'initial' };
      page = await this.list.execute(query, read.controller.signal);
    } catch {
      if (current()) {
        this.refreshRead = undefined;
        this.publish({ phase: 'failed' });
      }
      return;
    }
    if (!current()) return;

    this.refreshRead = undefined;
    this.pages = [page];
    const nextAnchor = anchor && refreshedAnchor(page, anchor);
    this.publish({
      items: orderedMovies(this.pages),
      olderCursor: page.olderCursor,
      newerCursor: page.newerCursor,
      asOf: page.asOf,
      phase: 'ready',
      anchor: nextAnchor,
      restoration: anchor ? this.nextRestoration(nextAnchor) : null,
    });
  }

  private resetIdentity(generation: number): void {
    this.cancelReads();
    this.identityGeneration = generation;
    this.pages = [];
    this.scrollReplacement = 'none';
    this.publish(initialTimelineState);
    if (this.visible && !this.refreshRead) void this.refresh(null, null);
  }

  private createRead(): TimelineRead {
    return {
      controller: new AbortController(),
      generation: this.identityGeneration,
      windowRevision: this.windowRevision,
    };
  }

  private isCurrent(read: TimelineRead): boolean {
    return this.visible && !read.controller.signal.aborted
      && this.sessions.identityGeneration === read.generation && this.windowRevision === read.windowRevision;
  }

  private cancelReads(): void {
    this.windowRevision++;
    const reads = [this.refreshRead, this.pagingReads.older, this.pagingReads.newer];
    this.refreshRead = undefined;
    this.pagingReads = {};
    for (const read of reads) read?.controller.abort();
  }

  private nextRestoration(anchor: TimelineAnchor | null): NonNullable<TimelineViewState['restoration']> {
    return { revision: ++this.restorationRevision, anchor };
  }

  private publish(changes: Partial<TimelineViewState>): void {
    this.state = changes === initialTimelineState ? initialTimelineState : { ...this.state, ...changes };
    for (const listener of this.listeners) listener();
  }
}
