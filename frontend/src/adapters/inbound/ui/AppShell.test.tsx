import { render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import { AppShell } from './AppShell';
jest.mock('expo-router', () => ({
  usePathname: () => '/following',
  Link: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => {
    const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
    return <Text {...props} accessibilityRole="link" {...{ href }}>{children}</Text>;
  },
}));
test('shell always renders both navigation destinations and highlights current route', async () => {
  await render(<AppShell><Text>Content</Text></AppShell>);
  expect(screen.getByText('Lumière')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Search' }).props.href).toBe('/');
  expect(screen.getByRole('link', { name: 'Following' }).props.href).toBe('/following');
  expect(screen.getByRole('link', { name: 'Following' }).props['aria-current']).toBe('page');
  expect(screen.getByText('Content')).toBeTruthy();
});
