import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => { await request.post('http://127.0.0.1:18081/__control', { data: { scenarios: {} } }); });
async function counts(request: import('@playwright/test').APIRequestContext) { return (await (await request.get('http://127.0.0.1:18081/__counts')).json()).total as number; }
async function search(page: import('@playwright/test').Page) {
  await page.getByRole('textbox', {name:'Search people'}).fill('Tom');
  const completed = page.waitForResponse(r => r.url().includes('/people/search?'));
  await page.getByRole('button', {name:'Search', exact:true}).click();
  const response = await completed;
  await expect(page.getByText('Tom Skerritt', {exact:true})).toBeVisible();
  return response;
}

test('test_real_browser_private_cache_reuse', async ({ page, context, request }) => {
  // This fresh context has no request routing, HAR replay, service workers or cache mocks.
  let bootstraps = 0;
  page.on('request', request => { if (request.url().endsWith('/guest-session')) bootstraps++; });
  await page.goto('/');
  const first = await search(page);
  expect(first.headers()['cache-control']).toBe('private, max-age=300');
  expect(first.headers()['vary'] ?? '').not.toMatch(/cookie/i);
  await search(page);
  expect(await counts(request)).toBe(1); expect(bootstraps).toBe(1);
  const before = (await context.cookies()).find(cookie => cookie.name === 'lumiere_guest')?.value;
  await context.clearCookies();
  await page.evaluate(async () => { const result = await fetch('/api/v1/guest-session', { method: 'POST', credentials: 'same-origin' }); if (!result.ok) throw new Error('bootstrap failed'); });
  const after = (await context.cookies()).find(cookie => cookie.name === 'lumiere_guest')?.value;
  expect(after).toBeDefined(); expect(after).not.toBe(before);
  await search(page);
  expect(await counts(request)).toBe(1); expect(bootstraps).toBe(2);
});

test('test_cache_expires_after_300_seconds @cache-expiry', async ({ page, request }) => {
  test.setTimeout(340000);
  await page.goto('/'); const first = await search(page);
  expect(first.headers()['cache-control']).toBe('private, max-age=300');
  expect(await counts(request)).toBe(1);
  for (let minute = 1; minute <= 5; minute++) { await new Promise(resolve => setTimeout(resolve, 60000)); console.log(`Cache expiry: ${minute * 60} real seconds elapsed`); }
  await new Promise(resolve => setTimeout(resolve, 2000));
  await search(page); expect(await counts(request)).toBe(2);
});
