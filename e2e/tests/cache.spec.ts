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

test('test_cache_expires_after_10_seconds @cache-expiry', async ({ page, request }) => {
  test.setTimeout(40000);
  await page.goto('/'); const first = await search(page);
  expect(first.headers()['cache-control']).toBe('private, max-age=10');
  expect(await counts(request)).toBe(1);
  await search(page);
  expect(await counts(request)).toBe(1);
  await new Promise(resolve => setTimeout(resolve, 12000));
  await search(page); expect(await counts(request)).toBe(2);
});

test('new representation bypasses a fresh legacy response and remains cacheable', async ({ page, request }) => {
  const { createServer } = await import('node:http');
  let legacyRequests = 0;
  const legacy = { query: 'Tom', people: [{ name: 'Tom Skerritt', department: 'Acting', profile_image_url: null, known_for: ['Alien'] }] };
  // A normal HTTP proxy seeds the previous release's representation. Browser
  // request routing is deliberately absent so Chromium's real cache stays on.
  const server = createServer(async (incoming, outgoing) => {
    try {
      const path = incoming.url ?? '/';
      const url = new URL(path, 'http://localhost');
      if (url.pathname === '/api/v1/people/search' && !url.searchParams.has('representation')) {
        legacyRequests++;
        outgoing.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'private, max-age=300' });
        outgoing.end(JSON.stringify(legacy));
        return;
      }
      const upstream = await fetch('http://127.0.0.1:18080' + path, {
        method: incoming.method,
        headers: { cookie: incoming.headers.cookie ?? '', 'accept-encoding': 'identity' },
      });
      outgoing.statusCode = upstream.status;
      for (const name of ['content-type', 'cache-control', 'vary', 'etag', 'last-modified']) {
        const value = upstream.headers.get(name);
        if (value) outgoing.setHeader(name, value);
      }
      const cookies = upstream.headers.getSetCookie();
      if (cookies.length) outgoing.setHeader('set-cookie', cookies);
      outgoing.end(Buffer.from(await upstream.arrayBuffer()));
    } catch {
      outgoing.writeHead(502).end();
    }
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('test proxy did not listen');
  try {
    await page.goto(`http://127.0.0.1:${address.port}/`);
    const old = await page.evaluate(async () => (await fetch('/api/v1/people/search?query=Tom')).json());
    expect(old.people[0]).toHaveProperty('department', 'Acting');
    const current = await search(page);
    expect(new URL(current.url()).searchParams.get('representation')).toBe('people-v2');
    expect((await current.json()).people[0]).toMatchObject({ provider: 'tmdb', provider_id: 4139 });
    await search(page);
    expect(await counts(request)).toBe(1);
    await page.evaluate(async () => (await fetch('/api/v1/people/search?query=Tom')).json());
    expect(legacyRequests).toBe(1);
  } finally {
    await page.goto('about:blank');
    server.closeAllConnections();
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
});
