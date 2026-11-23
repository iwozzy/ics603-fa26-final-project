import { useEffect, useLayoutEffect, useRef, useState, type ComponentRef, type PointerEvent as ReactPointerEvent } from 'react';
import { Platform, Pressable, StyleSheet, Text } from 'react-native';
import type { PersonSummary } from '../../../domain/people';
import { PersonRow } from './PersonRow';

interface Props {
  person: PersonSummary; rowId: string; status: 'available' | 'following' | 'hidden';
  touchSelected: boolean; onTouchSelect(rowId: string): void; onFollow(person: PersonSummary): void;
}
export function SearchPersonRow({ person, rowId, status, touchSelected, onTouchSelect, onFollow }: Props) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const modality = useRef<'mouse' | 'keyboard' | 'touch'>('keyboard');
  const gesture = useRef<{ x: number; y: number; id: number; moved: boolean } | null>(null);
  const touchActivation = useRef(false);
  const actionRef = useRef<ComponentRef<typeof Pressable>>(null);
  useLayoutEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined' || modality.current === 'touch') return;
    // RN web changes the host from button to status div. Removal loses DOM
    // focus without a blur event; transfer only if focus has fallen to body.
    const node = actionRef.current as unknown as HTMLElement | null;
    if (focused && node && document.activeElement === document.body) node.focus();
  }, [status, focused]);
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const touch = (event: PointerEvent) => {
      if (event.pointerType === 'touch') { modality.current = 'touch'; setHovered(false); setFocused(false); }
    };
    const keyboard = () => { modality.current = 'keyboard'; };
    document.addEventListener('pointerdown', touch, true); document.addEventListener('keydown', keyboard, true);
    return () => { document.removeEventListener('pointerdown', touch, true); document.removeEventListener('keydown', keyboard, true); };
  }, []);
  const revealed = hovered || focused || touchSelected;
  const revealStyle = { opacity: revealed ? 1 : 0, pointerEvents: revealed ? 'auto' as const : 'none' as const };
  const action = status === 'hidden' ? null : status === 'following' ?
    <Pressable ref={actionRef} role="status" onFocus={() => { if (modality.current !== 'touch') setFocused(true); }} onBlur={() => setFocused(false)} style={[styles.status, revealStyle, focused && styles.focused]}><Text>Following</Text></Pressable> :
    <Pressable ref={actionRef} accessibilityRole="button" accessibilityLabel="Follow +" onFocus={() => { if (modality.current !== 'touch') setFocused(true); }} onBlur={() => setFocused(false)}
      onPress={() => {
        if (modality.current === 'touch' && !touchActivation.current) return;
        touchActivation.current = false;
        onFollow(person);
      }} style={[styles.action, revealStyle, focused && styles.focused]}><Text style={styles.actionText}>Follow +</Text></Pressable>;
  const content = <PersonRow person={person} action={action} />;
  if (Platform.OS !== 'web') return <Pressable onPress={() => onTouchSelect(rowId)}>{content}</Pressable>;
  const down = (event: ReactPointerEvent<HTMLDivElement>) => {
    modality.current = event.pointerType === 'touch' ? 'touch' : 'mouse';
    if (event.pointerType === 'touch') {
      setHovered(false); setFocused(false);
      gesture.current = { x: event.clientX, y: event.clientY, id: event.pointerId, moved: false };
      touchActivation.current = touchSelected;
    }
  };
  return <div data-search-row={rowId} onPointerEnter={event => { if (event.pointerType === 'mouse') { modality.current = 'mouse'; setHovered(true); } }}
    onPointerLeave={() => setHovered(false)} onPointerDown={down}
    onPointerMove={event => {
      if (event.pointerType === 'mouse') { modality.current = 'mouse'; setHovered(true); }
      const current = gesture.current;
      if (current && (Math.abs(event.clientX - current.x) > 10 || Math.abs(event.clientY - current.y) > 10)) { current.moved = true; touchActivation.current = false; }
    }}
    onPointerCancel={() => { gesture.current = null; touchActivation.current = false; }}
    onPointerUp={event => {
      const current = gesture.current; gesture.current = null;
      if (event.pointerType === 'touch' && current && current.id === event.pointerId && !current.moved) onTouchSelect(rowId);
    }}>{content}</div>;
}
const styles = StyleSheet.create({
  action: { paddingVertical: 9, paddingHorizontal: 14, borderWidth: 2, borderColor: '#c3c7cc', borderRadius: 10 },
  actionText: { fontSize: 15, color: '#343941' }, status: { fontSize: 15, color: '#6c737c', padding: 10, borderWidth: 2, borderColor: 'transparent', borderRadius: 10 }, focused: { borderColor: '#4279b2' },
});
