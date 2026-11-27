import type { TimelineRepository } from '../../application/ports/timeline-repository';
import type { TimelinePage, TimelineQuery } from '../../domain/timeline';

interface TimelineCall {
  query: TimelineQuery;
  signal: AbortSignal;
  resolve(value: TimelinePage): void;
  reject(error: Error): void;
}

export class DeferredTimeline implements TimelineRepository {
  readonly calls: TimelineCall[] = [];

  list(query: TimelineQuery, signal: AbortSignal): Promise<TimelinePage> {
    return new Promise((resolve, reject) => {
      this.calls.push({ query, signal, resolve, reject });
    });
  }
}
