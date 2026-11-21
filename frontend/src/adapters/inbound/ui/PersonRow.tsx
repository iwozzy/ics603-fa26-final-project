import { useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import type { PersonSummary } from '../../../domain/people';

export function PersonRow({ person }: { person: PersonSummary }) {
  const [failed, setFailed] = useState(false);
  const metadata = [person.knownForDepartment?.trim(), person.knownFor.filter(title => title.trim()).slice(0, 3).join(', ')].filter(Boolean).join(' · ');
  return <View style={styles.row}>
    {person.profileImageUrl && !failed ? <Image accessibilityLabel={person.name + ' profile'} source={{ uri: person.profileImageUrl }} style={styles.photo} onError={() => setFailed(true)} /> :
      <View accessibilityRole="image" accessibilityLabel={person.name + ' silhouette'} style={styles.silhouette}><View style={styles.head} /><View style={styles.shoulders} /></View>}
    <View style={styles.details}><Text style={styles.name}>{person.name}</Text>{metadata ? <Text style={styles.metadata}>{metadata}</Text> : null}</View>
  </View>;
}
const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 16, paddingVertical: 14 },
  photo: { width: 58, height: 58, borderRadius: 29 },
  silhouette: { width: 58, height: 58, borderRadius: 29, overflow: 'hidden', backgroundColor: '#eff0f2', alignItems: 'center', borderWidth: 1, borderColor: '#c8ccd1' },
  head: { width: 19, height: 19, borderRadius: 10, marginTop: 10, backgroundColor: '#8a939e' },
  shoulders: { width: 43, height: 32, borderRadius: 22, marginTop: 4, backgroundColor: '#8a939e' },
  details: { flex: 1, minWidth: 0, gap: 6 }, name: { fontSize: 21, fontWeight: '600', color: '#22262c' }, metadata: { fontSize: 15, color: '#6c737c', lineHeight: 22 },
});
