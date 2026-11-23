import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
const searchRow = (page: Page, index = 0) => page.getByTestId('search-result-' + index);
const rows = (page: Page) => page.getByTestId(/^following-person-/).filter({ visible: true });
const followingRow = (page: Page, name: string) => rows(page).filter({ has: page.getByText(name, { exact: true }) });
const nav = (page: Page, name: 'Search' | 'Following') => page.getByRole('link', { name, exact: true });
async function search(page: Page) {
  const input = page.getByRole('textbox', { name: 'Search people' });
  await input.fill('Tom'); await input.press('Enter'); await expect(searchRow(page)).toBeVisible();
}
async function save(page: Page, index: number) {
  for (let attempt = 0; attempt < 5; attempt++) {
    await searchRow(page, index).hover();
    const completed = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'POST');
    await searchRow(page, index).getByRole('button', { name: 'Follow +' }).click();
    const response = await completed;
    if (response.status() === 200) { await expect(searchRow(page, index).getByRole('status')).toHaveCount(1); return; }
    expect(response.status()).toBe(500);
    await expect(searchRow(page, index).getByRole('button', { name: 'Follow +' })).toHaveCount(1);
  }
  throw new Error('Person was not persisted within five explicit user attempts');
}
async function seed(page: Page, count = 1) {
  await page.goto('/'); await search(page);
  for (let index = 0; index < count; index++) await save(page, index);
  await nav(page, 'Following').click(); await expect(rows(page)).toHaveCount(count);
}
async function providerCount(request: APIRequestContext) { return (await (await request.get('http://127.0.0.1:18081/__counts')).json()).total as number; }
const deletes = (page: Page) => page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'DELETE');
test.beforeEach(async ({ request }) => { await request.post('http://127.0.0.1:18081/__control', { data: { scenarios: {} } }); });

test('unfollow mouse reveal, durable empty 204, no GET and final blank row', async ({ page, request }) => {
  let gets = 0;
  page.on('request', r => { if (r.url().endsWith('/following') && r.method() === 'GET') gets++; });
  await seed(page);
  const beforeProvider = await providerCount(request);
  const row = followingRow(page, 'Tom Skerritt'); const action = row.getByRole('button', { name: 'Unfollow' });
  await page.mouse.move(0, 0); await expect(action).toHaveCSS('opacity', '0'); await expect(action).toHaveCSS('pointer-events', 'none');
  await row.hover(); await action.hover(); await expect(action).toHaveCSS('opacity', '1');
  await expect(action).toHaveCSS('border-color', 'rgb(195, 199, 204)');
  await page.mouse.move(0, 0); await expect(action).toHaveCSS('opacity', '0');
  const before = gets, completed = deletes(page);
  await row.hover(); await action.click(); const response = await completed;
  expect(response.status()).toBe(204); expect(await response.body()).toHaveLength(0);
  await expect(rows(page)).toHaveCount(0); expect(gets).toBe(before);
  await expect(page.getByRole('progressbar')).toHaveCount(0);
  await expect(page.getByText(/loading|no follows|try again|error|unfollow/i)).toHaveCount(0);
  await page.reload(); await expect(rows(page)).toHaveCount(0);
  const absent = await page.request.delete('/api/v1/following', { data: { provider: 'tmdb', provider_id: Number.MAX_SAFE_INTEGER } });
  expect(absent.status()).toBe(204); expect(await absent.body()).toHaveLength(0);
  expect(await providerCount(request)).toBe(beforeProvider);
});

for (const moveAway of [false, true]) test(`unfollow lost delivery restores keyboard access and respects movement ${moveAway}`, async ({ page }) => {
  let gets = 0;
  page.on('request', r => { if (r.url().endsWith('/following') && r.method() === 'GET') gets++; });
  await seed(page, 2);
  const row = followingRow(page, 'Tom Holland'), button = row.getByRole('button', { name: 'Unfollow' });
  let release!: () => void, committed!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const saved = new Promise<void>(resolve => { committed = resolve; });
  let lost = false;
  await page.route('**/api/v1/following', async route => {
    if (route.request().method() !== 'DELETE' || lost) return route.continue();
    lost = true;
    const response = await route.fetch(); expect(response.status()).toBe(204); committed();
    await gate; await route.abort('failed');
  });
  try {
    await page.mouse.move(0, 0); await button.focus(); await expect(button).toHaveCSS('opacity', '1');
    const before = gets;
    await page.keyboard.press('Enter'); await saved; await expect(row).toHaveCount(0);
    if (moveAway) await nav(page, 'Search').focus();
    release(); await expect(row).toHaveCount(1);
    expect(gets).toBe(before);
    await expect(rows(page).getByText(/Tom /)).toHaveText(['Tom Holland', 'Tom Skerritt']);
    if (moveAway) {
      await expect(nav(page, 'Search')).toBeFocused(); await expect(button).not.toBeFocused();
      await expect(button).toHaveCSS('opacity', '0');
      await button.focus();
    } else { await expect(button).toBeFocused(); await expect(button).toHaveCSS('opacity', '1'); }
    const repeated = deletes(page); await page.keyboard.press('Space'); expect((await repeated).status()).toBe(204);
    await expect(row).toHaveCount(0); expect(gets).toBe(before);
    await page.reload(); await expect(rows(page)).toHaveCount(1);
  } finally { release(); }
});

