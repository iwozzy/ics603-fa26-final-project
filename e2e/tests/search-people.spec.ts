import { test, expect } from '@playwright/test';
const names = ['Tom Skerritt','Tom Holland','Tom Hanks','Tom Cruise','Tom Hopper','Tom Hardy','Tom Welling'];
const input = (page: import('@playwright/test').Page) => page.getByRole('textbox', { name: 'Search people' });
async function scenario(request: import('@playwright/test').APIRequestContext, scenarios = {}) { await request.post('http://127.0.0.1:18081/__control', { data: { scenarios } }); }
async function count(request: import('@playwright/test').APIRequestContext) { return (await (await request.get('http://127.0.0.1:18081/__counts')).json()).total as number; }
test.beforeEach(async ({ request }) => { await scenario(request); });

test('fixture order, mixed titles, keyboard/icon and image fallback', async ({ page, request }) => {
  await page.goto('/'); await expect(page).toHaveTitle('Lumiere');
  await expect(page.getByText('Example searches:')).toBeVisible();
  await input(page).fill('Tom'); expect(await count(request)).toBe(0);
  const response = page.waitForResponse(r => r.url().includes('/people/search?'));
  await input(page).press('Enter');
  const first = await response;
  expect(first.status()).toBe(200); expect(first.headers()['cache-control']).toBe('private, max-age=300'); expect(first.headers()['vary'] ?? '').not.toMatch(/cookie/i);
  for (const name of names) await expect(page.getByText(name, { exact: true })).toBeVisible();
  const text = await page.locator('body').innerText();
  expect(names.map(name => text.indexOf(name))).toEqual([...names.map(name => text.indexOf(name))].sort((a,b) => a-b));
  await expect(page.getByText('Acting · The Umbrella Academy, Resident Evil: Welcome to Raccoon City, I Feel Pretty', { exact:true })).toBeVisible();
  await expect(page.getByText('Acting · Smallville, Lucifer, The Fog', { exact:true })).toBeVisible();
  await expect(page.getByRole('img', {name: 'Tom Skerritt silhouette'})).toBeVisible();
  await expect(input(page)).toBeFocused();
  await expect(page.getByText('Example searches:')).toHaveCount(0);
  await expect(page.getByText('Follow', {exact:true})).toHaveCount(0); await expect(page.getByText('Movies', {exact:true})).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(375);
});

for (const kind of ['empty','error']) test(`${kind} response leaves blank results with no extra copy`, async ({ page, request }) => {
  await scenario(request, { [kind]: { empty: kind === 'empty', status: kind === 'error' ? 503 : 200, delayMs: 300 } });
  await page.goto('/'); await input(page).fill(kind);
  const response = page.waitForResponse(r => r.url().includes('/people/search?'));
  await page.getByRole('button', {name:'Search', exact:true}).click();
  await expect(page.getByText('Example searches:')).toBeVisible();
  const completed = await response;
  expect(completed.status()).toBe(kind === 'empty' ? 200 : 500);
  expect(completed.headers()['cache-control']).toBe(kind === 'empty' ? 'private, max-age=300' : 'no-store');
  await expect(page.getByRole('button', {name:'Search', exact:true})).toHaveAttribute('aria-busy','false');
  await expect(page.getByText('Example searches:')).toHaveCount(0);
  await expect(page.getByText(/no results|try again|error|unavailable/i)).toHaveCount(0);
  for (const name of names) await expect(page.getByText(name, {exact:true})).toHaveCount(0);
});

test('slow overlapping submissions use latest result and clear invalidates pending', async ({ page, request }) => {
  await scenario(request, { A: { delayMs: 1200, prefix: 'A ' }, B: { prefix: 'B ' }, C: { delayMs: 800, prefix: 'C ' } });
  await page.goto('/'); await input(page).fill('A'); await input(page).press('Enter');
  await expect(page.getByRole('button', {name:'Search', exact:true})).toHaveAttribute('aria-busy', 'true');
  await expect(page.getByText('Example searches:')).toBeVisible();
  await expect(input(page)).toBeEditable();
  await expect.poll(() => count(request)).toBe(1);
  await input(page).fill('B'); await page.getByRole('button', {name:'Search', exact:true}).click();
  await expect(page.getByText('B Tom Skerritt', {exact:true})).toBeVisible();
  await expect.poll(async () => (await (await request.get('http://127.0.0.1:18081/__counts')).json()).completed).toBe(2);
  await expect(page.getByText('A Tom Skerritt', {exact:true})).toHaveCount(0);
  await input(page).fill('C'); await input(page).press('Enter');
  await expect.poll(() => count(request)).toBe(3);
  await input(page).fill('');
  await expect(page.getByText('Example searches:')).toBeVisible();
  await expect.poll(async () => (await (await request.get('http://127.0.0.1:18081/__counts')).json()).completed).toBe(3);
  await expect(page.getByText('C Tom Skerritt', {exact:true})).toHaveCount(0);
});

test('session quota rejects before a sixth provider dispatch', async ({ page, request }) => {
  await page.goto('/');
  for (let index = 0; index < 6; index++) {
    await input(page).fill('Quota' + index);
    const finished = page.waitForResponse(r => r.url().includes('/people/search?'));
    await input(page).press('Enter');
    const response = await finished;
    expect(response.status()).toBe(index < 5 ? 200 : 500);
  }
  await expect(page.getByText('Tom Skerritt', {exact:true})).toHaveCount(0);
  await expect(page.getByRole('button', {name:'Search', exact:true})).toHaveAttribute('aria-busy','false');
  expect(await count(request)).toBe(5);
});

test('Unicode input is preserved once and code-point bounds apply', async ({ page, request }) => {
  await page.goto('/');
  for (const query of ["Timothée O'Neil & 李😀", '😀'.repeat(200)]) {
    await input(page).fill(query);
    const finished = page.waitForResponse(r => r.url().includes('/people/search?'));
    await input(page).press('Enter');
    const response = await finished;
    expect(new URL(response.url()).searchParams.get('query')).toBe(query);
    expect(response.status()).toBe(200);
    await expect(page.getByText('Tom Skerritt', {exact:true})).toBeVisible();
  }
  await input(page).fill('😀'.repeat(201)); await input(page).press('Enter');
  await expect(page.getByText('Tom Skerritt', {exact:true})).toHaveCount(0);
  expect(await count(request)).toBe(2);
});
