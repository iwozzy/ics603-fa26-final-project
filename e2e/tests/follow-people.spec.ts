import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
const row = (page: Page, index = 0) => page.getByTestId('search-result-' + index);
const input = (page: Page) => page.getByRole('textbox', { name: 'Search people' });
async function search(page: Page) {
  await input(page).fill('Tom'); await input(page).press('Enter');
  await expect(row(page)).toBeVisible();
}
async function count(request: APIRequestContext) { return (await (await request.get('http://127.0.0.1:18081/__counts')).json()).total as number; }
async function save(page: Page, index: number) {
  // Explicit, bounded user retries accommodate best-effort catalog persistence.
  for (let attempt = 0; attempt < 5; attempt++) {
    await row(page, index).hover();
    const button = row(page, index).getByRole('button', { name: 'Follow +' });
    await expect(button).toBeVisible();
    const completed = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
    await button.click();
    const response = await completed;
    if (response.status() === 200) { await expect(row(page, index).getByRole('status')).toBeVisible(); return; }
    expect(response.status()).toBe(500); await expect(button).toBeVisible();
  }
  throw new Error('Person was not persisted within five explicit user attempts');
}
test.beforeEach(async ({ request }) => { await request.post('http://127.0.0.1:18081/__control', { data: { scenarios: {} } }); });

