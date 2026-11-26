import type { GuestSessionRepository } from '../../../application/ports/guest-session-repository';
import type { TimelineRepository } from '../../../application/ports/timeline-repository';
import { TimelineFailed } from '../../../domain/errors';
import type { TimelinePage, TimelineQuery } from '../../../domain/timeline';
import type { ListTimelineData } from './generated/types.gen';
import { mapTimelinePage } from './timeline-mappers';
import { withDeadline } from './transport';

const timelinePath: ListTimelineData['url'] = '/api/v1/timeline';

function timelineUrl(query: TimelineQuery): string {
  const params: NonNullable<ListTimelineData['query']> = { limit: query.limit };
  if (query.mode === 'page') {
    params.direction = query.direction;
    params.cursor = query.cursor;
  } else if (query.mode === 'anchor') {
    params.anchor_date = query.anchor.releaseDate;
    params.anchor_id = query.anchor.id;
  }
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) search.set(name, String(value));
  }
  const queryString = search.toString();
  return queryString ? `${timelinePath}?${queryString}` : timelinePath;
}

export class HttpTimelineRepository implements TimelineRepository {
  constructor(private readonly fetchImpl: typeof fetch, private readonly sessions: GuestSessionRepository) {}

  async list(query: TimelineQuery, signal: AbortSignal): Promise<TimelinePage> {
    try {
      return await withDeadline(signal, async combined => {
        await this.sessions.ensure(combined);
        if (combined.aborted) throw new TimelineFailed();
        const response = await this.fetchImpl(timelineUrl(query), {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
          signal: combined,
        });
        if (combined.aborted || !response.ok) throw new TimelineFailed();
        return mapTimelinePage(await response.json());
      });
    } catch {
      // The next ordinary read can bootstrap the guest session again.
      if (!signal.aborted) this.sessions.invalidate();
      throw new TimelineFailed();
    }
  }
}