test('unfollow disappears immediately while DELETE is held and survives navigation', async ({ page }) => {
  await seed(page, 2);
  let release!: () => void, entered!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const waiting = new Promise<void>(resolve => { entered = resolve; });
  await page.route('**/api/v1/following', async route => {
    if (route.request().method() !== 'DELETE') return route.continue();
    entered(); await gate; await route.continue();
  });
  try {
    const row = followingRow(page, 'Tom Holland'); await row.hover(); await row.getByRole('button').click();
    await waiting; await expect(row).toHaveCount(0);
    await nav(page, 'Search').click(); await search(page);
    await expect(searchRow(page, 1).getByRole('button', { name: 'Follow +' })).toHaveCount(1);
    await nav(page, 'Following').click(); await expect(row).toHaveCount(0);
    const completed = deletes(page); release(); expect((await completed).status()).toBe(204);
    await expect(row).toHaveCount(0); await page.reload(); await expect(rows(page)).toHaveCount(1);
  } finally { release(); }
});

test('unfollow releases a slot at three and replacement persists without provider work', async ({ page, request }) => {
  await seed(page, 3);
  const beforeProvider = await providerCount(request);
  const row = followingRow(page, 'Tom Holland'); await row.hover();
  const completed = deletes(page); await row.getByRole('button').click(); expect((await completed).status()).toBe(204);
  await nav(page, 'Search').click(); await search(page);
  const afterSearch = await providerCount(request);
  await save(page, 3);
  await nav(page, 'Following').click(); await expect(rows(page)).toHaveCount(3);
  await expect(followingRow(page, 'Tom Cruise')).toBeVisible();
  await expect(followingRow(page, 'Tom Holland')).toHaveCount(0);
  await page.reload(); await expect(rows(page)).toHaveCount(3);
  expect(await providerCount(request)).toBe(afterSearch);
  // Routed/browser-cache settings can affect the second search; mutations cannot.
  expect(afterSearch).toBeGreaterThanOrEqual(beforeProvider);
});

