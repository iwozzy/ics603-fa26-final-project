import { expect, test } from '@playwright/test';

const api = 'http://127.0.0.1:8000';

test('initial route has no discovery request and reload discards search state', async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('https://image.tmdb.org/**', (route) => route.abort());
  await request.post(`${api}/__test__/reset`);
  await page.emulateMedia({ colorScheme: 'dark' });
  expect((await request.get(`${api}/health`)).ok()).toBe(true);
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Cast & Crew' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Movies', exact: true }),
  ).toBeDisabled();
  await expect(page.getByRole('button', { name: /^Search for / })).toHaveCount(
    3,
  );
  await expect(page.locator('html')).toHaveClass(/light/);
  expect(await (await request.get(`${api}/__test__/requests`)).json()).toEqual(
    [],
  );
  await page.getByLabel('Search people').fill('Tom');
  expect(await (await request.get(`${api}/__test__/requests`)).json()).toEqual(
    [],
  );
  await page.getByLabel('Search people').press('Enter');
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Search people')).toHaveValue('');
  await expect(page.getByText('Try a search')).toBeVisible();
  await expect(page.getByText('Tom Skerritt', { exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
