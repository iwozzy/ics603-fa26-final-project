import { act, fireEvent, screen } from '@testing-library/react-native';
import { DeferredRepository, result } from '../../../test-utils/fakes/people-search';
import { renderWithPorts } from '../../../test-utils/renderWithPorts';
import SearchPeopleScreen from './SearchPeopleScreen';
import { PersonRow } from './PersonRow';
const placeholder = 'Search for actors, directors, or creative team to follow';

test('wireframe copy and keyboard/pointer submission without typing dispatch', async () => {
  const repository = new DeferredRepository();
  await renderWithPorts(<SearchPeopleScreen />, repository);
  for (const text of ['Cast & Crew', 'Example searches:', 'Timothée Chalamet (Actor)', 'Hayao Miyazaki (Director, Writer)', 'Autumn Durald Arkapaw (Cinematographer)']) expect(screen.queryByText(text)).not.toBeNull();
  expect(screen.queryByText('Movies')).toBeNull(); expect(screen.queryByText(/Follow/)).toBeNull();
  const input = screen.getByPlaceholderText(placeholder);
  await fireEvent.changeText(input, 'A');
  expect(repository.calls).toHaveLength(0);
  await fireEvent(input, 'submitEditing', { nativeEvent: { isComposing: true } });
  expect(repository.calls).toHaveLength(0);
  await fireEvent(input, 'submitEditing', { nativeEvent: { keyCode: 229 } });
  expect(repository.calls).toHaveLength(0);
  await fireEvent(input, 'submitEditing', { nativeEvent: {} });
  expect(repository.calls).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Search' })).toBeBusy();
  expect(screen.queryByText('Example searches:')).not.toBeNull();
  expect(input.props.editable).not.toBe(false);
  await fireEvent.changeText(input, 'B');
  expect(screen.getByRole('button', { name: 'Search' })).not.toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
  expect(repository.calls.map(call => call.query)).toEqual(['A', 'B']);
  await act(() => repository.calls[1].resolve(result('B')));
  await act(() => repository.calls[0].resolve(result('A')));
  expect(screen.queryByText('B')).not.toBeNull(); expect(screen.queryByText('A')).toBeNull();
  await fireEvent.changeText(input, 'C');
  expect(screen.queryByText('B')).not.toBeNull();
});

test.each(['empty','error'])('completed %s leaves only heading and input', async kind => {
  const repository = new DeferredRepository(); await renderWithPorts(<SearchPeopleScreen />, repository);
  await fireEvent.changeText(screen.getByPlaceholderText(placeholder), 'A');
  await fireEvent.press(screen.getByRole('button', { name: 'Search' }));
  if (kind === 'empty') await act(() => repository.calls[0].resolve({ query: 'A', people: [] })); else await act(() => repository.calls[0].reject(new Error('failure')));
  expect(screen.queryByText('Example searches:')).toBeNull();
  expect(screen.getByRole('button', { name: 'Search' })).not.toBeBusy();
  expect(screen.queryByText(/error|no results|try again|Follow|Movies/i)).toBeNull();
});

test('row limits mixed titles and handles missing or broken images without separators', async () => {
  const repository = new DeferredRepository();
  const person = { name: 'Tom', department: null, profileImageUrl: 'https://images.test/photo.jpg', knownFor: ['Movie', 'TV', 'Third', 'Fourth'] };
  await renderWithPorts(<PersonRow person={person} />, repository);
  expect(screen.queryByText('Movie, TV, Third')).not.toBeNull(); expect(screen.queryByText(/Fourth| · /)).toBeNull();
  await fireEvent(screen.getByLabelText('Tom profile'), 'error');
  expect(screen.queryByLabelText('Tom silhouette')).not.toBeNull();
});
