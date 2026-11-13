import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request, page }) => {
  await request.post('/__test/reset', { data: {} });
  await page.goto('/');
});

test('typing is separate from submission, and the API renders recognition metadata', async ({ page, request }) => {
  const input = page.getByRole('textbox', { name: 'Search cast and crew' });
  await expect(page.getByRole('button', { name: 'Movies', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeDisabled();
  await expect(page.getByText('Example searches:')).toBeVisible();
  await input.fill('  Tóm  S  ');
  expect(await (await request.get('/__test/attempts')).json()).toEqual([]);
  await input.press('Enter');
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  await expect(page.getByText('Acting • Alien, Picket Fences')).toBeVisible();
  await expect(input).toHaveValue('  Tóm  S  ');
  await expect(page.getByText('Example searches:')).toHaveCount(0);
  expect(await (await request.get('/__test/attempts')).json()).toEqual([{ query: 'Tóm  S', page: '1' }]);
});

test('draft edits and clearing preserve displayed and pending submitted results', async ({ page, request }) => {
  await request.post('/__test/reset', { data: { First: { delay: 0.3 }, Second: { delay: 0.3 } } });
  const input = page.getByRole('textbox', { name: 'Search cast and crew' });
  await input.fill('First');
  await input.press('Enter');
  await expect(page.getByLabel('Searching', { exact: true })).toBeVisible();
  await input.fill('unsubmitted edit');
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  await expect(input).toHaveValue('unsubmitted edit');
  await input.clear();
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeDisabled();
  await input.fill('Second');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('Tom Skerritt', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Searching', { exact: true })).toBeVisible();
  await input.clear();
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  await expect(input).toHaveValue('');
  expect(await (await request.get('/__test/attempts')).json()).toEqual([{ query: 'First', page: '1' }, { query: 'Second', page: '1' }]);
});

for (const [name, role] of [['Timothée Chalamet', 'Actor'], ['Hayao Miyazaki', 'Director, Writer'], ['Autumn Durald Arkapaw', 'Cinematographer']]) {
  test(`example submits only ${name}`, async ({ page, request }) => {
    await page.getByText(`${name} (${role})`, { exact: true }).click();
    await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
    await expect(page.getByRole('textbox')).toHaveValue(name);
    expect(await (await request.get('/__test/attempts')).json()).toEqual([{ query: name, page: '1' }]);
  });
}

test('single character and URL-sensitive names are manually submitted unchanged inside the trim', async ({ page, request }) => {
  const input = page.getByRole('textbox');
  await input.fill('   ');
  await input.press('Enter');
  expect(await (await request.get('/__test/attempts')).json()).toEqual([]);
  for (const name of ['X', '  Zoë & 李  / ? +  ']) {
    await input.fill(name);
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  }
  expect(await (await request.get('/__test/attempts')).json()).toEqual([{ query: 'X', page: '1' }, { query: 'Zoë & 李  / ? +', page: '1' }]);
  expect(new URL(page.url()).search).toBe('');
});

for (const oldStatus of [200, 503]) {
  test(`late ${oldStatus} cannot replace a newer submission even when transport cannot abort`, async ({ page, request }) => {
    // Model an uncancellable platform transport at the external browser boundary.
    await page.addInitScript(() => {
      const original = window.fetch;
      window.fetch = (url, options) => original(url, { ...options, signal: undefined });
    });
    await page.reload();
    await request.post('/__test/reset', { data: {
      Old: { delay: 0.5, status: oldStatus, payload: { results: [{ id: 1, name: 'Old person' }] } },
      Latest: { delay: 0.1, payload: { results: [{ id: 2, name: 'Latest person' }] } },
    } });
    const input = page.getByRole('textbox');
    await input.fill('Old');
    await input.press('Enter');
    await expect.poll(async () => (await (await request.get('/__test/attempts')).json()).length).toBe(1);
    await input.fill('Latest');
    await input.press('Enter');
    await expect(page.getByText('Latest person', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
    // Wait for the known external completion before checking that it did not alter the screen.
    await page.waitForTimeout(600);
    await expect(page.getByText('Latest person', { exact: true })).toBeVisible();
    await expect(page.getByText('Old person', { exact: true })).toHaveCount(0);
    await expect(input).toHaveValue('Latest');
  });
}

test('an old completion cannot stop the latest loading indicator', async ({ page, request }) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = (url, options) => original(url, { ...options, signal: undefined });
  });
  await page.reload();
  await request.post('/__test/reset', { data: { Old: { delay: 0.1 }, Latest: { delay: 0.7 } } });
  const input = page.getByRole('textbox');
  await input.fill('Old');
  await input.press('Enter');
  await expect.poll(async () => (await (await request.get('/__test/attempts')).json()).length).toBe(1);
  await input.fill('Latest');
  await input.press('Enter');
  await page.waitForTimeout(250);
  await expect(page.getByLabel('Searching', { exact: true })).toBeVisible();
  await expect(page.getByTestId('person-row')).toHaveCount(0);
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
});

for (const scenario of [
  { payload: { results: [] } },
  { status: 503 },
  { raw: 'unreadable provider envelope' },
]) {
  test(`empty or failed outcome stays silent and can be explicitly resubmitted: ${JSON.stringify(scenario)}`, async ({ page, request }) => {
    await request.post('/__test/reset', { data: { Silent: scenario } });
    const input = page.getByRole('textbox');
    await input.fill('Silent');
    const responsePromise = page.waitForResponse(r => r.url().includes('/api/people/search'));
    await input.press('Enter');
    await responsePromise;
    await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
    await expect(page.getByTestId('results')).toBeEmpty();
    await expect(page.getByText('Example searches:')).toHaveCount(0);
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(input).toHaveValue('Silent');
    expect(await (await request.get('/__test/attempts')).json()).toHaveLength(1);
    // Failure is no-store. Empty successes may be cached, so retry a new URI.
    await input.fill('Retry');
    await input.press('Enter');
    await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
    expect(await (await request.get('/__test/attempts')).json()).toHaveLength(2);
  });
}

test('a reload discards search state and late pending work', async ({ page, request }) => {
  await request.post('/__test/reset', { data: { Pending: { delay: 0.4 } } });
  await page.getByRole('textbox').fill('Pending');
  await page.getByRole('textbox').press('Enter');
  await expect(page.getByLabel('Searching', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText('Example searches:')).toBeVisible();
  await expect(page.getByRole('textbox')).toHaveValue('');
  await page.waitForTimeout(500);
  await expect(page.getByTestId('results')).toBeEmpty();
  await expect(page.getByText('Example searches:')).toBeVisible();
});

test('browser stores and reuses a fresh successful HTTP response', async ({ page, request }) => {
  const uri = '/api/people/search?query=Cached';
  const result = await page.evaluate(async path => {
    const first = await fetch(path);
    await first.json();
    const second = await fetch(path);
    await second.json();
    return { headers: second.headers.get('cache-control'), transfers: performance.getEntriesByName(new URL(path, location.href).href).map(e => (e as PerformanceResourceTiming).transferSize) };
  }, uri);
  expect(result.headers).toBe('private, max-age=60');
  expect(result.transfers).toHaveLength(2);
  expect(result.transfers[0]).toBeGreaterThan(0);
  expect(result.transfers[1]).toBe(0);
  expect(await (await request.get('/__test/attempts')).json()).toEqual([{ query: 'Cached', page: '1' }]);
});

test('a failed response is not cached and resubmitting the same query can recover', async ({ page, request }) => {
  await request.post('/__test/reset', { data: { Recovery: { status: 503 } } });
  await page.getByRole('textbox').fill('Recovery');
  let completion = page.waitForResponse(r => r.url().includes('/api/people/search'));
  await page.getByRole('textbox').press('Enter');
  const failure = await completion;
  expect(failure.status()).toBe(500);
  expect(failure.headers()['cache-control']).toBe('no-store');
  await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
  expect(await (await request.get('/__test/attempts')).json()).toHaveLength(1);
  await request.post('/__test/reset', { data: {} });
  completion = page.waitForResponse(r => r.url().includes('/api/people/search'));
  await page.getByRole('textbox').press('Enter');
  expect((await completion).status()).toBe(200);
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  expect(await (await request.get('/__test/attempts')).json()).toHaveLength(1);
});
