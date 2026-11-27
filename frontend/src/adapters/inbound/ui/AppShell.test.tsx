import { render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import { AppShell } from './AppShell';
jest.mock('expo-router', () => ({
  usePathname: () => '/timeline',
  Link: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => {
    const { Text } = jest.requireActual<typeof import('react-native')>('react-native');
    return <Text {...props} accessibilityRole="link" {...{ href }}>{children}</Text>;
  },
}));
test('shell always renders three navigation destinations in order and highlights current route', async () => {
  await render(<AppShell><Text>Content</Text></AppShell>);
  expect(screen.getByText('Lumière')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Search' }).props.href).toBe('/');
  expect(screen.getByRole('link', { name: 'Following' }).props.href).toBe('/following');
  expect(screen.getAllByRole('link').map(link => link.props.href)).toEqual(['/', '/timeline', '/following']);
  expect(screen.getByRole('link', { name: 'Timeline' }).props['aria-current']).toBe('page');
  expect(screen.getByRole('link', { name: 'Following' }).props['aria-current']).toBeUndefined();
  expect(screen.getByText('Content')).toBeTruthy();
});