for (const phase of ['delayed', 'empty', 'failed']) test(`following sidebar is unconditional and initial ${phase} content is blank`, async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/following', async route => {
    if (phase === 'delayed') await gate;
    await route.fulfill({ status: phase === 'failed' ? 500 : 200, contentType: 'application/json', body: phase === 'failed' ? '' : JSON.stringify({ people: [], limit: 3 }) });
  });
  try {
    await page.goto('/following');
    await expect(page.getByRole('link', { name: 'Search', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Following', exact: true })).toBeVisible();
    await expect(page.getByRole('progressbar')).toHaveCount(0);
    await expect(page.getByText(/loading|no follows|try again|error|unfollow/i)).toHaveCount(0);
    await expect(page.getByRole('img')).toHaveCount(0);
    await page.getByRole('link', { name: 'Search', exact: true }).click();
    await expect(input(page)).toBeVisible();
    await page.goBack(); await expect(page).toHaveURL(/\/following$/);
    await page.goForward(); await expect(input(page)).toBeVisible();
  } finally { release(); }
});

test('follow people by mouse and keyboard; cap, newest-first and reload persistence', async ({ page, request }) => {
  await page.goto('/'); await search(page);
  const first = row(page).getByRole('button', { name: 'Follow +' });
  await row(page).hover(); await expect(first).toBeVisible(); await first.hover(); await expect(first).toBeVisible();
  // A real Tab reaches an initially invisible eligible action and reveals its ring.
  await page.mouse.move(0, 0); await input(page).focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
  await expect(first).toBeFocused(); await expect(first).toBeVisible();
  const firstResponse = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
  await page.keyboard.press('Enter');
  if ((await firstResponse).status() !== 200) await save(page, 0);
  await save(page, 1);
  // Space activates the third action exactly once.
  const third = row(page, 2).getByRole('button', { name: 'Follow +' });
  await third.focus(); await expect(third).toBeVisible();
  const thirdResponse = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
  await page.keyboard.press('Space'); expect((await thirdResponse).status()).toBe(200);
  await expect(page.getByRole('button', { name: 'Follow +' })).toHaveCount(0);
  const direct = await page.request.post('/api/v1/following', { data: { provider: 'tmdb', provider_id: 500 } });
  expect(direct.status()).toBe(500); expect(await direct.body()).toHaveLength(0);
  await page.getByRole('link', { name: 'Following', exact: true }).click();
  await expect(page).toHaveURL(/\/following$/);
  await expect(input(page)).toBeHidden();
  await expect(page.getByText('Tom Hanks', { exact: true })).toBeVisible();
  const names = await page.locator('body').innerText();
  expect(names.indexOf('Tom Hanks')).toBeLessThan(names.indexOf('Tom Holland'));
  expect(names.indexOf('Tom Holland')).toBeLessThan(names.indexOf('Tom Skerritt'));
  await expect(page.getByText('Unfollow', { exact: true })).toHaveCount(0);
  await page.reload(); await expect(page.getByText('Tom Hanks', { exact: true })).toBeVisible();
  expect(await count(request)).toBe(1);
});

test('mouse following status hides on leave and keeps its outline after reload', async ({ page }) => {
  await page.goto('/'); await search(page); await save(page, 0);
  const status = row(page).getByRole('status');
  await expect(status).toHaveCSS('border-color', 'rgb(195, 199, 204)');
  await page.mouse.move(0, 0);
  await expect(status).toHaveCSS('opacity', '0');
  await row(page).hover();
  await expect(status).toHaveCSS('opacity', '1');
  await page.reload(); await search(page);
  await row(page).hover();
  await expect(status).toHaveCSS('opacity', '1');
  await expect(status).toHaveCSS('border-color', 'rgb(195, 199, 204)');
  await page.mouse.move(0, 0);
  await expect(status).toHaveCSS('opacity', '0');
});

test('following lost third response rolls back without GET and manual retry succeeds at cap', async ({ page, request }) => {
  let followingGets = 0;
  page.on('request', r => { if (r.url().endsWith('/following') && r.method() === 'GET') followingGets++; });
  await page.goto('/'); await search(page); await save(page, 0); await save(page, 1);
  let failedDelivery = false;
  await page.route('**/api/v1/following', async route => {
    if (route.request().method() !== 'POST' || failedDelivery) return route.continue();
    const response = await route.fetch(); expect(response.status()).toBe(200);
    failedDelivery = true; await route.abort('failed');
  });
  const getsBeforeFailedDelivery = followingGets;
  await row(page, 2).hover(); await row(page, 2).getByRole('button', { name: 'Follow +' }).click();
  await expect.poll(() => failedDelivery).toBe(true);
  await expect(row(page, 2).getByRole('button', { name: 'Follow +' })).toBeVisible();
  expect(followingGets).toBe(getsBeforeFailedDelivery);
  await save(page, 2);
  expect((await (await page.request.get('/api/v1/following')).json()).people).toHaveLength(3);
  expect(await count(request)).toBe(1);
});

test('following missing catalog person rolls back preserving query and does not reconcile', async ({ page }) => {
  let gets = 0;
  page.on('request', r => { if (r.url().endsWith('/following') && r.method() === 'GET') gets++; });
  await page.route('**/api/v1/people/search?*', route => route.fulfill({ json: { query: 'Tom', people: [{ provider: 'tmdb', provider_id: Number.MAX_SAFE_INTEGER, name: 'Absent Person', known_for_department: null, profile_image_url: null, known_for: [] }] } }));
  await page.goto('/'); await search(page); await row(page).hover();
  const button = row(page).getByRole('button', { name: 'Follow +' }); await expect(button).toBeVisible();
  const before = gets;
  const completed = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
  await button.click(); const response = await completed;
  expect(response.status()).toBe(500); expect(await response.body()).toHaveLength(0);
  await expect(button).toBeVisible(); expect(gets).toBe(before);
  await expect(input(page)).toHaveValue('Tom'); await expect(page.getByText('Absent Person')).toBeVisible();
});

test('following pending save survives navigation and Search resets on returning and history', async ({ page }) => {
  await page.goto('/'); await search(page);
  // Ensure the selected summary is stored with an explicit successful follow.
  await save(page, 0);
  let release!: () => void;
  let committed!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const saved = new Promise<void>(resolve => { committed = resolve; });
  await page.route('**/api/v1/following', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    const response = await route.fetch(); expect(response.status()).toBe(200); committed();
    await gate; await route.fulfill({ response });
  });
  try {
    await row(page, 1).hover(); await row(page, 1).getByRole('button', { name: 'Follow +' }).click(); await saved;
    await page.getByRole('link', { name: 'Following', exact: true }).click();
    await expect(page.getByText('Tom Holland', { exact: true })).toBeVisible(); release();
    await page.getByRole('link', { name: 'Search', exact: true }).click();
    await expect(input(page)).toHaveValue(''); await expect(page.getByText('Example searches:').filter({ visible: true })).toBeVisible();
    await page.goBack(); await expect(page.getByText('Tom Holland', { exact: true })).toBeVisible();
    await page.goForward(); await expect(input(page)).toHaveValue('');
  } finally { release(); }
});

