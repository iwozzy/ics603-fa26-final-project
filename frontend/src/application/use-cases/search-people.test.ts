import { SearchPeople } from './search-people';
import { InvalidQuery } from '../../domain/errors';
test('validates before delegating and preserves query', async () => {
  const search = jest.fn(async (query: string) => ({ query, people: [] }));
  const useCase = new SearchPeople({ search });
  const signal = new AbortController().signal;
  await expect(useCase.execute('  ', signal)).rejects.toBeInstanceOf(InvalidQuery);
  await expect(useCase.execute('😀'.repeat(201), signal)).rejects.toBeInstanceOf(InvalidQuery);
  expect(search).not.toHaveBeenCalled();
  await expect(useCase.execute(' 李😀 ', signal)).resolves.toEqual({ query: '李😀', people: [] });
  expect(search).toHaveBeenCalledWith('李😀', signal);
});
