import { expect, test } from '@playwright/test';

test('production bundle submits to the same origin through the API proxy', async ({
  page,
  request,
  baseURL,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const health = await request.get('/health');
  expect(health.ok()).toBe(true);
  expect(await health.json()).toEqual({ status: 'ok' });

  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Cast & Crew' }),
  ).toBeVisible();

  await page.route('**/api/people/search?**', async (route) => {
    const url = new URL(route.request().url());
    expect(url.origin).toBe(new URL(baseURL!).origin);
    expect(url.searchParams.get('query')).toBe('Tom');
    // Exercise the real API's invalid-input response without provider access.
    url.searchParams.set('query', ' ');
    const response = await route.fetch({ url: url.toString() });
    expect(await response.json()).toEqual({
      code: 'SEARCH_FAILED',
      message: 'Unable to complete search.',
    });
    await route.fulfill({ response });
  });
  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/people/search'),
  );
  await page.getByLabel('Search people').fill('Tom');
  await page.getByLabel('Search people').press('Enter');
  const response = await responsePromise;
  expect(response.status()).toBe(500);
  expect(response.headers()['cache-control']).toBe('no-store');
  await expect(page.getByText('Try a search')).toBeVisible();
  await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel('Search people')).toHaveValue('');
  expect(errors).toEqual([]);
});

test('serves navigation fallbacks and returns 404 for missing assets', async ({
  request,
}) => {
  const navigation = await request.get('/future-client-route');
  expect(navigation.ok()).toBe(true);
  expect(navigation.headers()['content-type']).toContain('text/html');
  expect(navigation.headers()['cache-control']).toBe('no-cache');
  for (const path of ['/_expo/missing.js', '/assets/missing.png']) {
    expect((await request.get(path)).status()).toBe(404);
  }
  const missingApi = await request.get('/api/missing');
  expect(missingApi.status()).toBe(404);
  expect(missingApi.headers()['content-type']).toContain('application/json');
});
