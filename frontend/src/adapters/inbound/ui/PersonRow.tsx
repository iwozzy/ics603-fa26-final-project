import { useState, type ReactNode } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import type { PersonSummary } from '../../../domain/people';
import { useThemedStyles, type ThemeColors } from './theme';

export function PersonRow({ person, action }: { person: PersonSummary; action?: ReactNode }) {
  const styles = useThemedStyles(createStyles);
  const [failed, setFailed] = useState(false);
  const metadata = [person.knownForDepartment?.trim(), person.knownFor.filter(title => title.trim()).slice(0, 3).join(', ')].filter(Boolean).join(' · ');
  return <View style={styles.row}>
    {person.profileImageUrl && !failed ? <Image accessibilityLabel={person.name + ' profile'} source={{ uri: person.profileImageUrl }} style={styles.photo} onError={() => setFailed(true)} /> :
      <View accessibilityRole="image" accessibilityLabel={person.name + ' silhouette'} style={styles.silhouette}><View style={styles.head} /><View style={styles.shoulders} /></View>}
    <View style={styles.details}><Text style={styles.name}>{person.name}</Text>{metadata ? <Text style={styles.metadata}>{metadata}</Text> : null}</View>
    {action}
  </View>;
}
const createStyles = (colors: ThemeColors) => StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 16, paddingVertical: 14 },
  photo: { width: 58, height: 58, borderRadius: 29 },
  silhouette: { width: 58, height: 58, borderRadius: 29, overflow: 'hidden', backgroundColor: colors.surface, alignItems: 'center', borderWidth: 1, borderColor: colors.avatarBorder },
  head: { width: 19, height: 19, borderRadius: 10, marginTop: 10, backgroundColor: colors.silhouette },
  shoulders: { width: 43, height: 32, borderRadius: 22, marginTop: 4, backgroundColor: colors.silhouette },
  details: { flex: 1, minWidth: 0, gap: 6 }, name: { fontSize: 21, fontWeight: '600', color: colors.text }, metadata: { fontSize: 15, color: colors.muted, lineHeight: 22 },
});
