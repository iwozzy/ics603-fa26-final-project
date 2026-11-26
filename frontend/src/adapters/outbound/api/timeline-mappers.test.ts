import { mapTimelinePage } from './timeline-mappers';

const movie = {
  id: Number.MAX_SAFE_INTEGER,
  title: 'Bullet Train',
  overview: null,
  poster_image_url: null,
  release_date: '2022-08-03',
};
const validPage = {
  items: [movie],
  older_cursor: null,
  newer_cursor: 'future-boundary',
  as_of: '2026-11-26',
  anchor_index: null,
};

test('maps the initial timeline page and preserves numeric IDs and calendar strings', () => {
  expect(mapTimelinePage(validPage)).toEqual({
    items: [{
      id: Number.MAX_SAFE_INTEGER,
      title: 'Bullet Train',
      overview: null,
      posterImageUrl: null,
      releaseDate: '2022-08-03',
    }],
    olderCursor: null,
    newerCursor: 'future-boundary',
    asOf: '2026-11-26',
    anchorIndex: null,
  });
});

test('maps nonnull movie fields and the first anchored index', () => {
  expect(mapTimelinePage({
    ...validPage,
    items: [{
      ...movie,
      id: 1,
      overview: 'A trip to Kyoto.',
      poster_image_url: 'https://images.example.test/train.jpg',
      release_date: '2000-02-29',
    }],
    older_cursor: 'older-edge',
    newer_cursor: null,
    anchor_index: 0,
  })).toEqual({
    items: [{
      id: 1,
      title: 'Bullet Train',
      overview: 'A trip to Kyoto.',
      posterImageUrl: 'https://images.example.test/train.jpg',
      releaseDate: '2000-02-29',
    }],
    olderCursor: 'older-edge',
    newerCursor: null,
    asOf: '2026-11-26',
    anchorIndex: 0,
  });
});

test.each(['123', true, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1])('rejects invalid movie ID %p', id => {
  expect(() => mapTimelinePage({ ...validPage, items: [{ ...movie, id }] })).toThrow();
});

test.each(['2023-02-29', '1900-02-29', '2026-04-31', '0000-01-01', '2026-11-26T00:00:00Z'])(
  'rejects invalid calendar date %s for both movie releases and the timeline boundary',
  date => {
    expect(() => mapTimelinePage({ ...validPage, items: [{ ...movie, release_date: date }] })).toThrow();
    expect(() => mapTimelinePage({ ...validPage, as_of: date })).toThrow();
  },
);
