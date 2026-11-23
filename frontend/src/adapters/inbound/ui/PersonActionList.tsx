import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ComponentRef } from 'react';
import { useFocusEffect } from 'expo-router';
import { Platform, View } from 'react-native';
import type { PersonSummary } from '../../../domain/people';
import { PersonActionRow, type PersonAction } from './PersonActionRow';

interface Props {
  people: readonly PersonSummary[];
  resultSetKey: string;
  actionFor(person: PersonSummary): PersonAction;
  onActivate(person: PersonSummary): void;
  rowIdFor(person: PersonSummary, position: number): string;
  testIdFor(person: PersonSummary, position: number): string;
}
export function PersonActionList({ people, resultSetKey, actionFor, onActivate, rowIdFor, testIdFor }: Props) {
  const [selection, setSelection] = useState<{ people: readonly PersonSummary[]; key: string; rowId: string } | null>(null);
  const selected = selection?.people === people && selection.key === resultSetKey ? selection.rowId : null;
  const root = useRef<ComponentRef<typeof View>>(null);
  const restoration = useRef<{ rowId: string; key: string; fallback: HTMLElement } | null>(null);
  const keyboard = useRef(true);
  useFocusEffect(useCallback(() => () => { setSelection(null); restoration.current = null; }, []));
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const pointer = (event: PointerEvent) => {
      keyboard.current = false;
      restoration.current = null;
      if (event.pointerType !== 'touch') return;
      const container = root.current as unknown as HTMLElement | null;
      const target = event.target;
      if (!(target instanceof Element) || !container?.contains(target) || target.closest('[data-person-row]')?.getAttribute('data-person-row') !== selected) setSelection(null);
    };
    const keydown = () => { keyboard.current = true; restoration.current = null; };
    const focus = (event: FocusEvent) => {
      if (restoration.current && event.target !== restoration.current.fallback) restoration.current = null;
    };
    document.addEventListener('pointerdown', pointer, true);
    document.addEventListener('keydown', keydown, true);
    document.addEventListener('focusin', focus, true);
    return () => {
      document.removeEventListener('pointerdown', pointer, true);
      document.removeEventListener('keydown', keydown, true);
      document.removeEventListener('focusin', focus, true);
    };
  }, [selected]);
  useLayoutEffect(() => {
    const token = restoration.current;
    if (!token || Platform.OS !== 'web' || typeof document === 'undefined') return;
    if (token.key !== resultSetKey || document.activeElement !== token.fallback) { restoration.current = null; return; }
    const row = Array.from(token.fallback.querySelectorAll<HTMLElement>('[data-person-row]')).find(node => node.getAttribute('data-person-row') === token.rowId);
    const action = row?.querySelector<HTMLElement>('[role="button"]');
    if (action) { restoration.current = null; action.focus(); }
  }, [people, resultSetKey]);
  const activate = (person: PersonSummary, rowId: string) => {
    if (Platform.OS === 'web' && typeof document !== 'undefined' && keyboard.current && actionFor(person) === 'unfollow') {
      const container = root.current as unknown as HTMLElement | null;
      const focused = document.activeElement;
      if (container && focused instanceof Element && container.contains(focused) && focused.closest('[data-person-row]')?.getAttribute('data-person-row') === rowId) {
        restoration.current = { rowId, key: resultSetKey, fallback: container };
        container.focus();
      }
    }
    onActivate(person);
  };
  return <View ref={root} tabIndex={-1}>{people.map((person, position) => {
    const rowId = rowIdFor(person, position);
    return <View key={rowId} testID={testIdFor(person, position)}>
      <PersonActionRow person={person} rowId={rowId} action={actionFor(person)} touchSelected={selected === rowId}
        onTouchSelect={id => setSelection({ people, key: resultSetKey, rowId: id })} onActivate={p => activate(p, rowId)} />
    </View>;
  })}</View>;
}
