import { expect, test, type Page } from '@playwright/test';
import baseline from '../../docs/samples/api/tmdb/v3/search/person.json';

const api = 'http://127.0.0.1:8000';

async function submit(page: Page, query: string) {
  await page.getByLabel('Search people').fill(query);
  await page.getByLabel('Search people').press('Enter');
}

test.beforeEach(async ({ page, request }) => {
  await request.post(`${api}/__test__/reset`);
  await page.route('https://image.tmdb.org/**', (route) => route.abort());
  await page.goto('/');
});

test('button search displays the first seven in order and examples and repeated searches work', async ({
  page,
  request,
}) => {
  const input = page.getByLabel('Search people');
  await input.fill(' Tom ');
  expect(await (await request.get(`${api}/__test__/requests`)).json()).toEqual(
    [],
  );
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  const follows = page.getByRole('button', { name: /^Follow / });
  await expect(follows).toHaveCount(7);
  expect(
    await follows.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute('aria-label')),
    ),
  ).toEqual(
    baseline.results.slice(0, 7).map((person) => `Follow ${person.name}`),
  );
  await expect(
    page.getByText('Acting • Alien, Top Gun, Contact', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/pagination|more results|limit|next page/i),
  ).toHaveCount(0);
  const repeated = page.waitForResponse((response) =>
    response.url().includes('/api/people/search'),
  );
  await input.press('Enter');
  await repeated;
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  await submit(page, 'Empty');
  const example = page.getByRole('button', {
    name: 'Search for Hayao Miyazaki',
  });
  await expect(example).toBeVisible();
  await example.focus();
  await example.press('Enter');
  await expect(input).toHaveValue('Hayao Miyazaki');
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
});

test('Follow is visible only on row hover and future controls cannot receive keyboard focus', async ({
  page,
}) => {
  await submit(page, 'Tom');
  const follow = page.getByRole('button', { name: 'Follow Tom Skerritt' });
  await expect(follow).toBeDisabled();
  await expect(follow).toHaveCSS('opacity', '0');
  await page.getByText('Tom Skerritt', { exact: true }).hover();
  await expect(follow).toHaveCSS('opacity', '1');
  await page.getByRole('heading', { name: 'Cast & Crew' }).hover();
  await expect(follow).toHaveCSS('opacity', '0');
  await page.getByLabel('Search people').focus();
  await page.keyboard.press('Tab');
  await expect(
    page.getByRole('button', { name: 'Search', exact: true }),
  ).toBeFocused();
  const inputOutline = await page
    .getByLabel('Search people')
    .evaluate((node) => {
      (node as HTMLElement).focus();
      const css = getComputedStyle(node);
      return { width: css.outlineWidth, style: css.outlineStyle };
    });
  expect(inputOutline.style).not.toBe('none');
  expect(inputOutline.width).not.toBe('0px');
});

for (const query of ['Empty', 'Failure', 'Unusable']) {
  test(`${query} restores examples without a visible error or retry`, async ({
    page,
  }) => {
    const failures: string[] = [];
    page.on('console', (message) => {
      if (message.text() === 'People search failed')
        failures.push(message.text());
    });
    await submit(page, 'Tom');
    await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
    await submit(page, query);
    await expect(page.getByText('Try a search')).toBeVisible();
    await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
    await expect(page.getByText(/retry|unable|failed|error/i)).toHaveCount(0);
    expect(failures).toHaveLength(query === 'Empty' ? 0 : 1);
    await submit(page, 'Tom');
    await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  });
}

for (const query of ['Slow success', 'Slow failure']) {
  test(`${query} cannot override the latest result`, async ({
    page,
    request,
  }) => {
    await submit(page, query);
    await expect(page.getByLabel('Searching', { exact: true })).toBeVisible();
    await expect(page.getByText('Try a search')).toBeVisible();
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    expect(
      await (await request.get(`${api}/__test__/requests`)).json(),
    ).toEqual([query]);
    await submit(page, 'Latest');
    await expect(
      page.getByText('Latest result', { exact: true }),
    ).toBeVisible();
    const oldCompletion = page.waitForResponse(
      (response) => new URL(response.url()).searchParams.get('query') === query,
    );
    await request.post(
      `${api}/__test__/release?query=${encodeURIComponent(query)}`,
    );
    await oldCompletion;
    await expect(
      page.getByText('Latest result', { exact: true }),
    ).toBeVisible();
    await expect(page.getByText('Older result', { exact: true })).toHaveCount(
      0,
    );
    await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
  });
}

