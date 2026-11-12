import { createPeopleSearch } from '../src/adapters/http/search-people';

test('encodes the query and translates wire summaries into application types', async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      results: [
        {
          name: 'Timothée',
          portrait_url: null,
          department: 'Acting',
          known_for: ['Film'],
        },
      ],
    }),
  });
  const search = createPeopleSearch('http://backend', fetcher);
  expect(await search('Timothée & Other')).toEqual([
    {
      name: 'Timothée',
      portraitUrl: null,
      department: 'Acting',
      knownFor: ['Film'],
    },
  ]);
  expect(fetcher).toHaveBeenCalledTimes(1);
  const [url] = fetcher.mock.calls[0];
  expect(new URL(url).pathname).toBe('/api/people/search');
  expect(new URL(url).searchParams.get('query')).toBe('Timothée & Other');
});

test('classifies HTTP failure without reading the response payload or retrying', async () => {
  const json = jest.fn();
  const fetcher = jest.fn().mockResolvedValue({ ok: false, json });
  await expect(
    createPeopleSearch('http://backend', fetcher)('name'),
  ).rejects.toMatchObject({ kind: 'http', message: 'People search failed' });
  expect(json).not.toHaveBeenCalled();
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test('classifies network and decoding failures safely', async () => {
  const fetcher = jest.fn().mockRejectedValue(new Error('private URL'));
  await expect(
    createPeopleSearch('http://backend', fetcher)('name'),
  ).rejects.toMatchObject({
    kind: 'transport',
    message: 'People search failed',
  });
  fetcher.mockResolvedValueOnce({
    ok: true,
    json: async () => {
      throw new Error('private body');
    },
  });
  await expect(
    createPeopleSearch('http://backend', fetcher)('name'),
  ).rejects.toMatchObject({
    kind: 'transport',
    message: 'People search failed',
  });
});

test.each(['fetch', 'body'])(
  'enforces twelve seconds including a stalled %s and aborts the request',
  async (phase) => {
    jest.useFakeTimers();
    try {
      const never = new Promise(() => {});
      const fetcher = jest
        .fn()
        .mockImplementation(() =>
          phase === 'fetch'
            ? never
            : Promise.resolve({ ok: true, json: () => never }),
        );
      const pending = createPeopleSearch('http://backend', fetcher)('name');
      const rejected = expect(pending).rejects.toMatchObject({
        kind: 'timeout',
      });
      const signal = fetcher.mock.calls[0][1]?.signal;
      expect(signal).toBeDefined();
      await jest.advanceTimersByTimeAsync(11_999);
      expect(signal.aborted).toBe(false);
      await jest.advanceTimersByTimeAsync(1);
      expect(signal.aborted).toBe(true);
      await rejected;
      expect(fetcher).toHaveBeenCalledTimes(1);
      expect(jest.getTimerCount()).toBe(0);
    } finally {
      jest.useRealTimers();
    }
  },
);

test('clears the deadline after a successful response', async () => {
  jest.useFakeTimers();
  try {
    const fetcher = jest
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ results: [] }) });
    await createPeopleSearch('http://backend', fetcher)('name');
    expect(jest.getTimerCount()).toBe(0);
  } finally {
    jest.useRealTimers();
  }
});
