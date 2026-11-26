import type { TimelinePage, TimelineQuery } from '../../domain/timeline';
import { DeferredTimeline } from '../../test-utils/fakes/timeline';
import { ListTimeline } from './list-timeline';

test('lists through the repository with the original query and cancellation signal', async () => {
  const repository = new DeferredTimeline();
  const useCase = new ListTimeline(repository);
  const query: TimelineQuery = { mode: 'page', direction: 'older', cursor: 'older-edge' };
  const signal = new AbortController().signal;
  const page: TimelinePage = { items: [], olderCursor: null, newerCursor: null, asOf: null, anchorIndex: null };

  const request = useCase.execute(query, signal);
  expect(repository.calls).toHaveLength(1);
  expect(repository.calls[0].query).toBe(query);
  expect(repository.calls[0].signal).toBe(signal);
  repository.calls[0].resolve(page);
  await expect(request).resolves.toBe(page);
});

test('propagates repository failures unchanged', async () => {
  const repository = new DeferredTimeline();
  const request = new ListTimeline(repository).execute({ mode: 'initial' }, new AbortController().signal);
  const error = new Error('timeline unavailable');

  repository.calls[0].reject(error);
  await expect(request).rejects.toBe(error);
});
