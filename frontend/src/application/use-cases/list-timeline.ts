import type { TimelinePage, TimelineQuery } from '../../domain/timeline';
import type { TimelineRepository } from '../ports/timeline-repository';

export class ListTimeline {
  constructor(private readonly repository: TimelineRepository) {}

  execute(query: TimelineQuery, signal: AbortSignal): Promise<TimelinePage> {
    return this.repository.list(query, signal);
  }
}
