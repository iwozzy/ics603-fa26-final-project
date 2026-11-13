/** Minimal opt-in live check; logs counts/outcomes only, never provider content. */
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

if (!process.env.TMDB_API_READ_ACCESS_TOKEN)
  throw new Error('Set TMDB_API_READ_ACCESS_TOKEN');
const backendDirectory = fileURLToPath(
  new URL('../../backend/', import.meta.url),
);
const server = spawn(
  'uv',
  [
    'run',
    'uvicorn',
    'lumiere.runtime:create_app',
    '--factory',
    '--app-dir',
    '.',
    '--host',
    '127.0.0.1',
    '--port',
    '8767',
    '--no-access-log',
  ],
  {
    cwd: backendDirectory,
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
  },
);
let output = '';
server.stdout.on('data', (chunk) => {
  output += chunk;
});
server.stderr.on('data', (chunk) => {
  output += chunk;
});
let browser;
try {
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null) throw new Error('API failed to start');
    try {
      if ((await fetch('http://127.0.0.1:8767')).ok) break;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8767');
  const responsePromise = page.waitForResponse((r) =>
    r.url().includes('/api/people/search'),
  );
  await page.getByText('Timothée Chalamet (Actor)', { exact: true }).click();
  const response = await responsePromise;
  assert.equal(response.status(), 200);
  assert.equal(response.headers()['cache-control'], 'private, max-age=60');
  await page.getByTestId('person-row').first().waitFor();
  const data = await response.json();
  assert.ok(data.results.length > 0 && data.results.length <= 7);
  const portrait = data.results.find((row) => row.portrait_url)?.portrait_url;
  assert.ok(
    portrait?.startsWith('https://image.tmdb.org/t/p/w180_and_h180_face/'),
  );
  const transform = await page.evaluate(async (url) => {
    const image = new Image();
    image.src = url;
    await image.decode();
    return { width: image.naturalWidth, height: image.naturalHeight };
  }, portrait);
  assert.deepEqual(transform, { width: 180, height: 180 });
  const cache = await page.evaluate(async (uri) => {
    const repeated = await fetch(uri);
    await repeated.json();
    return performance.getEntriesByName(uri).map((entry) => entry.transferSize);
  }, response.url());
  assert.equal(cache.length, 2);
  assert.ok(cache[0] > 0);
  assert.equal(cache[1], 0);
  // Test actual runtime output, including all Uvicorn/HTTP client output.
  assert.ok(
    !output.includes('Timoth') &&
      !output.includes('query=') &&
      !output.includes(portrait),
  );
  assert.ok(!output.includes(process.env.TMDB_API_READ_ACCESS_TOKEN));
  const telemetry = output
    .split('\n')
    .filter((line) => line.startsWith('{'))
    .map((line) => JSON.parse(line));
  assert.equal(telemetry.length, 1);
  assert.equal(telemetry[0].provider_attempts, 1);
  assert.ok(['success', 'empty'].includes(telemetry[0].outcome));
  console.log(
    JSON.stringify({
      liveSearch: 'passed',
      results: data.results.length,
      portraitTransform: transform,
      cacheTransferBytes: cache,
      providerAttempts: 1,
      runtimeLogContentExcluded: true,
    }),
  );
} finally {
  await browser?.close();
  server.kill('SIGTERM');
}