test('unfollow failure at cap restores original and retains replacement until backend rejects it', async ({ page }) => {
  await seed(page, 3);
  let releaseDelete!: () => void, releasePost!: () => void, posting!: () => void;
  const deletion = new Promise<void>(resolve => { releaseDelete = resolve; });
  const post = new Promise<void>(resolve => { releasePost = resolve; });
  const sending = new Promise<void>(resolve => { posting = resolve; });
  await page.route('**/api/v1/following', async route => {
    if (route.request().method() === 'DELETE') { await deletion; return route.fulfill({ status: 500, body: '', headers: { 'Cache-Control': 'no-store' } }); }
    if (route.request().method() === 'POST') {
      const response = await route.fetch(); expect(response.status()).toBe(500); posting();
      await post; return route.fulfill({ response });
    }
    return route.continue();
  });
  try {
    const row = followingRow(page, 'Tom Holland'); await row.hover(); await row.getByRole('button').click(); await expect(row).toHaveCount(0);
    await nav(page, 'Search').click(); await search(page);
    await searchRow(page, 3).hover(); await searchRow(page, 3).getByRole('button', { name: 'Follow +' }).click();
    await expect(searchRow(page, 3).getByRole('status')).toHaveCount(1);
    releaseDelete(); await sending;
    await expect(searchRow(page, 1).getByRole('status')).toHaveCount(1);
    await expect(searchRow(page, 3).getByRole('status')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Follow +' })).toHaveCount(0);
    releasePost(); await expect(searchRow(page, 3).getByRole('status')).toHaveCount(0);
    await nav(page, 'Following').click(); await expect(rows(page)).toHaveCount(3);
    await expect(followingRow(page, 'Tom Holland')).toBeVisible();
    await expect(followingRow(page, 'Tom Cruise')).toHaveCount(0);
  } finally { releaseDelete(); releasePost(); }
});

test('unfollow real touch reveals, switches, dismisses, cancels and navigates without interception', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:18080', hasTouch: true, viewport: { width: 375, height: 700 } });
  const page = await context.newPage();
  let removals = 0;
  page.on('request', r => { if (r.url().endsWith('/following') && r.method() === 'DELETE') removals++; });
  try {
    await seed(page, 3);
    const first = followingRow(page, 'Tom Hanks'), button = first.getByRole('button', { name: 'Unfollow' });
    const bounds = await button.boundingBox(); expect(bounds).not.toBeNull();
    await page.touchscreen.tap(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2);
    await expect(button).toHaveCSS('opacity', '1'); expect(removals).toBe(0);
    const other = followingRow(page, 'Tom Holland'); await other.getByText('Tom Holland', { exact: true }).tap();
    await expect(button).toHaveCSS('opacity', '0'); await expect(other.getByRole('button')).toHaveCSS('opacity', '1');
    await page.getByText('Lumière', { exact: true }).tap(); await expect(other.getByRole('button')).toHaveCSS('opacity', '0');
    const session = await context.newCDPSession(page);
    const rowBounds = await first.boundingBox(); const x = rowBounds!.x + 20, y = rowBounds!.y + 20;
    for (const cancel of [false, true]) {
      await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
      if (!cancel) await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: y - 80 }] });
      await session.send('Input.dispatchTouchEvent', { type: cancel ? 'touchCancel' : 'touchEnd', touchPoints: [] });
    }
    expect(removals).toBe(0); await expect(button).toHaveCSS('opacity', '0');
    await first.getByText('Tom Hanks', { exact: true }).tap(); await expect(button).toHaveCSS('opacity', '1');
    const completed = deletes(page); await button.tap(); expect((await completed).status()).toBe(204);
    await expect(first).toHaveCount(0); expect(removals).toBe(1);
    await other.getByText('Tom Holland', { exact: true }).tap();
    await nav(page, 'Search').tap(); await expect(page).toHaveURL(/\/$/);
    await nav(page, 'Following').tap(); await expect(other.getByRole('button')).toHaveCSS('opacity', '0');
  } finally { await context.close(); }
});

test('unfollow touch selection survives an ordinary identical refresh', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:18080', hasTouch: true, viewport: { width: 375, height: 700 } });
  const page = await context.newPage();
  let release!: () => void, entered!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const waiting = new Promise<void>(resolve => { entered = resolve; });
  try {
    await seed(page, 2); await nav(page, 'Search').tap();
    await page.route('**/api/v1/following', async route => {
      if (route.request().method() !== 'GET') return route.continue();
      entered(); await gate; await route.continue();
    });
    await nav(page, 'Following').tap(); await waiting;
    const row = followingRow(page, 'Tom Holland'), action = row.getByRole('button');
    await row.getByText('Tom Holland', { exact: true }).tap(); await expect(action).toHaveCSS('opacity', '1');
    const refreshed = page.waitForResponse(r => r.url().endsWith('/following') && r.request().method() === 'GET');
    release(); expect((await refreshed).status()).toBe(200);
    await expect(action).toHaveCSS('opacity', '1');
    const completed = deletes(page); await action.tap(); expect((await completed).status()).toBe(204);
    await expect(row).toHaveCount(0);
  } finally { release?.(); await context.close(); }
});

test('unfollow pen taps reveal and submit once, and outside pen dismisses', async ({ page }) => {
  await seed(page, 2);
  let removals = 0;
  page.on('request', r => { if (r.url().endsWith('/following') && r.method() === 'DELETE') removals++; });
  const row = followingRow(page, 'Tom Holland'), name = row.getByText('Tom Holland', { exact: true }), action = row.getByRole('button');
  const pen = { pointerType: 'pen', pointerId: 1, clientX: 20, clientY: 20, isPrimary: true, button: 0, buttons: 1 };
  await name.dispatchEvent('pointerdown', pen); await name.dispatchEvent('pointerup', { ...pen, buttons: 0 });
  await expect(action).toHaveCSS('opacity', '1'); expect(removals).toBe(0);
  await page.getByText('Lumière', { exact: true }).dispatchEvent('pointerdown', pen);
  await expect(action).toHaveCSS('opacity', '0');
  await name.dispatchEvent('pointerdown', pen); await name.dispatchEvent('pointerup', { ...pen, buttons: 0 });
  await expect(action).toHaveCSS('opacity', '1');
  const completed = deletes(page);
  await action.dispatchEvent('pointerdown', pen); await action.dispatchEvent('pointerup', { ...pen, buttons: 0 }); await action.dispatchEvent('click');
  expect((await completed).status()).toBe(204); await expect(row).toHaveCount(0); expect(removals).toBe(1);
});
