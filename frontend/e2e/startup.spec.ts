import { expect, test } from '@playwright/test';

test('API and Expo Router start without external services', async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const health = await request.get('http://127.0.0.1:8000/health');
  expect(health.ok()).toBe(true);
  expect(await health.json()).toEqual({ status: 'ok' });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Lumiere' })).toBeVisible();
  await expect(page.getByText('Application scaffold is ready.')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Lumiere' })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
