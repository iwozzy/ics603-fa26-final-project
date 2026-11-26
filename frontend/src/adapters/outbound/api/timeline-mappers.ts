import type { TimelinePage } from '../../../domain/timeline';
import { zTimelineResponse } from './generated/zod.gen';

function calendarDate(date: string): string {
  // The API's calendar date range starts at year 0001.
  if (date.startsWith('0000-')) throw new RangeError('Timeline dates must have a positive year');
  return date;
}

export function mapTimelinePage(value: unknown): TimelinePage {
  const dto = zTimelineResponse.parse(value);
  return {
    items: dto.items.map(movie => ({
      id: movie.id,
      title: movie.title,
      overview: movie.overview,
      posterImageUrl: movie.poster_image_url,
      releaseDate: calendarDate(movie.release_date),
    })),
    olderCursor: dto.older_cursor,
    newerCursor: dto.newer_cursor,
    asOf: dto.as_of === null ? null : calendarDate(dto.as_of),
    anchorIndex: dto.anchor_index,
  };
}
