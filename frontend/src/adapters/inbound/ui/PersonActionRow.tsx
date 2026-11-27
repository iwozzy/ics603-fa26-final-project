import { useEffect, useLayoutEffect, useRef, useState, type ComponentRef, type PointerEvent as ReactPointerEvent } from 'react';
import { Platform, Pressable, StyleSheet, Text } from 'react-native';
import type { PersonSummary } from '../../../domain/people';
import { PersonRow } from './PersonRow';
import { useThemedStyles, type ThemeColors } from './theme';

export type PersonAction = 'follow' | 'following' | 'unfollow' | 'hidden';

interface Props {
  person: PersonSummary; rowId: string; action: PersonAction;
  touchSelected: boolean; onTouchSelect(rowId: string): void; onActivate(person: PersonSummary): void;
}
export function PersonActionRow({ person, rowId, action: kind, touchSelected, onTouchSelect, onActivate }: Props) {
  const styles = useThemedStyles(createStyles);
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
  }, [kind, focused]);
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const touch = (event: PointerEvent) => {
      if (event.pointerType === 'touch' || event.pointerType === 'pen') { modality.current = 'touch'; setHovered(false); setFocused(false); }
    };
    const keyboard = () => { modality.current = 'keyboard'; };
    document.addEventListener('pointerdown', touch, true); document.addEventListener('keydown', keyboard, true);
    return () => { document.removeEventListener('pointerdown', touch, true); document.removeEventListener('keydown', keyboard, true); };
  }, []);
  const revealed = hovered || focused || touchSelected;
  const revealStyle = { opacity: revealed ? 1 : 0, pointerEvents: revealed ? 'auto' as const : 'none' as const };
  const action = kind === 'hidden' ? null : kind === 'following' ?
    <Pressable ref={actionRef} role="status" onFocus={() => setFocused(modality.current === 'keyboard')} onBlur={() => setFocused(false)} style={[styles.status, revealStyle, focused && styles.focused]}><Text style={styles.statusText}>Following</Text></Pressable> :
    <Pressable ref={actionRef} accessibilityRole="button" accessibilityLabel={kind === 'unfollow' ? 'Unfollow' : 'Follow +'} onFocus={() => setFocused(modality.current === 'keyboard')} onBlur={() => setFocused(false)}
      onPress={() => {
        if (modality.current === 'touch' && !touchActivation.current) return;
        touchActivation.current = false;
        onActivate(person);
      }} style={[styles.action, revealStyle, focused && styles.focused]}><Text style={styles.actionText}>{kind === 'unfollow' ? 'Unfollow' : 'Follow +'}</Text></Pressable>;
  const content = <PersonRow person={person} action={action} />;
  if (Platform.OS !== 'web') return <Pressable onPress={() => onTouchSelect(rowId)}>{content}</Pressable>;
  const down = (event: ReactPointerEvent<HTMLDivElement>) => {
    modality.current = (event.pointerType === 'touch' || event.pointerType === 'pen') ? 'touch' : 'mouse';
    setFocused(false);
    if (event.pointerType === 'touch' || event.pointerType === 'pen') {
      setHovered(false);
      gesture.current = { x: event.clientX, y: event.clientY, id: event.pointerId, moved: false };
      touchActivation.current = touchSelected;
    }
  };
  return <div data-person-row={rowId} onPointerEnter={event => { if (event.pointerType === 'mouse') { modality.current = 'mouse'; setHovered(true); } }}
    onPointerLeave={() => setHovered(false)} onPointerDown={down}
    onPointerMove={event => {
      if (event.pointerType === 'mouse') { modality.current = 'mouse'; setHovered(true); }
      const current = gesture.current;
      if (current && (Math.abs(event.clientX - current.x) > 10 || Math.abs(event.clientY - current.y) > 10)) { current.moved = true; touchActivation.current = false; }
    }}
    onPointerCancel={() => { gesture.current = null; touchActivation.current = false; }}
    onPointerUp={event => {
      const current = gesture.current; gesture.current = null;
      if ((event.pointerType === 'touch' || event.pointerType === 'pen') && current && current.id === event.pointerId && !current.moved) onTouchSelect(rowId);
    }}>{content}</div>;
}
const createStyles = (colors: ThemeColors) => StyleSheet.create({
  action: { paddingVertical: 9, paddingHorizontal: 14, borderWidth: 2, borderColor: colors.border, borderRadius: 10 },
  actionText: { fontSize: 15, color: colors.body }, statusText: { fontSize: 15, color: colors.muted }, status: { fontSize: 15, color: colors.muted, padding: 10, borderWidth: 2, borderColor: colors.border, borderRadius: 10 }, focused: { borderColor: colors.focus },
});
