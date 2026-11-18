export interface PersonSummary {
  name: string;
  portraitUrl: string | null;
  department: string | null;
  knownFor: string[];
}

export type SearchPeople = (query: string) => Promise<PersonSummary[]>;

export interface SearchState {
  draft: string;
  submitted: string | null;
  loading: boolean;
  results: PersonSummary[];
}

export class SearchController {
  state: SearchState = {
    draft: '',
    submitted: null,
    loading: false,
    results: [],
  };
  private readonly listeners = new Set<() => void>();
  private readonly pending = new Set<string>();
  private sequence = 0;
  private disposed = false;

  constructor(
    private readonly search: SearchPeople,
    private readonly logFailure: (message: string) => void = () => {},
  ) {}

  edit(draft: string) {
    if (this.disposed) return;
    this.update({ draft });
  }

  dispose() {
    this.disposed = true;
    this.sequence++;
    this.listeners.clear();
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private update(changes: Partial<SearchState>) {
    this.state = { ...this.state, ...changes };
    this.listeners.forEach((listener) => listener());
  }

  async submit() {
    if (this.disposed) return;
    const query = this.state.draft.trim();
    if (!query) {
      this.sequence++;
      this.update({ draft: '', submitted: null, loading: false, results: [] });
      return;
    }
    if (Array.from(query).length > 100) return;
    if (this.pending.has(query)) return;
    this.pending.add(query);
    const sequence = ++this.sequence;
    this.update({ submitted: query, loading: true });
    try {
      const results = await this.search(query);
      if (sequence === this.sequence) this.update({ results, loading: false });
    } catch {
      if (!this.disposed) this.logFailure('People search failed');
      if (sequence === this.sequence)
        this.update({ results: [], loading: false });
    } finally {
      this.pending.delete(query);
    }
  }
}
