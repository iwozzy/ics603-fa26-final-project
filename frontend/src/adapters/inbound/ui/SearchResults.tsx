import { personKey } from '../../../domain/following';
import type { PersonSummary } from '../../../domain/people';
import { PersonActionList } from './PersonActionList';
import { useFollowing } from './useFollowing';
export function SearchResults({ people, resultSetKey }: { people: readonly PersonSummary[]; resultSetKey: string }) {
  const { state, follow } = useFollowing();
  const followed = new Set(state.people.map(personKey));
  return <PersonActionList people={people} resultSetKey={resultSetKey} onActivate={follow}
    actionFor={person => followed.has(personKey(person)) ? 'following' : state.canFollow ? 'follow' : 'hidden'}
    rowIdFor={(_person, position) => resultSetKey + ':' + position} testIdFor={(_person, position) => 'search-result-' + position} />;
}
