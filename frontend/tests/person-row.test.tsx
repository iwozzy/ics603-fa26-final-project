import { fireEvent, render, screen } from '@testing-library/react-native';

import { PersonRow } from '../src/adapters/ui/PersonRow';
import type { PersonSummary } from '../src/application/search-people';

const person: PersonSummary = {
  name: 'A Person',
  portraitUrl: null,
  department: null,
  knownFor: [],
};

test('missing portraits use a decorative person fallback', async () => {
  await render(<PersonRow person={person} />);
  expect(
    screen.getByTestId('portrait-fallback', { includeHiddenElements: true }),
  ).toBeOnTheScreen();
  expect(screen.queryByRole('image')).not.toBeOnTheScreen();
  expect(screen.getByText('A Person')).toBeOnTheScreen();
});

test('portrait download failures fall back without removing result hints', async () => {
  await render(
    <PersonRow
      person={{
        ...person,
        portraitUrl: 'https://image.tmdb.org/portrait.jpg',
        knownFor: ['Movie'],
      }}
    />,
  );
  const image = screen.getByTestId('portrait', { includeHiddenElements: true });
  expect(image).toHaveProp('source', {
    uri: 'https://image.tmdb.org/portrait.jpg',
  });
  expect(screen.queryByRole('image')).not.toBeOnTheScreen();
  await fireEvent(image, 'error', {
    nativeEvent: { error: 'download failure' },
  });
  expect(
    screen.getByTestId('portrait-fallback', { includeHiddenElements: true }),
  ).toBeOnTheScreen();
  expect(screen.getByText('Movie')).toBeOnTheScreen();
});

test.each([
  [null, [], null],
  ['Acting', [], 'Acting'],
  [null, ['Show'], 'Show'],
  ['Directing', ['One', 'Two', 'Three', 'Four'], 'Directing • One, Two, Three'],
] as const)(
  'omits empty hints and separators: %p %p',
  async (department, knownFor, text) => {
    await render(
      <PersonRow person={{ ...person, department, knownFor: [...knownFor] }} />,
    );
    if (text) expect(screen.getByText(text)).toBeOnTheScreen();
    expect(screen.queryByText('Four')).not.toBeOnTheScreen();
    expect(screen.queryByText(/^\s*•|•\s*$/)).not.toBeOnTheScreen();
    expect(
      screen.getByRole('button', { name: 'Follow A Person' }),
    ).toBeDisabled();
  },
);
