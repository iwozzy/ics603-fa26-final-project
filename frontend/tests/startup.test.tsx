import { renderRouter, screen } from 'expo-router/testing-library';

test('opens people search at the root route', async () => {
  await renderRouter('./src/app', { initialUrl: '/' });
  expect(screen).toHavePathname('/');
  expect(
    screen.getByRole('heading', { name: 'Cast & Crew' }),
  ).toBeOnTheScreen();
  expect(screen.getByLabelText('Search people')).toHaveDisplayValue('');
  expect(screen.getByText('Try a search')).toBeOnTheScreen();
});
