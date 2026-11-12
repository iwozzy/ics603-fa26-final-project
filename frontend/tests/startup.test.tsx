import { renderRouter, screen } from 'expo-router/testing-library';

test('opens the startup screen at the root route', async () => {
  await renderRouter('./src/app', { initialUrl: '/' });
  expect(screen).toHavePathname('/');
  expect(screen.getByRole('heading', { name: 'Lumiere' })).toBeOnTheScreen();
  expect(screen.getByText('Application scaffold is ready.')).toBeOnTheScreen();
});
