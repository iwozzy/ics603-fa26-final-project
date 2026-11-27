import { expect, test } from '@playwright/test';

import {
  enter, filmography, fixtureUrl, follow, gate, hydrated, movieRow, movies, nav, posters, prepare,
  region, settledLayout, staysAt, timelineReads, topOf, visibleAnchor, wheel,
} from '../support/timeline.ts';

test.use({ bypassCSP: true });

test('filmography fixture counts completed person reads independently of search', async ({ request }) => {
  await request.post(fixtureUrl + '/__control', {
    data: { filmographies: { 17: { status: 429, retryAfter: '71', body: { limited: true } } } },
  });
  const limited = await request.get(fixtureUrl + '/3/person/17?append_to_response=movie_credits');
  expect(limited.status()).toBe(429);
  expect(limited.headers()['retry-after']).toBe('71');
  expect(await limited.json()).toEqual({ limited: true });
  const missing = await request.get(fixtureUrl + '/3/person/18?append_to_response=movie_credits');
  expect(missing.status()).toBe(404);
  expect(await (await request.get(fixtureUrl + '/__counts')).json()).toMatchObject({
    total: 0, completed: 0, byQuery: {}, filmographyTotal: 2, filmographyCompleted: 2, byPerson: { 17: 1, 18: 1 },
  });
});

test('delayed hydration appears on return, with one movie for two people and three roles', async ({ page }) => {
  const first = 126471, second = 13022;
  const films = movies(28000, 3, 0);
  await posters(page);
  await prepare(page, { [first]: filmography(first, films, 450), [second]: filmography(second, films.slice(0, 1), 450) });
  const reads = timelineReads(page);
  await enter(page);
  await expect(region(page).getByRole('heading')).toHaveCount(0);
  await follow(page, first);
  await follow(page, second);
  const items = await hydrated(page, 2, 3, false);
  await settledLayout(page);
  await expect(region(page).getByRole('heading')).toHaveCount(0);
  expect(reads).toHaveLength(1);
  await nav(page, 'Search').click();
  await enter(page, () => nav(page, 'Timeline').click());
  await expect(region(page).getByRole('heading')).toHaveText(items.map(item => item.title));
  for (const item of items) await expect(movieRow(page, item.id)).toHaveCount(1);
  await expect(region(page).getByText('August, 2000', { exact: true })).toHaveCount(3);
  await expect(page.getByRole('button', { name: /refresh/i })).toHaveCount(0);
  expect(reads).toHaveLength(2);
});

test('unfollowing the visible movie’s only contributor returns to the nearest remaining date', async ({ page }) => {
  const leaving = 207442, remaining = 1591019;
  const films = movies(30000, 9, 0);
  await posters(page);
  await prepare(page, { [leaving]: filmography(leaving, films.slice(6)), [remaining]: filmography(remaining, films.slice(0, 6)) });
  await follow(page, remaining);
  await follow(page, leaving);
  const items = await hydrated(page, 2, 9, false);
  const reads = timelineReads(page);
  await enter(page);
  await wheel(page, 61);
  await settledLayout(page);
  const old = await visibleAnchor(page);
  expect(old.id).toBe(items[0].id);
  await nav(page, 'Following').click();
  await expect(page).toHaveURL(/\/following$/);
  const personRow = page.getByTestId('following-person-tmdb:' + leaving);
  await personRow.hover();
  const deleted = page.waitForResponse(r => r.url().endsWith('/api/v1/following') && r.request().method() === 'DELETE');
  await personRow.getByRole('button', { name: 'Unfollow' }).click();
  expect((await deleted).status()).toBe(204);
  await enter(page, () => page.goBack());
  expect(reads.at(-1)?.get('anchor_id')).toBe(String(old.id));
  await expect(movieRow(page, old.id)).toHaveCount(0);
  await staysAt(page, items[3].id, await topOf(region(page)));
});

test('a newly bootstrapped guest returns to a blank timeline', async ({ page, context }) => {
  const person = 1364004;
  const films = movies(32000, 4, 0);
  await posters(page);
  await prepare(page, { [person]: filmography(person, films) });
  await follow(page, person);
  await hydrated(page, 1, 4, false);
  await enter(page);
  await expect(region(page).getByRole('heading')).toHaveCount(4);
  await nav(page, 'Search').click();
  await context.clearCookies({ name: 'lumiere_guest' });
  // The first ordinary Following read detects the expired guest and invalidates readiness.
  const failed = page.waitForResponse(r => r.url().endsWith('/api/v1/following') && r.status() === 500);
  await nav(page, 'Following').click();
  await failed;
  const created = page.waitForResponse(r => r.url().endsWith('/guest-session') && r.headers()['x-lumiere-guest-created'] === 'true');
  const pending = gate(), release = gate();
  await page.route('**/api/v1/timeline*', async route => {
    const response = await route.fetch();
    pending.release();
    await release.wait;
    await route.fulfill({ response });
  });
  try {
    await nav(page, 'Timeline').click();
    await created;
    await pending.wait;
    await expect(region(page).getByRole('heading')).toHaveCount(0);
    const completed = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v1/timeline');
    release.release();
    expect((await completed).status()).toBe(200);
    await settledLayout(page);
    await expect(region(page).getByRole('heading')).toHaveCount(0);
  } finally { release.release(); }
});
