import { fireEvent, render, screen } from '@testing-library/react-native';
import { MovieRow } from './MovieRow';

const movie = { id: 11, title: 'Bullet Train', releaseDate: '2022-08-03', overview: 'On the train.', posterImageUrl: null };

test('shows public movie text and reserves a decorative poster slot on image failure', async () => {
  const view = await render(<MovieRow movie={movie} />);
  expect(screen.getByRole('header', { name: 'Bullet Train' })).toBeTruthy();
  expect(screen.getByText('August, 2022')).toBeTruthy();
  expect(screen.getByText('On the train.')).toBeTruthy();
  expect(screen.getByTestId('poster-slot', { includeHiddenElements: true })).toHaveStyle({ width: 112, height: 160 });
  await view.rerender(<MovieRow movie={{ ...movie, overview: null, posterImageUrl: 'https://example.invalid/image.jpg' }} />);
  expect(screen.queryByText('On the train.')).toBeNull();
  await fireEvent(screen.container.queryAll(node => node.type === 'Image')[0], 'error');
  expect(screen.container.queryAll(node => node.type === 'Image')).toHaveLength(0);
  expect(screen.getByTestId('poster-slot', { includeHiddenElements: true })).toHaveStyle({ width: 112, height: 160 });
});
