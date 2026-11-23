import { useCallback } from 'react';
import { useFocusEffect } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { personKey } from '../../../domain/following';
import { PersonRow } from './PersonRow';
import { useFollowing } from './useFollowing';
export default function FollowingScreen() {
  const { state, refresh } = useFollowing();
  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));
  return <ScrollView contentContainerStyle={styles.page}><View style={styles.list}>
    {state.people.map(person => <PersonRow key={personKey(person)} person={person} />)}
  </View></ScrollView>;
}
const styles = StyleSheet.create({ page: { flexGrow: 1, alignItems: 'center', paddingHorizontal: 20, paddingTop: 120, paddingBottom: 40, backgroundColor: '#fff' }, list: { width: '100%', maxWidth: 880 } });
