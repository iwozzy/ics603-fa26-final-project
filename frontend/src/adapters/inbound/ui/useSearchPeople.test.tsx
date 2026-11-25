import { act, renderHook } from '@testing-library/react-native';
import { DeferredRepository, result } from '../../../test-utils/fakes/people-search';
import { portsWrapper } from '../../../test-utils/renderWithPorts';
import { useSearchPeople } from './useSearchPeople';

async function setup() {
  const repository = new DeferredRepository();
  const hook = await renderHook(useSearchPeople, { wrapper: portsWrapper(repository) });
  async function submit(query: string) {
    await act(() => { hook.result.current.setDraft(query); });
    await act(() => { void hook.result.current.submit(); });
  }
  return { repository, ...hook, submit };
}

test('test_latest_submission_wins_even_after_old_failure', async () => {
  const h = await setup();
  await h.submit('A'); await h.submit('B');
  await act(() => h.repository.calls[1].resolve(result('B')));
  await act(() => h.repository.calls[0].reject(new Error('old failure')));
  expect(h.result.current).toMatchObject({ phase: 'results', submittedQuery: 'B', people: result('B').people });
  expect(h.repository.calls[0].signal.aborted).toBe(true);
});

test.each(['clear', 'unmount'])('test_clear_or_unmount_invalidates_pending_completion %s', async kind => {
  const h = await setup(); await h.submit('A');
  if (kind === 'clear') await act(() => h.result.current.setDraft('')); else await h.unmount();
  expect(h.repository.calls[0].signal.aborted).toBe(true);
  await act(() => h.repository.calls[0].resolve(result('A')));
  if (kind === 'clear') expect(h.result.current).toMatchObject({ draft: '', phase: 'initial', people: [] });
});

test('test_duplicate_pending_query_is_ignored', async () => {
  const h = await setup(); await h.submit(' A '); await h.submit('A');
  expect(h.repository.calls).toHaveLength(1);
  await act(() => h.repository.calls[0].resolve(result('A')));
  await act(() => h.result.current.setDraft('edit'));
  expect(h.result.current.people).toEqual(result('A').people);
});

test.each(['empty', 'error', 'invalid'])('completion leaves a blank list %s', async kind => {
  const h = await setup(); await h.submit('A');
  if (kind === 'empty') await act(() => h.repository.calls[0].resolve({ query: 'A', people: [] }));
  if (kind === 'error') await act(() => h.repository.calls[0].reject(new Error('failure')));
  if (kind === 'invalid') {
    await h.submit('😀'.repeat(201));
    expect(h.repository.calls).toHaveLength(1);
    expect(h.repository.calls[0].signal.aborted).toBe(true);
    await act(() => h.repository.calls[0].resolve(result('A')));
  }
  expect(h.result.current).toMatchObject({ phase: 'blank', people: [] });
});

test('reset aborts a retained screen search and ignores late results', async () => {
  const h = await setup(); await h.submit('A');
  await act(() => h.result.current.reset());
  expect(h.result.current).toMatchObject({ draft: '', submittedQuery: '', phase: 'initial', people: [] });
  expect(h.repository.calls[0].signal.aborted).toBe(true);
  await act(() => h.repository.calls[0].resolve(result('A')));
  expect(h.result.current.people).toEqual([]);
});
