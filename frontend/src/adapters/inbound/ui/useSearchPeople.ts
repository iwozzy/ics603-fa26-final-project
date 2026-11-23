import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { normalizeQuery, type PersonSummary } from '../../../domain/people';
import { PeopleSearchContext } from './PeopleSearchContext';

export interface SearchState { draft: string; submittedQuery: string; phase: 'initial' | 'loading' | 'results' | 'blank'; people: readonly PersonSummary[]; }
const initial: SearchState = { draft: '', submittedQuery: '', phase: 'initial', people: [] };

export function useSearchPeople(): SearchState & { setDraft(value: string): void; submit(): Promise<void>; reset(): void } {
  const ports = useContext(PeopleSearchContext);
  if (!ports) throw new Error('PeopleSearchContext is required');
  const { searchPeople } = ports;
  const [state, setState] = useState<SearchState>(initial);
  const draft = useRef('');
  const generation = useRef(0);
  const mounted = useRef(true);
  const pending = useRef<{ query: string; controller: AbortController } | undefined>(undefined);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; generation.current = generation.current + 1; pending.current?.controller.abort(); };
  }, []);

  const reset = useCallback(() => {
    draft.current = '';
    generation.current++;
    pending.current?.controller.abort(); pending.current = undefined;
    setState(initial);
  }, []);
  const setDraft = useCallback((value: string) => {
    draft.current = value;
    if (value === '') reset();
    else setState(previous => ({ ...previous, draft: value }));
  }, [reset]);

  const submit = useCallback(async () => {
    const raw = draft.current;
    if (pending.current?.query === raw.trim()) return;
    const current = ++generation.current;
    pending.current?.controller.abort(); pending.current = undefined;
    let query: string;
    try { query = normalizeQuery(raw); }
    catch { setState(previous => ({ ...previous, submittedQuery: raw.trim(), phase: 'blank', people: [] })); return; }
    const controller = new AbortController();
    pending.current = { query, controller };
    setState(previous => ({ ...previous, submittedQuery: query, phase: 'loading', people: [] }));
    try {
      const result = await searchPeople.execute(query, controller.signal);
      if (mounted.current && generation.current === current) setState(previous => ({ ...previous, phase: result.people.length ? 'results' : 'blank', people: result.people }));
    } catch {
      if (mounted.current && generation.current === current) setState(previous => ({ ...previous, phase: 'blank', people: [] }));
    } finally {
      if (generation.current === current) pending.current = undefined;
    }
  }, [searchPeople]);
  return { ...state, setDraft, submit, reset };
}
