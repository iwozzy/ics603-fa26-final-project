import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { PersonSummary } from '../src/application/search-people';

import { SearchScreen } from '../src/adapters/ui/SearchScreen';

test('initial screen offers a named search form, three examples, and disabled Movies without requesting', async () => {
  const search = jest.fn();
  await render(<SearchScreen search={search} />);
  expect(
    screen.getByRole('heading', { name: 'Cast & Crew' }),
  ).toBeOnTheScreen();
  expect(screen.getByLabelText('Search people')).toHaveDisplayValue('');
  expect(screen.getByRole('button', { name: 'Search' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Movies' })).toBeDisabled();
  for (const name of [
    'Timothée Chalamet',
    'Hayao Miyazaki',
    'Autumn Durald Arkapaw',
  ]) {
    expect(
      screen.getByRole('button', { name: `Search for ${name}` }),
    ).toBeOnTheScreen();
  }
  expect(search).not.toHaveBeenCalled();
});

test('uses the wireframe placeholder with a muted color', async () => {
  await render(<SearchScreen search={jest.fn()} />);
  const input = screen.getByPlaceholderText(
    'Search for actors, directors, or creative team to follow',
  );
  expect(input).toHaveProp('placeholderTextColor', '#64748b');
});

test('search uses a decorative magnifier and retains an accessible button name', async () => {
  await render(<SearchScreen search={jest.fn()} />);
  expect(screen.getByRole('button', { name: 'Search' })).toBeEnabled();
  expect(screen.queryByText('Search')).not.toBeOnTheScreen();
  expect(
    screen.getByTestId('search-icon', { includeHiddenElements: true }),
  ).toBeOnTheScreen();
});

test('loading retains examples, announces searching, and renders result hints when ready', async () => {
  let resolve!: (people: PersonSummary[]) => void;
  const search = jest.fn(
    () =>
      new Promise<PersonSummary[]>((done) => {
        resolve = done;
      }),
  );
  await render(<SearchScreen search={search} />);
  await fireEvent.press(
    screen.getByRole('button', { name: 'Search for Hayao Miyazaki' }),
  );
  expect(screen.getByLabelText('Searching')).toBeOnTheScreen();
  expect(screen.getByText('Try a search')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Search' })).toBeEnabled();
  await act(async () =>
    resolve([
      {
        name: 'Hayao',
        portraitUrl: null,
        department: 'Directing',
        knownFor: ['Spirited Away'],
      },
    ]),
  );
  expect(screen.queryByLabelText('Searching')).not.toBeOnTheScreen();
  expect(screen.queryByText('Try a search')).not.toBeOnTheScreen();
  expect(screen.getByText('Hayao')).toBeOnTheScreen();
  expect(screen.getByText('Directing • Spirited Away')).toBeOnTheScreen();
  expect(screen.getByRole('button', { name: 'Follow Hayao' })).toBeDisabled();
  expect(screen.getByText('1 person found')).toBeOnTheScreen();
});

test.each(['enter', 'button', 'example'])(
  '%s submits, while typing alone does not',
  async (trigger) => {
    const search = jest.fn().mockResolvedValue([]);
    await render(<SearchScreen search={search} />);
    const input = screen.getByLabelText('Search people');
    await fireEvent.changeText(input, '  Timothée  ');
    expect(search).not.toHaveBeenCalled();
    if (trigger === 'enter') await fireEvent(input, 'submitEditing');
    if (trigger === 'button')
      await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
    if (trigger === 'example')
      await fireEvent.press(
        screen.getByRole('button', { name: 'Search for Hayao Miyazaki' }),
      );
    expect(search).toHaveBeenCalledTimes(1);
    expect(search).toHaveBeenCalledWith(
      trigger === 'example' ? 'Hayao Miyazaki' : 'Timothée',
    );
    if (trigger === 'example')
      expect(input).toHaveDisplayValue('Hayao Miyazaki');
  },
);

test.each(['empty', 'failure'])(
  '%s completion restores examples without an error or retry control',
  async (outcome) => {
    const search = jest
      .fn()
      .mockResolvedValueOnce([
        { name: 'Person', portraitUrl: null, department: null, knownFor: [] },
      ]);
    if (outcome === 'empty') search.mockResolvedValueOnce([]);
    else search.mockRejectedValueOnce(new Error('private details'));
    const log = jest.fn();
    await render(<SearchScreen search={search} logFailure={log} />);
    await fireEvent.changeText(
      screen.getByLabelText('Search people'),
      'Person',
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
    expect(screen.getByText('Person')).toBeOnTheScreen();
    await fireEvent.changeText(screen.getByLabelText('Search people'), 'Next');
    await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
    expect(screen.getByText('Try a search')).toBeOnTheScreen();
    expect(screen.queryByText('Person')).not.toBeOnTheScreen();
    expect(
      screen.queryByText(/retry|error|failed|private details/i),
    ).not.toBeOnTheScreen();
    expect(screen.queryByLabelText('Searching')).not.toBeOnTheScreen();
    expect(search).toHaveBeenCalledTimes(2);
    expect(log).toHaveBeenCalledTimes(outcome === 'failure' ? 1 : 0);
  },
);

test.each(['𠮷'.repeat(101)])(
  'invalid submission leaves results displayed without a validation message',
  async (draft) => {
    const search = jest
      .fn()
      .mockResolvedValue([
        { name: 'Person', portraitUrl: null, department: null, knownFor: [] },
      ]);
    await render(<SearchScreen search={search} />);
    await fireEvent.changeText(
      screen.getByLabelText('Search people'),
      'Person',
    );
    await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
    await fireEvent.changeText(screen.getByLabelText('Search people'), draft);
    await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
    expect(screen.getByText('Person')).toBeOnTheScreen();
    expect(
      screen.queryByText(/invalid|too long|required|error/i),
    ).not.toBeOnTheScreen();
    expect(search).toHaveBeenCalledTimes(1);
  },
);

test.each(['enter', 'button'])(
  '%s with a blank draft restores examples without requesting',
  async (trigger) => {
    const search = jest
      .fn()
      .mockResolvedValue([
        { name: 'Person', portraitUrl: null, department: null, knownFor: [] },
      ]);
    await render(<SearchScreen search={search} />);
    for (const draft of ['', '  ']) {
      const input = screen.getByLabelText('Search people');
      await fireEvent.changeText(input, 'Person');
      await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
      expect(screen.getByText('Person')).toBeOnTheScreen();
      const calls = search.mock.calls.length;
      await fireEvent.changeText(input, draft);
      if (trigger === 'enter') await fireEvent(input, 'submitEditing');
      else
        await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
      expect(screen.getByText('Try a search')).toBeOnTheScreen();
      expect(screen.queryByText('Person')).not.toBeOnTheScreen();
      expect(screen.queryByLabelText('Searching')).not.toBeOnTheScreen();
      expect(input).toHaveDisplayValue('');
      expect(search).toHaveBeenCalledTimes(calls);
    }
  },
);
