import type { TimelinePage, TimelineQuery } from '../../domain/timeline';

export interface TimelineRepository {
  list(query: TimelineQuery, signal: AbortSignal): Promise<TimelinePage>;
}
