import {
  PersonSummary,
  SearchController,
} from '../src/application/search-people';

const person: PersonSummary = {
  name: 'Person',
  portraitUrl: null,
  department: null,
  knownFor: [],
};

function deferred() {
  let resolve!: (value: PersonSummary[]) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<PersonSummary[]>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

test('starts empty and editing the draft makes no request', () => {
  const search = jest.fn();
  const controller = new SearchController(search);
  expect(controller.state).toEqual({
    draft: '',
    submitted: null,
    loading: false,
    results: [],
  });
  controller.edit('Timothée');
  expect(controller.state.draft).toBe('Timothée');
  expect(search).not.toHaveBeenCalled();
});

test('explicit submission trims only the edges and publishes loading then results', async () => {
  const pending = deferred();
  const search = jest.fn(() => pending.promise);
  const controller = new SearchController(search);
  const changed = jest.fn();
  controller.subscribe(changed);
  controller.edit('  Timothée  O’Neill  ');
  const completed = controller.submit();
  expect(search).toHaveBeenCalledWith('Timothée  O’Neill');
  expect(controller.state.loading).toBe(true);
  expect(controller.state.submitted).toBe('Timothée  O’Neill');
  pending.resolve([person]);
  await completed;
  expect(controller.state.results).toEqual([person]);
  expect(controller.state.loading).toBe(false);
  expect(changed).toHaveBeenCalled();
});

test.each(['𠮷'.repeat(101)])(
  'silently rejects invalid draft %p and preserves displayed state',
  async (draft) => {
    const search = jest.fn().mockResolvedValue([person]);
    const controller = new SearchController(search);
    controller.edit('valid');
    await controller.submit();
    controller.edit(draft);
    const before = controller.state;
    await controller.submit();
    expect(controller.state).toBe(before);
    expect(search).toHaveBeenCalledTimes(1);
  },
);

test.each(['', ' \n\t'])(
  'blank submission %p restores the initial state without a request',
  async (draft) => {
    const search = jest.fn().mockResolvedValue([person]);
    const controller = new SearchController(search);
    controller.edit('Person');
    await controller.submit();
    controller.edit(draft);
    await controller.submit();
    expect(controller.state).toEqual({
      draft: '',
      submitted: null,
      loading: false,
      results: [],
    });
    expect(search).toHaveBeenCalledTimes(1);
  },
);

test.each(['success', 'failure'])(
  'a late %s cannot undo a blank-search reset',
  async (outcome) => {
    const pending = deferred();
    const search = jest.fn(() => pending.promise);
    const controller = new SearchController(search);
    controller.edit('Person');
    const completed = controller.submit();
    controller.edit('');
    await controller.submit();
    const reset = controller.state;
    expect(reset).toEqual({
      draft: '',
      submitted: null,
      loading: false,
      results: [],
    });
    if (outcome === 'success') pending.resolve([person]);
    else pending.reject(new Error('late failure'));
    await completed;
    expect(controller.state).toBe(reset);
    expect(search).toHaveBeenCalledTimes(1);
  },
);

test.each(['𠮷', '𠮷'.repeat(100)])(
  'accepts Unicode code point boundary %p',
  async (draft) => {
    const search = jest.fn().mockResolvedValue([]);
    const controller = new SearchController(search);
    controller.edit(draft);
    await controller.submit();
    expect(search).toHaveBeenCalledWith(draft);
  },
);

test('ignores a duplicate pending query but allows it again after completion', async () => {
  const pending = deferred();
  const search = jest.fn(() => pending.promise);
  const controller = new SearchController(search);
  controller.edit(' Person ');
  const completed = controller.submit();
  controller.edit('Person');
  const duplicate = controller.submit();
  expect(search).toHaveBeenCalledTimes(1);
  pending.resolve([person]);
  await Promise.all([completed, duplicate]);
  await controller.submit();
  expect(search).toHaveBeenCalledTimes(2);
});

test('keeps previous results while loading, then clears them and logs a safe failure', async () => {
  const pending = deferred();
  const search = jest
    .fn()
    .mockResolvedValueOnce([person])
    .mockReturnValueOnce(pending.promise)
    .mockResolvedValue([]);
  const log = jest.fn();
  const controller = new SearchController(search, log);
  controller.edit('first');
  await controller.submit();
  controller.edit('second');
  const completed = controller.submit();
  expect(controller.state.results).toEqual([person]);
  expect(controller.state.loading).toBe(true);
  pending.reject(new Error('private details'));
  await completed;
  expect(controller.state.loading).toBe(false);
  expect(controller.state.results).toEqual([]);
  expect(log).toHaveBeenCalledWith('People search failed');
  await controller.submit();
  expect(search).toHaveBeenCalledTimes(3);
  expect(controller.state.results).toEqual([]);
});

test.each(['success', 'failure'])(
  'older %s cannot stop newer loading or replace newer results',
  async (outcome) => {
    const older = deferred();
    const newer = deferred();
    const search = jest
      .fn()
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise);
    const controller = new SearchController(search);
    controller.edit('older');
    const first = controller.submit();
    controller.edit('newer');
    const second = controller.submit();
    if (outcome === 'success') older.resolve([{ ...person, name: 'Old' }]);
    else older.reject(new Error('old failure'));
    await first;
    expect(controller.state.loading).toBe(true);
    expect(controller.state.submitted).toBe('newer');
    newer.resolve([person]);
    await second;
    expect(controller.state.results).toEqual([person]);
  },
);

test.each(['success', 'failure'])(
  'older %s after latest completion cannot replace it',
  async (outcome) => {
    const older = deferred();
    const controller = new SearchController(
      jest
        .fn()
        .mockReturnValueOnce(older.promise)
        .mockResolvedValueOnce([person]),
    );
    controller.edit('older');
    const first = controller.submit();
    controller.edit('newer');
    await controller.submit();
    const latest = controller.state;
    if (outcome === 'success') older.resolve([]);
    else older.reject(new Error('old failure'));
    await first;
    expect(controller.state).toBe(latest);
  },
);

test.each(['success', 'failure'])(
  'ignores %s completions and new actions after disposal',
  async (outcome) => {
    const pending = deferred();
    const search = jest.fn(() => pending.promise);
    const log = jest.fn();
    const controller = new SearchController(search, log);
    const listener = jest.fn();
    controller.subscribe(listener);
    controller.edit('Person');
    const completed = controller.submit();
    controller.dispose();
    listener.mockClear();
    const disposed = controller.state;
    if (outcome === 'success') pending.resolve([person]);
    else pending.reject(new Error('late failure'));
    await completed;
    controller.edit('Another');
    await controller.submit();
    expect(controller.state).toBe(disposed);
    expect(listener).not.toHaveBeenCalled();
    expect(search).toHaveBeenCalledTimes(1);
    expect(log).not.toHaveBeenCalled();
  },
);

test('editing alone does not invalidate the submitted request', async () => {
  const pending = deferred();
  const controller = new SearchController(() => pending.promise);
  controller.edit('submitted');
  const completed = controller.submit();
  controller.edit('unsubmitted draft');
  pending.resolve([person]);
  await completed;
  expect(controller.state.results).toEqual([person]);
  expect(controller.state.draft).toBe('unsubmitted draft');
});
