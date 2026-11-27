import type { PropsWithChildren } from 'react';
import { Link, usePathname } from 'expo-router';
import { StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useThemedStyles, type ThemeColors } from './theme';
export function AppShell({ children }: PropsWithChildren) {
  const styles = useThemedStyles(createStyles);
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const narrow = width < 600;
  return <View style={[styles.shell, narrow && styles.narrow]}>
    <View style={[styles.sidebar, narrow && styles.topbar]}>
      <Text style={[styles.brand, narrow && styles.smallBrand]}>Lumière</Text>
      <View role="navigation" accessibilityLabel="Main navigation" style={[styles.links, narrow && styles.horizontal]}>
        {([{ href: '/', label: 'Search' }, { href: '/timeline', label: 'Timeline' }, { href: '/following', label: 'Following' }] as const).map(({ href, label }) =>
          <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined} style={[styles.link, narrow && styles.compactLink, pathname === href && styles.current]}>{label}</Link>)}
      </View>
    </View>
    <View style={styles.content}>{children}</View>
  </View>;
}
const createStyles = (colors: ThemeColors) => StyleSheet.create({
  shell: { flex: 1, flexDirection: 'row', backgroundColor: colors.background }, narrow: { flexDirection: 'column' },
  sidebar: { width: 220, borderRightWidth: 1, borderColor: colors.divider, padding: 20, paddingTop: 36 },
  topbar: { width: '100%', padding: 12, paddingTop: 16, borderRightWidth: 0, borderBottomWidth: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  brand: { fontSize: 32, fontWeight: '600', color: colors.body, marginBottom: 56 }, smallBrand: { fontSize: 23, marginBottom: 0 },
  links: { gap: 8 }, horizontal: { flexDirection: 'row', gap: 4 },
  link: { padding: 12, borderRadius: 12, fontSize: 17, color: colors.body }, current: { backgroundColor: colors.surface, fontWeight: '600' },
  compactLink: { paddingHorizontal: 6, paddingVertical: 8, fontSize: 15 },
  content: { flex: 1, minWidth: 0, minHeight: 0 },
});
