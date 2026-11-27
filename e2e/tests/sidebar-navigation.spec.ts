import { test, expect } from '@playwright/test';
import { gate, nav } from '../support/timeline.ts';

for (const phase of ['completed', 'pending'] as const) {
  test('sidebar screens retain a ' + phase + ' search and reuse Following', async ({ page }) => {
    const person = { provider: 'tmdb', provider_id: 123, name: 'Tom Navigation',
      known_for_department: 'Acting', known_for: ['A movie'], profile_image_url: null };
    const completion = gate();
    let searches = 0;
    await page.route('**/api/v1/guest-session', route => route.fulfill({
      status: 204, headers: { 'X-Lumiere-Guest-Created': 'false' },
    }));
    await page.route('**/api/v1/following', route => route.fulfill({ json: { people: [person], limit: 3 } }));
    await page.route('**/api/v1/timeline*', route => route.fulfill({ json: {
      items: [], older_cursor: null, newer_cursor: null, as_of: '2026-11-26', anchor_index: null,
    } }));
    await page.route('**/api/v1/people/search?*', async route => {
      searches++;
      if (phase === 'pending') await completion.wait;
      await route.fulfill({ json: { query: 'Tom', people: [person] } });
    });
    const input = page.getByRole('textbox', { name: 'Search people' });
    const result = page.getByTestId('search-result-0');
    const following = page.getByTestId('following-person-tmdb:123');
    try {
      await page.goto('/');
      await input.fill('Tom');
      await input.evaluate(node => node.setAttribute('data-navigation-instance', 'search'));
      await input.press('Enter');
      await expect.poll(() => searches).toBe(1);
      if (phase === 'completed') await expect(result).toContainText(person.name);
      await input.fill('Tom revised');

      let visitedFollowing = false;
      for (const destination of ['Following', 'Timeline', 'Following'] as const) {
        await nav(page, destination).click();
        if (destination === 'Following') {
          await expect(following).toBeVisible();
          if (visitedFollowing) await expect(following).toHaveAttribute('data-navigation-instance', 'following');
          else await following.evaluate(node => node.setAttribute('data-navigation-instance', 'following'));
          visitedFollowing = true;
        }
        completion.release();
        // Observe completion while Search is still hidden, before returning to it.
        await expect(result).toContainText(person.name);
        await nav(page, 'Search').click();
        await expect(input).toHaveValue('Tom revised');
        await expect(input).toHaveAttribute('data-navigation-instance', 'search');
        await expect(result).toContainText(person.name);
        expect(searches).toBe(1);
      }
      await page.goBack();
      await expect(page).toHaveURL(/\/following$/);
      await page.goForward();
      await expect(page).toHaveURL(/\/$/);
      await expect(input).toHaveValue('Tom revised');
      await expect(result).toContainText(person.name);
      await input.fill('');
      await expect(result).toHaveCount(0);
      await expect(page.getByText('Example searches:')).toBeVisible();
      await input.fill('Unsubmitted draft');
      await page.reload();
      await expect(input).toHaveValue('');
      await expect(page.getByText('Example searches:')).toBeVisible();
      expect(searches).toBe(1);
    } finally { completion.release(); }
  });
}