test('narrow layout wraps long names and titles, preserves the form position, and renders fallback portraits', async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 812 });
  const formBefore = await page.getByLabel('Search people').boundingBox();
  await submit(page, 'Long');
  await expect(page.getByText('A'.repeat(180), { exact: true })).toBeVisible();
  await expect(
    page.getByText('Unbroken'.repeat(60), { exact: true }),
  ).toBeVisible();
  const formAfter = await page.getByLabel('Search people').boundingBox();
  expect(formAfter?.y).toBe(formBefore?.y);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(page.getByTestId('portrait-fallback')).toBeVisible();
  await submit(page, 'Tom');
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  await expect(page.getByTestId('portrait-fallback')).toHaveCount(7);
});

test('overlong submissions preserve current results without a request or message', async ({
  page,
  request,
}) => {
  await submit(page, 'Tom');
  await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
  for (const invalid of ['𠮷'.repeat(101)]) {
    await submit(page, invalid);
    await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
    await expect(page.getByText(/invalid|required|too long/i)).toHaveCount(0);
  }
  expect(await (await request.get(`${api}/__test__/requests`)).json()).toEqual([
    'Tom',
  ]);
});

test('blank submissions restore examples without sending another request', async ({
  page,
  request,
}) => {
  for (const trigger of ['enter', 'button']) {
    await submit(page, 'Tom');
    await expect(page.getByText('Tom Skerritt', { exact: true })).toBeVisible();
    await page
      .getByLabel('Search people')
      .fill(trigger === 'enter' ? '' : '  ');
    if (trigger === 'enter')
      await page.getByLabel('Search people').press('Enter');
    else
      await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page.getByText('Try a search')).toBeVisible();
    await expect(
      page.getByRole('button', { name: /^Search for / }),
    ).toHaveCount(3);
    await expect(page.getByText('Tom Skerritt', { exact: true })).toHaveCount(
      0,
    );
    await expect(page.getByLabel('Search people')).toHaveValue('');
    await expect(page.getByLabel('Searching', { exact: true })).toHaveCount(0);
  }
  expect(await (await request.get(`${api}/__test__/requests`)).json()).toEqual([
    'Tom',
    'Tom',
  ]);
});

test('search presentation matches the wireframe and distinguishes placeholder from entered text', async ({
  page,
}) => {
  const input = page.getByPlaceholder(
    'Search for actors, directors, or creative team to follow',
  );
  await expect(input).toBeVisible();
  const colors = await input.evaluate((node) => ({
    placeholder: getComputedStyle(node, '::placeholder').color,
    entered: getComputedStyle(node).color,
  }));
  expect(colors.placeholder).not.toBe(colors.entered);
  await input.fill('Tom');
  expect(await input.evaluate((node) => getComputedStyle(node).color)).toBe(
    colors.entered,
  );
  const button = page.getByRole('button', { name: 'Search', exact: true });
  await expect(button).toHaveText('');
  await expect(button.locator('svg')).toHaveCount(1);
  const shape = await button.evaluate((node) => {
    const bounds = node.getBoundingClientRect();
    return {
      width: bounds.width,
      height: bounds.height,
      radius: parseFloat(getComputedStyle(node).borderRadius),
    };
  });
  expect(shape.width).toBe(shape.height);
  expect(shape.radius).toBeGreaterThanOrEqual(shape.width / 2);
});

test('a narrow browser can scroll to the final result', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 600 });
  await submit(page, 'Tom');
  const last = page.getByText(baseline.results[6].name, { exact: true });
  await expect(last).toBeVisible();
  await page.mouse.move(180, 450);
  await page.mouse.wheel(0, 1200);
  await expect(last).toBeInViewport();
});
