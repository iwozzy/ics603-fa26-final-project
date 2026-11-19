import type { SearchPerson } from './model';

export interface SearchRequest {
  result: Promise<SearchPerson[]>;
  cancel(): void;
}
export interface PeopleSearch {
  start(name: string): SearchRequest;
}
export interface SearchState {
  draft: string;
  submitted: string | null;
  loading: boolean;
  results: SearchPerson[];
}

/** A mounted screen owns one workflow; submitting or clearing supersedes pending work. */
export function createSearchWorkflow(backend: PeopleSearch) {
  let state: SearchState = {
    draft: '',
    submitted: null,
    loading: false,
    results: [],
  };
  let generation = 0;
  let active: SearchRequest | undefined;
  let disposed = false;
  const listeners = new Set<() => void>();
  const update = (next: SearchState) => {
    if (disposed) return;
    state = next;
    listeners.forEach((listener) => listener());
  };
  return {
    snapshot: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    edit(draft: string) {
      if (disposed) return;
      if (!draft.trim()) {
        ++generation;
        active?.cancel();
        active = undefined;
        update({ draft, submitted: null, loading: false, results: [] });
        return;
      }
      update({ ...state, draft });
    },
    submit(draft = state.draft) {
      const name = draft.trim();
      if (!name || disposed) return;
      const current = ++generation;
      active?.cancel();
      update({ ...state, draft, submitted: name, loading: true, results: [] });
      active = backend.start(name);
      active.result.then(
        (results) => {
          if (generation === current)
            update({ ...state, results, loading: false });
        },
        () => {
          if (generation === current)
            update({ ...state, results: [], loading: false });
        },
      );
    },
    dispose() {
      disposed = true;
      ++generation;
      active?.cancel();
      listeners.clear();
    },
  };
}
