import { test, expect, type Page } from '@playwright/test';
import {
  enter, filmography, follow, gate, hydrated, movieRow, movies, nav, posters, prepare, region,
  settledLayout, staysAt, timelineReads, topOf, visibleAnchor, wheel,
} from '../support/timeline.ts';

test.use({ bypassCSP: true, hasTouch: true });

async function swipeDown(page: Page) {
  const box = (await region(page).boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + 70;
  const cdp = await page.context().newCDPSession(page);
  try {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: y + 60 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  } finally { await cdp.detach(); }
}

const shapes = [
  { label: 'full', past: 36, people: [500, 1017294, 2524] },
  { label: 'short', past: 1, people: [11824, 192944, 75066] },
  { label: 'empty', past: 0, people: [91606, 2040266, 10993] },
];
for (const { label, past, people } of shapes) {
  for (const [index, input] of ['wheel', 'keyboard', 'touch'].entries()) {
    test(input + ' discovers future movies with ' + label + ' initial past content', async ({ page }) => {
      const person = people[index];
      const films = movies(10000000 + person * 100, past, 4);
      await posters(page);
      await prepare(page, { [person]: filmography(person, films) });
      await follow(page, person);
      await hydrated(page, 1, past, true);
      const reads = timelineReads(page);
      await enter(page);
      expect(reads.map(query => query.get('direction'))).toEqual([null]);
      const firstUpcoming = region(page).getByRole('heading', { name: films[past].title, exact: true });
      await expect(firstUpcoming).toHaveCount(0);
      if (input === 'wheel') await wheel(page, -60);
      else if (input === 'keyboard') await region(page).press('ArrowUp');
      else await swipeDown(page);
      await expect(firstUpcoming).toBeAttached();
      expect(reads.map(query => query.get('direction'))).toEqual([null, 'newer']);
      // The old row stays anchored after prepend. The user can now scroll up to see the new rows.
      if (past) await region(page).press('Home');
      await expect(region(page).getByRole('heading', { name: films.at(-1)!.title, exact: true })).toBeInViewport();
    });
  }
}

test('variable-height prepend, resize, poster completion and repeated route return preserve the measured offset', async ({ page }) => {
  const person = 78798;
  const films = movies(35000, 42, 18);
  const pictures = gate();
  const images = await posters(page, pictures.wait);
  try {
    await prepare(page, { [person]: filmography(person, films) });
    await follow(page, person);
    const items = await hydrated(page, 1, 42, true);
    const reads = timelineReads(page);
    await enter(page);
    await expect.poll(images.started).toBeGreaterThan(0);
    const initial = await visibleAnchor(page);
    expect(initial.id).toBe(items[0].id);
    expect(images.completed()).toBe(0);
    await wheel(page, -1);
    await expect(region(page).getByRole('heading', { name: films.at(-1)!.title, exact: true })).toBeAttached();
    await staysAt(page, initial.id, initial.y);
    await page.setViewportSize({ width: 835, height: 697 });
    await staysAt(page, initial.id, initial.y);
    pictures.release();
    await expect.poll(images.completed).toBeGreaterThan(0);
    await expect.poll(() => region(page).locator('img').evaluateAll(images =>
      images.some(image => image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0))).toBe(true);
    await staysAt(page, initial.id, initial.y);

    await wheel(page, 530);
    await settledLayout(page);
    const anchor = await visibleAnchor(page);
    expect(anchor.id).not.toBe(initial.id);
    expect(anchor.y).toBeLessThan(await topOf(region(page)));
    for (const destination of ['Search', 'Following', 'Search'] as const) {
      const before = reads.length;
      await nav(page, destination).click();
      await expect(page).toHaveURL(destination === 'Search' ? /\/$/ : /\/following$/);
      await enter(page, () => page.goBack());
      expect(reads.slice(before).map(query => query.get('anchor_id'))).toEqual([String(anchor.id)]);
      await staysAt(page, anchor.id, anchor.y);
    }
    await page.goForward();
    await expect(page.getByRole('textbox', { name: 'Search people' })).toBeVisible();
    const beforeBack = reads.length;
    await enter(page, () => page.goBack());
    expect(reads.slice(beforeBack).map(query => query.get('anchor_id'))).toEqual([String(anchor.id)]);
    await staysAt(page, anchor.id, anchor.y);
    await enter(page, () => page.reload());
    expect(reads.at(-1)?.has('anchor_id')).toBe(false);
    await staysAt(page, initial.id, await topOf(region(page)));
  } finally { pictures.release(); }
});

test('scrolling while the return read is delayed keeps the new movie and performs one replacement', async ({ page }) => {
  const person = 15112;
  const films = movies(36000, 52, 10);
  await posters(page);
  await prepare(page, { [person]: filmography(person, films) });
  await follow(page, person);
  await hydrated(page, 1, 52, true);
  await enter(page);
  await wheel(page, 550);
  await settledLayout(page);
  const old = await visibleAnchor(page);
  await nav(page, 'Following').click();
  const original = gate(), received = gate(), replacement = gate(), replacing = gate();
  const originalSent = gate(), replacementSent = gate();
  const anchors: string[] = [];
  await page.route('**/api/v1/timeline?*', async route => {
    const id = new URL(route.request().url()).searchParams.get('anchor_id');
    if (!id) return route.continue();
    anchors.push(id);
    const first = anchors.length === 1;
    const response = await route.fetch();
    if (first) { received.release(); await original.wait; }
    else { replacing.release(); await replacement.wait; }
    await route.fulfill({ response });
    (first ? originalSent : replacementSent).release();
  });
  try {
    await nav(page, 'Timeline').click();
    await received.wait;
    await staysAt(page, old.id, old.y);
    await wheel(page, 730);
    await replacing.wait;
    const moved = await visibleAnchor(page);
    expect(moved.id).not.toBe(old.id);
    original.release();
    await originalSent.wait;
    await staysAt(page, moved.id, moved.y);
    replacement.release();
    await replacementSent.wait;
    await staysAt(page, moved.id, moved.y);
    expect(anchors).toEqual([String(old.id), String(moved.id)]);
  } finally { original.release(); replacement.release(); }
});

test('older paging reaches a deep variable-height movie and restores it on sidebar return', async ({ page }) => {
  const person = 2441;
  const films = movies(37000, 56, 0);
  await posters(page);
  await prepare(page, { [person]: filmography(person, films) });
  await follow(page, person);
  const items = await hydrated(page, 1, 56, false);
  const reads = timelineReads(page);
  await enter(page);
  for (let count = 1; count <= 2; count++) {
    await region(page).press('End');
    await expect.poll(() => reads.filter(query => query.get('direction') === 'older').length).toBe(count);
    await settledLayout(page);
  }
  await region(page).press('End');
  await expect(movieRow(page, items.at(-1)!.id)).toBeInViewport();
  await settledLayout(page);
  const anchor = await visibleAnchor(page);
  expect(items.findIndex(movie => movie.id === anchor.id)).toBeGreaterThan(40);
  await nav(page, 'Following').click();
  await expect(page).toHaveURL(/\/following$/);
  await enter(page, () => nav(page, 'Timeline').click());
  expect(reads.at(-1)?.get('anchor_id')).toBe(String(anchor.id));
  await staysAt(page, anchor.id, anchor.y);
});
