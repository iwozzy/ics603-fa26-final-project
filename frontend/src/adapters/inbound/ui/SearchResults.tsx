import { useEffect, useRef, useState, type ComponentRef } from 'react';
import { Platform, View } from 'react-native';
import { personKey } from '../../../domain/following';
import type { PersonSummary } from '../../../domain/people';
import { SearchPersonRow } from './SearchPersonRow';
import { useFollowing } from './useFollowing';
export function SearchResults({ people, resultSetKey }: { people: readonly PersonSummary[]; resultSetKey: string }) {
  const { state, follow } = useFollowing();
  const [selection, setSelection] = useState<{ people: readonly PersonSummary[]; key: string; rowId: string } | null>(null);
  const selected = selection?.people === people && selection.key === resultSetKey ? selection.rowId : null;
  const setSelected = (rowId: string | null) => setSelection(rowId === null ? null : { people, key: resultSetKey, rowId });
  const root = useRef<ComponentRef<typeof View>>(null);
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const outside = (event: PointerEvent) => {
      if (event.pointerType !== 'touch') return;
      const container = root.current as unknown as HTMLElement | null;
      const target = event.target;
      if (!(target instanceof Element) || !container?.contains(target) || target.closest('[data-search-row]')?.getAttribute('data-search-row') !== selected) setSelection(null);
    };
    document.addEventListener('pointerdown', outside, true);
    return () => document.removeEventListener('pointerdown', outside, true);
  }, [selected]);
  const followed = new Set(state.people.map(personKey));
  return <View ref={root}>{people.map((person, position) => {
    const rowId = resultSetKey + ':' + position;
    return <View key={rowId} testID={'search-result-' + position}>
      <SearchPersonRow person={person} rowId={rowId} status={followed.has(personKey(person)) ? 'following' : state.canFollow ? 'available' : 'hidden'} touchSelected={selected === rowId} onTouchSelect={setSelected} onFollow={follow} />
    </View>;
  })}</View>;
}
