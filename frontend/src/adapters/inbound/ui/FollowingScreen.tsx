import { useCallback } from 'react';
import { useFocusEffect } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { personKey } from '../../../domain/following';
import { PersonActionList } from './PersonActionList';
import { useFollowing } from './useFollowing';
import { useThemedStyles, type ThemeColors } from './theme';
export default function FollowingScreen() {
  const styles = useThemedStyles(createStyles);
  const { state, refresh, unfollow } = useFollowing();
  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));
  return <ScrollView style={styles.background} contentContainerStyle={styles.page}><View style={styles.list}>
    <PersonActionList selectionMode="membership" people={state.people} resultSetKey={state.confirmed ? 'following' : 'unknown'} actionFor={() => 'unfollow'}
      onActivate={unfollow} rowIdFor={personKey} testIdFor={person => 'following-person-' + personKey(person)} />
  </View></ScrollView>;
}
const createStyles = (colors: ThemeColors) => StyleSheet.create({ background: { backgroundColor: colors.background }, page: { flexGrow: 1, alignItems: 'center', paddingHorizontal: 20, paddingTop: 120, paddingBottom: 40, backgroundColor: colors.background }, list: { width: '100%', maxWidth: 880 } });
