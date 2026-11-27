import { test, expect } from '@playwright/test';
import { gate, nav, region, settledLayout, visibleAnchor, wheel } from '../support/timeline.ts';

test('sidebar returns reuse the timeline and preserve its viewport before refresh completes', async ({ page }) => {
  const films = Array.from({ length: 80 }, (_, index) => ({
    id: 90000 - index, title: 'Navigation movie ' + index, release_date: '2000-01-01',
    poster_image_url: null, overview: 'A scene in a coastal town. '.repeat(4 + 10 * (index % 5)),
  }));
  let pending: ReturnType<typeof gate> | undefined;
  let refreshes = 0;
  await page.route('**/api/v1/guest-session', route => route.fulfill({
    status: 204, headers: { 'X-Lumiere-Guest-Created': 'false' },
  }));
  await page.route('**/api/v1/following', route => route.fulfill({ json: { people: [], limit: 3 } }));
  await page.route('**/api/v1/timeline*', async route => {
    const anchor = Number(new URL(route.request().url()).searchParams.get('anchor_id'));
    const index = films.findIndex(movie => movie.id === anchor);
    const start = anchor ? Math.max(0, index - 5) : 0;
    if (anchor) { refreshes++; await pending?.wait; }
    await route.fulfill({ json: {
      items: anchor ? films.slice(start, start + 20) : films,
      older_cursor: null, newer_cursor: null, as_of: '2026-11-26',
      anchor_index: anchor ? index - start : null,
    } });
  });

  await page.goto('/timeline');
  await expect(region(page).getByRole('heading').first()).toBeVisible();
  await wheel(page, 2400);
  await settledLayout(page);
  const saved = await visibleAnchor(page);
  await region(page).evaluate(node => node.setAttribute('data-navigation-instance', 'retained'));

  try {
    const destinations = ['Search', 'Following', 'Search'] as const;
    for (const [index, destination] of destinations.entries()) {
      pending = gate();
      await nav(page, destination).click();
      await nav(page, 'Timeline').click();
      await expect.poll(() => refreshes).toBe(index + 1);
      // The API response is still gated: the existing list must already be usable.
      await expect(region(page)).toHaveAttribute('data-navigation-instance', 'retained');
      for (let frame = 0; frame < 10; frame++) {
        const visible = await visibleAnchor(page);
        expect(visible.id).toBe(saved.id);
        expect(Math.abs(visible.y - saved.y)).toBeLessThanOrEqual(2);
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
      }
      const refreshed = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/timeline');
      pending.release();
      await (await refreshed).finished();
      await settledLayout(page);
      const visible = await visibleAnchor(page);
      expect(visible.id).toBe(saved.id);
      expect(Math.abs(visible.y - saved.y)).toBeLessThanOrEqual(2);
    }
    await page.goBack();
    await expect(page).toHaveURL(/\/$/);
    await page.goForward();
    await expect(page).toHaveURL(/\/timeline$/);
    await settledLayout(page);
    const visible = await visibleAnchor(page);
    expect(visible.id).toBe(saved.id);
    expect(Math.abs(visible.y - saved.y)).toBeLessThanOrEqual(2);
  } finally { pending?.release(); }
});