test('follow people touch reveals first, switches, dismisses and scrolls without activation', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:18080', hasTouch: true, viewport: { width: 375, height: 600 } });
  const page = await context.newPage();
  let posts = 0;
  page.on('request', r => { if (r.url().endsWith('/following') && r.method() === 'POST') posts++; });
  try {
    await page.goto('/'); await search(page);
    const action = row(page).getByRole('button', { name: 'Follow +' });
    await expect(action).toHaveCount(1);
    // A first tap exactly where the invisible action sits must only select.
    const box = await action.boundingBox(); expect(box).not.toBeNull();
    await page.touchscreen.tap(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await expect(action).toBeVisible(); expect(posts).toBe(0);
    await row(page, 1).getByText('Tom Holland').tap();
    await expect(action).toHaveCSS('opacity', '0');
    await expect(row(page, 1).getByRole('button')).toBeVisible(); expect(posts).toBe(0);
    await input(page).tap();
    await expect(row(page, 1).getByRole('button')).toHaveCSS('opacity', '0');
    await row(page).getByText('Tom Skerritt').tap(); await expect(action).toBeVisible();
    const completed = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
    await action.tap(); expect((await completed).status()).toBe(200); expect(posts).toBe(1);
    const session = await context.newCDPSession(page);
    const bounds = await row(page, 2).boundingBox(); expect(bounds).not.toBeNull();
    const x = bounds!.x + 20, y = Math.min(bounds!.y + 20, 550);
    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
    await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: y - 80 }] });
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    expect(posts).toBe(1);
    await expect(row(page, 2).getByRole('button')).toHaveCSS('opacity', '0');
    await page.getByRole('link', { name: 'Following', exact: true }).tap();
    await expect(page).toHaveURL(/\/following$/); await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  } finally { await context.close(); }
});

for (const moveAway of [false, true]) test(`following keyboard rollback preserves real focus and respects user movement ${moveAway}`, async ({ page }) => {
  await page.goto('/'); await search(page); await save(page, 0);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let rejected = false;
  await page.route('**/api/v1/following', async route => {
    if (route.request().method() !== 'POST' || rejected) return route.continue();
    rejected = true; await gate;
    await route.fulfill({ status: 500, body: '', headers: { 'Cache-Control': 'no-store' } });
  });
  const button = row(page, 1).getByRole('button', { name: 'Follow +' });
  await page.mouse.move(0, 0); await button.focus();
  await expect(button).toHaveCSS('opacity', '1');
  const failed = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
  try {
    await page.keyboard.press('Enter');
    await expect(row(page, 1).getByRole('status')).toBeFocused({ timeout: 1000 });
    if (moveAway) await input(page).focus();
    release(); expect((await failed).status()).toBe(500);
    if (moveAway) {
      await expect(input(page)).toBeFocused();
      await expect(button).not.toBeFocused();
      await expect(button).toHaveCSS('opacity', '0');
    } else {
      await expect(button).toBeFocused();
      await expect(button).toHaveCSS('opacity', '1');
      const retried = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
      await page.keyboard.press('Space'); expect((await retried).status()).toBe(200);
      await expect(row(page, 1).getByRole('status')).toBeFocused({ timeout: 1000 });
    }
  } finally { release(); await failed; }
});
