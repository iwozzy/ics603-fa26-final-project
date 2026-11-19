import { SearchFailed } from '../../../domain/errors';

export function cancellable<T>(promise: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const abort = () => reject(new SearchFailed());
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
  });
}

export async function withDeadline<T>(caller: AbortSignal | undefined, operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  caller?.addEventListener('abort', abort, { once: true });
  if (caller?.aborted) abort();
  const timer = setTimeout(abort, 8000);
  try {
    if (controller.signal.aborted) throw new SearchFailed();
    return await cancellable(operation(controller.signal), controller.signal);
  } finally {
    clearTimeout(timer);
    caller?.removeEventListener('abort', abort);
  }
}
