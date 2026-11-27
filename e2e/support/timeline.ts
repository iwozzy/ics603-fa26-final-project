import { expect, type Locator, type Page } from '@playwright/test';

export const fixtureUrl = 'http://127.0.0.1:18081';
export const timelinePath = '/api/v1/timeline';
export const region = (page: Page) => page.getByRole('region', { name: 'Movie timeline' });
export const nav = (page: Page, name: 'Search' | 'Following' | 'Timeline') => page.getByRole('link', { name, exact: true });
export const movieRow = (page: Page, id: number) => page.getByTestId('timeline-row-' + id);
export interface Movie { id: number; title: string; release_date: string; overview: string | null; poster_path: string | null }

export function movies(base: number, past: number, future: number): Movie[] {
  return Array.from({ length: past + future }, (_, index) => {
    const year = index < past ? 2000 : 2099;
    const day = String(1 + Math.floor((index < past ? index : index - past) / 3)).padStart(2, '0');
    return {
      id: base + index, title: 'Film ' + (base + index), release_date: year + '-08-' + day,
      overview: index % 5 === 1 ? null : ('Scene ' + index + ' in a coastal town. ').repeat(4 + 10 * (index % 5)).trim(),
      poster_path: index % 3 === 0 ? null : '/timeline-' + (base + index) + '.png',
    };
  });
}

export function filmography(id: number, films: Movie[], delayMs = 0) {
  const cast = films.map(film => ({ ...film, character: 'Visitor', credit_id: id + '-cast-' + film.id }));
  const crew = films.slice(0, 1).flatMap(film => ['Writer', 'Director'].map(job => ({
    ...film, job, department: 'Production', credit_id: id + '-' + job + '-' + film.id,
  })));
  return { body: { id, name: 'Fixture person ' + id, movie_credits: { cast, crew } }, delayMs };
}

export async function prepare(page: Page, fixtures: Record<number, ReturnType<typeof filmography>>) {
  expect((await page.request.post(fixtureUrl + '/__control', { data: { scenarios: { Tom: { personIds: Object.keys(fixtures).map(Number) } }, filmographies: fixtures } })).ok()).toBe(true);
  expect((await page.request.post('/api/v1/guest-session')).ok()).toBe(true);
  expect((await page.request.get('/api/v1/people/search?query=Tom')).ok()).toBe(true);
}

export async function follow(page: Page, id: number) {
  // The search writer commits independently. Every retry represents an explicit follow attempt.
  for (let attempt = 1; attempt <= 5; attempt++) {
    const result = await page.request.post('/api/v1/following', { data: { provider: 'tmdb', provider_id: id } });
    if (result.status() === 200) return;
    expect(result.status()).toBe(500);
    if (attempt < 5) await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('Person was absent after five follow attempts');
}

export interface TimelineMovie { id: number; title: string; release_date: string }
interface InitialPage { items: TimelineMovie[]; newer_cursor: string | null }

export async function hydrated(page: Page, completions: number, expectedPast: number, hasFuture: boolean) {
  await expect.poll(async () => (await (await page.request.get(fixtureUrl + '/__counts')).json()).filmographyCompleted)
    .toBe(completions);
  let snapshot!: InitialPage;
  await expect.poll(async () => {
    const response = await page.request.get(timelinePath + '?limit=100');
    expect(response.status()).toBe(200);
    snapshot = await response.json();
    return [snapshot.items.length, Boolean(snapshot.newer_cursor)];
  }).toEqual([expectedPast, hasFuture]);
  return snapshot.items;
}

export function timelineReads(page: Page) {
  const reads: URLSearchParams[] = [];
  page.on('request', req => {
    const url = new URL(req.url());
    if (url.pathname === timelinePath) reads.push(url.searchParams);
  });
  return reads;
}

export async function enter(page: Page, navigate: () => Promise<unknown> = () => page.goto('/timeline')) {
  const [response] = await Promise.all([page.waitForResponse(r => new URL(r.url()).pathname === timelinePath, { timeout: 5000 }), navigate()]);
  expect(response.status()).toBe(200);
  await response.finished();
  await expect(region(page)).toBeVisible();
  await settledLayout(page);
}

export function gate() {
  let release!: () => void;
  const wait = new Promise<void>(resolve => { release = resolve; });
  return { wait, release };
}

// Wait through FlatList batching, the 160 ms gesture settlement and several layout frames.
// A single lucky frame during a jump cannot satisfy the pixel assertion.
export async function settledLayout(page: Page) {
  await page.waitForTimeout(250);
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

export async function topOf(locator: Locator) {
  const rect = await locator.boundingBox();
  expect(rect).not.toBeNull();
  return rect!.y;
}

export async function visibleAnchor(page: Page) {
  const bounds = await region(page).boundingBox();
  const rows = await region(page).getByTestId(/^timeline-row-/).evaluateAll(nodes =>
    nodes.map(node => ({ id: Number(node.getAttribute('data-testid')!.slice('timeline-row-'.length)),
      y: node.getBoundingClientRect().top, bottom: node.getBoundingClientRect().bottom })));
  const first = rows.filter(row => row.bottom > bounds!.y && row.y < bounds!.y + bounds!.height)
    .sort((a, b) => a.y - b.y)[0];
  expect(first, 'first visible movie').toBeDefined();
  return { id: first.id, y: first.y };
}

export async function staysAt(page: Page, id: number, y: number) {
  await settledLayout(page);
  for (let sample = 0; sample < 3; sample++) {
    expect(Math.abs(await topOf(movieRow(page, id)) - y), 'settled movie ' + id + ' Y relative to ' + y).toBeLessThanOrEqual(2);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
  }
}

export async function posters(page: Page, hold?: Promise<void>) {
  let started = 0, completed = 0;
  // The test ingress normally blocks external images. Only the timeline tests bypass its
  // CSP, with the image origin intercepted before navigation and fulfilled entirely here.
  await page.route('https://image.tmdb.org/**', async route => {
    if (new URL(route.request().url()).pathname.includes('/timeline-')) {
      started++;
      await hold;
      completed++;
    }
    await route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="112" height="160"><rect width="112" height="160" fill="gray"/></svg>' });
  });
  return { started: () => started, completed: () => completed };
}

export async function wheel(page: Page, dy: number) {
  await region(page).hover();
  await page.mouse.wheel(0, dy);
}
