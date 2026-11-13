import { useEffect, useState, useSyncExternalStore } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from 'react-native';
import type { PersonResponse } from './api.generated';
import { httpPeopleSearch } from './search/backend';
import { createSearchWorkflow } from './search/workflow';
import './web.css';

const examples = [
  ['Timothée Chalamet', 'Actor'],
  ['Hayao Miyazaki', 'Director, Writer'],
  ['Autumn Durald Arkapaw', 'Cinematographer'],
];

function Portrait({ person }: { person: PersonResponse }) {
  const [failed, setFailed] = useState(false);
  if (!person.portrait_url || failed) {
    return (
      <View
        style={styles.portrait}
        accessibilityLabel={`Portrait unavailable for ${person.name}`}
        role="img"
      >
        <View style={styles.head} />
        <View style={styles.shoulders} />
      </View>
    );
  }
  return (
    <Image
      source={{ uri: person.portrait_url }}
      accessibilityLabel={`Portrait of ${person.name}`}
      onError={() => setFailed(true)}
      style={styles.portrait}
    />
  );
}

export default function App() {
  const [workflow] = useState(() => createSearchWorkflow(httpPeopleSearch));
  const state = useSyncExternalStore(workflow.subscribe, workflow.snapshot);
  const [rowReveal, setRowReveal] = useState<{
    results: PersonResponse[];
    personId: string | null;
  } | null>(null);
  const revealed =
    rowReveal?.results === state.results ? rowReveal.personId : null;
  const { width, height } = useWindowDimensions();
  const narrow = width < 600;
  useEffect(() => () => workflow.dispose(), [workflow]);

  return (
    <ScrollView
      style={styles.page}
      contentContainerStyle={{ minHeight: height }}
      keyboardShouldPersistTaps="handled"
    >
      <View
        style={[
          styles.content,
          {
            paddingTop: narrow ? 64 : Math.max(72, height * 0.25),
            paddingHorizontal: narrow ? 20 : 32,
          },
        ]}
      >
        <View
          style={styles.tabs}
          role="tablist"
          accessibilityLabel="Search mode"
        >
          <Pressable
            role="tab"
            accessibilityState={{ selected: true }}
            style={styles.activeTab}
          >
            <Text style={styles.tabText}>Cast &amp; Crew</Text>
          </Pressable>
          <Pressable
            role="button"
            accessibilityLabel="Movies"
            disabled
            accessibilityState={{ disabled: true }}
          >
            <Text style={[styles.tabText, styles.muted]}>Movies</Text>
          </Pressable>
        </View>
        <View testID="search-box" style={styles.searchBox}>
          <TextInput
            accessibilityLabel="Search cast and crew"
            placeholder="Search for actors, directors, or creative team to follow"
            placeholderTextColor="#92979d"
            value={state.draft}
            onChangeText={workflow.edit}
            onSubmitEditing={() => workflow.submit()}
            returnKeyType="search"
            style={[styles.input, { fontSize: narrow ? 15 : 18 }]}
          />
          <Pressable
            accessibilityLabel="Search"
            role="button"
            disabled={!state.draft.trim()}
            accessibilityState={{ disabled: !state.draft.trim() }}
            onPress={() => workflow.submit()}
            style={({ pressed }) => [
              styles.searchAction,
              { opacity: pressed ? 0.65 : state.draft.trim() ? 1 : 0.45 },
            ]}
          >
            {state.loading ? (
              <ActivityIndicator
                accessibilityLabel="Searching"
                color="#555e69"
                size="small"
              />
            ) : (
              <View style={styles.searchGlyph}>
                <View style={styles.searchHandle} />
              </View>
            )}
          </Pressable>
        </View>
        {state.submitted === null && (
          <View style={styles.examples}>
            <Text style={styles.exampleHeading}>Example searches:</Text>
            {examples.map(([name, role]) => (
              <Pressable
                key={name}
                onPress={() => workflow.submit(name)}
                style={styles.example}
              >
                <Text style={styles.exampleText}>
                  {name} <Text style={styles.muted}>({role})</Text>
                </Text>
              </Pressable>
            ))}
          </View>
        )}
        <View
          testID="results"
          accessibilityLiveRegion="polite"
          style={styles.results}
        >
          {state.results.map((person) => {
            const id = person.provider_ref.id;
            const secondary = [
              person.department,
              person.known_for.length ? person.known_for.join(', ') : null,
            ]
              .filter(Boolean)
              .join(' • ');
            return (
              <Pressable
                key={id}
                testID="person-row"
                accessibilityLabel={person.name}
                role="group"
                onPress={() =>
                  setRowReveal({
                    results: state.results,
                    personId: revealed === id ? null : id,
                  })
                }
                style={({ pressed }) => [
                  styles.row,
                  {
                    gap: narrow ? 12 : 18,
                    backgroundColor: pressed ? '#f5f6f7' : 'transparent',
                  },
                ]}
              >
                <Portrait person={person} />
                <View style={styles.personText}>
                  <Text
                    style={[styles.personName, { fontSize: narrow ? 20 : 24 }]}
                  >
                    {person.name}
                  </Text>
                  {!!secondary && (
                    <Text style={styles.secondary}>{secondary}</Text>
                  )}
                </View>
                <View
                  testID="follow-container"
                  style={[
                    styles.followContainer,
                    revealed === id && styles.revealed,
                  ]}
                >
                  <Pressable
                    role="button"
                    accessibilityLabel={`Follow ${person.name}`}
                    disabled
                    accessibilityState={{ disabled: true }}
                    style={styles.follow}
                  >
                    <Text style={styles.followText}>Follow +</Text>
                  </Pressable>
                </View>
              </Pressable>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#fff' },
  content: {
    width: '100%',
    maxWidth: 880,
    alignSelf: 'center',
    paddingBottom: 64,
  },
  tabs: {
    flexDirection: 'row',
    gap: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  activeTab: {
    borderBottomColor: '#252a31',
    borderBottomWidth: 2,
    paddingVertical: 8,
  },
  tabText: { color: '#252a31', fontSize: 23, fontWeight: '600' },
  muted: { color: '#8b9097' },
  searchBox: {
    borderWidth: 1,
    borderColor: '#a8adb4',
    borderRadius: 16,
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    gap: 8,
  },
  input: {
    flex: 1,
    minWidth: 0,
    paddingHorizontal: 6,
    paddingVertical: 10,
    color: '#252a31',
  },
  searchAction: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#e5e8ec',
    alignItems: 'center',
    justifyContent: 'center',
  },
  searchGlyph: {
    width: 16,
    height: 16,
    borderWidth: 2,
    borderColor: '#65717e',
    borderRadius: 8,
    marginRight: 4,
    marginBottom: 4,
  },
  searchHandle: {
    position: 'absolute',
    width: 9,
    height: 2,
    backgroundColor: '#65717e',
    right: -6,
    bottom: -3,
    transform: [{ rotate: '45deg' }],
  },
  examples: { paddingHorizontal: 16, paddingTop: 22, gap: 8 },
  exampleHeading: { fontSize: 15, color: '#737b85', marginBottom: 8 },
  example: { alignSelf: 'flex-start', paddingVertical: 5 },
  exampleText: { fontSize: 15, color: '#626c78', lineHeight: 23 },
  results: { paddingTop: 22, gap: 8 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 12,
    minHeight: 88,
    flexWrap: 'wrap',
  },
  portrait: {
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: '#edf0f3',
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  head: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#a0a8b2',
    marginTop: 12,
  },
  shoulders: {
    width: 38,
    height: 28,
    borderRadius: 19,
    backgroundColor: '#a0a8b2',
    marginTop: 4,
  },
  personText: { flex: 1, minWidth: 110, gap: 6 },
  personName: { color: '#252a31', fontWeight: '600' },
  secondary: { color: '#777f89', fontSize: 14, lineHeight: 21 },
  followContainer: { opacity: 0 },
  revealed: { opacity: 1 },
  follow: {
    borderWidth: 1,
    borderColor: '#a8adb4',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  followText: { color: '#7d858f', fontSize: 15 },
});
