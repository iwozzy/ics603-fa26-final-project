import { useCallback, useRef, useState, type ComponentRef } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { useFollowing } from './useFollowing';
import { PersonRow } from './PersonRow';
import { useSearchPeople } from './useSearchPeople';

export default function SearchPeopleScreen() {
  const state = useSearchPeople();
  const { refresh } = useFollowing();
  const { reset } = state;
  useFocusEffect(useCallback(() => { void refresh(); return reset; }, [refresh, reset]));
  const input = useRef<ComponentRef<typeof TextInput>>(null);
  const [focused, setFocused] = useState(false);
  const [buttonFocused, setButtonFocused] = useState(false);
  const { width } = useWindowDimensions();
  const busy = state.phase === 'loading';
  const duplicate = busy && state.draft.trim() === state.submittedQuery;
  const submit = () => { void state.submit(); input.current?.focus(); };
  return <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.page, { paddingTop: width < 600 ? 56 : 120 }]}>
    <View style={styles.content}>
      <View style={styles.headingWrap}><Text accessibilityRole="header" style={styles.heading}>Cast & Crew</Text></View>
      <View style={[styles.field, focused && styles.focused]}>
        <TextInput ref={input} accessibilityLabel="Search people" placeholder="Search for actors, directors, or creative team to follow" placeholderTextColor="#9299a2" value={state.draft} onChangeText={state.setDraft} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} style={styles.input} returnKeyType="search" blurOnSubmit={false} autoCapitalize="none" onSubmitEditing={event => {
          const native = event.nativeEvent as { isComposing?: boolean; keyCode?: number };
          if (!native.isComposing && native.keyCode !== 229) submit();
        }} />
        <Pressable accessibilityRole="button" accessibilityLabel="Search" aria-busy={busy} accessibilityState={{ busy, disabled: duplicate }} disabled={duplicate} onPress={submit} onFocus={() => setButtonFocused(true)} onBlur={() => setButtonFocused(false)} style={[styles.search, buttonFocused && styles.buttonFocused]}>
          {duplicate ? <ActivityIndicator color="#667180" accessibilityElementsHidden importantForAccessibility="no-hide-descendants" /> : <View accessible={false} style={styles.icon}><View style={styles.lens} /><View style={styles.handle} /></View>}
        </Pressable>
      </View>
      {state.phase === 'initial' || busy ? <View style={styles.examples}>
        <Text style={styles.examplesTitle}>Example searches:</Text>
        <Text style={styles.example}>Timothée Chalamet (Actor)</Text>
        <Text style={styles.example}>Hayao Miyazaki (Director, Writer)</Text>
        <Text style={styles.example}>Autumn Durald Arkapaw (Cinematographer)</Text>
      </View> : <View style={styles.results}>{state.people.map((person, position) => <PersonRow key={state.submittedQuery + ':' + position} person={person} />)}</View>}
    </View>
  </ScrollView>;
}
const styles = StyleSheet.create({
  page: { flexGrow: 1, alignItems: 'center', paddingHorizontal: 20, paddingBottom: 40, backgroundColor: '#fff' },
  content: { width: '100%', maxWidth: 880 }, headingWrap: { alignSelf: 'center', borderBottomWidth: 2, borderBottomColor: '#343941', marginBottom: 32, paddingBottom: 7 },
  heading: { fontSize: 28, fontWeight: '600', color: '#24282d' },
  field: { flexDirection: 'row', alignItems: 'center', borderWidth: 2, borderColor: '#c3c7cc', borderRadius: 16, padding: 8, minHeight: 68 },
  focused: { borderColor: '#4279b2' }, input: { flex: 1, minWidth: 0, fontSize: 17, padding: 10, color: '#22262c', outlineStyle: 'solid', outlineWidth: 0 },
  search: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: '#e3e7ec', borderWidth: 2, borderColor: 'transparent' },
  buttonFocused: { borderColor: '#4279b2' }, icon: { width: 23, height: 23 }, lens: { width: 16, height: 16, borderWidth: 2, borderColor: '#697786', borderRadius: 8 }, handle: { position: 'absolute', width: 10, height: 2, backgroundColor: '#697786', left: 13, top: 17, transform: [{ rotate: '45deg' }] },
  examples: { marginTop: 24, paddingHorizontal: 12, gap: 10 }, examplesTitle: { color: '#737b85', fontSize: 15, marginBottom: 10 }, example: { color: '#737b85', fontSize: 15, lineHeight: 23 }, results: { marginTop: 24, paddingHorizontal: 8 },
});
