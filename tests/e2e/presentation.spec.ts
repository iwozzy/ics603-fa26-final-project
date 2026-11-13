import { test, expect, type Page } from '@playwright/test';

const payload = { results: [
  { id: 1, name: 'With portrait', profile_path: '/broken.jpg', known_for_department: 'Acting', known_for: [{ media_type: 'movie', title: 'A Film' }] },
  { id: 2, name: 'Name only' },
  { id: 3, name: 'Titles only', known_for: [{ media_type: 'tv', name: 'A Series' }] },
  { id: 4, name: 'Department only', known_for_department: 'Directing' },
] };

async function submit(page: Page) {
  await page.getByRole('textbox').fill('People');
  await page.getByRole('textbox').press('Enter');
  await expect(page.getByTestId('person-row')).toHaveCount(4);
}

test.beforeEach(async ({ request }) => {
  await request.post('/__test/reset', { data: { People: { payload } } });
});

test('portraits fall back, missing secondary text has no separators, and keyboard focus reveals disabled Follow', async ({ page }) => {
  await page.route('https://image.tmdb.org/**', route => route.fulfill({ status: 404, body: '' }));
  await page.goto('/');
  await submit(page);
  const rows = page.getByTestId('person-row');
  await expect(page.getByRole('img', { name: 'Portrait unavailable for With portrait' })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Portrait unavailable for Name only' })).toBeVisible();
  await expect(rows.nth(1)).toHaveText('Name onlyFollow +');
  await expect(rows.nth(2)).toHaveText('Titles onlyA SeriesFollow +');
  await expect(rows.nth(3)).toHaveText('Department onlyDirectingFollow +');
  await expect(rows.nth(0).getByTestId('follow-container')).toHaveCSS('opacity', '0');
  await rows.nth(0).hover();
  await expect(rows.nth(0).getByTestId('follow-container')).toHaveCSS('opacity', '1');
  await page.getByRole('textbox').hover();
  await rows.nth(1).focus();
  await expect(rows.nth(1)).toBeFocused();
  await expect(rows.nth(1).getByTestId('follow-container')).toHaveCSS('opacity', '1');
  await expect(rows.nth(1).getByRole('button', { name: 'Follow Name only' })).toBeDisabled();
  await page.keyboard.press('Enter');
  expect(new URL(page.url()).pathname).toBe('/');
  await expect(rows).toHaveCount(4);
  await page.screenshot({ path: '/private/tmp/wayfinder-results-wide.png' });
});

test('touch reveal toggles, moves, and resets at a narrow viewport', async ({ browser, request }) => {
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, hasTouch: true, isMobile: true });
  const page = await context.newPage();
  await page.route('https://image.tmdb.org/**', route => route.fulfill({ status: 404, body: '' }));
  await page.goto('/');
  await page.screenshot({ path: '/private/tmp/wayfinder-initial-narrow.png' });
  await submit(page);
  const rows = page.getByTestId('person-row');
  const follow = (index: number) => rows.nth(index).getByTestId('follow-container');
  await expect(follow(0)).toHaveCSS('opacity', '0');
  await rows.nth(0).tap();
  await expect(follow(0)).toHaveCSS('opacity', '1');
  await rows.nth(0).tap();
  await expect(follow(0)).toHaveCSS('opacity', '0');
  await rows.nth(0).tap();
  await rows.nth(1).tap();
  await expect(follow(0)).toHaveCSS('opacity', '0');
  await expect(follow(1)).toHaveCSS('opacity', '1');
  await expect(rows.nth(1).getByRole('button')).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '/private/tmp/wayfinder-results-narrow.png' });
  await page.getByRole('textbox').fill('Refresh');
  await page.getByRole('textbox').press('Enter');
  await expect(rows).toHaveCount(1);
  await expect(follow(0)).toHaveCSS('opacity', '0');
  expect(new URL(page.url()).search).toBe('');
  expect(await (await request.get('/__test/attempts')).json()).toHaveLength(2);
  await context.close();
});

for (const body of ['{}', '{"results":[{"name":"incomplete"}]}', '{"results":null}', 'not JSON']) {
  test(`invalid application response is silent: ${body}`, async ({ page }) => {
    await page.route('**/api/people/search?*', route => route.fulfill({ status: 200, contentType: 'application/json', body }));
    await page.goto('/');
    await page.getByRole('textbox').fill('Invalid');
    await page.getByRole('textbox').press('Enter');
    await expect(page.getByText('Example searches:')).toHaveCount(0);
    await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
    await expect(page.getByTestId('results')).toBeEmpty();
    await expect(page.getByRole('textbox')).toHaveValue('Invalid');
  });
}

test('browser network failure is silent and a resubmission can recover', async ({ page, request }) => {
  await page.route('**/api/people/search?*', route => route.abort('failed'));
  await page.goto('/');
  await page.getByRole('textbox').fill('Offline');
  await page.getByRole('textbox').press('Enter');
  await expect(page.getByText('Example searches:')).toHaveCount(0);
  await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
  await expect(page.getByTestId('results')).toBeEmpty();
  await expect(page.getByRole('textbox')).toHaveValue('Offline');
  expect(await (await request.get('/__test/attempts')).json()).toEqual([]);
  await page.unroute('**/api/people/search?*');
  await page.getByRole('textbox').press('Enter');
  await expect(page.getByTestId('person-row')).toHaveCount(1);
});

test('the browser deadline stops waiting when transport never completes', async ({ page }) => {
  await page.route('**/api/people/search?*', async route => {
    await new Promise(resolve => setTimeout(resolve, 9000));
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"results":[]}' }).catch(() => {});
  });
  await page.goto('/');
  await page.getByRole('textbox').fill('Stalled');
  await page.getByRole('textbox').press('Enter');
  await expect(page.getByLabel('Searching', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0, { timeout: 8500 });
  await expect(page.getByTestId('results')).toBeEmpty();
  await expect(page.getByRole('textbox')).toHaveValue('Stalled');
});
