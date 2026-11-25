import type { PropsWithChildren } from 'react';
import { Link, usePathname } from 'expo-router';
import { StyleSheet, Text, View, useWindowDimensions } from 'react-native';
export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const narrow = width < 600;
  return <View style={[styles.shell, narrow && styles.narrow]}>
    <View style={[styles.sidebar, narrow && styles.topbar]}>
      <Text style={[styles.brand, narrow && styles.smallBrand]}>Lumière</Text>
      <View role="navigation" accessibilityLabel="Main navigation" style={[styles.links, narrow && styles.horizontal]}>
        {([{ href: '/', label: 'Search' }, { href: '/following', label: 'Following' }] as const).map(({ href, label }) =>
          <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined} style={[styles.link, pathname === href && styles.current]}>{label}</Link>)}
      </View>
    </View>
    <View style={styles.content}>{children}</View>
  </View>;
}
const styles = StyleSheet.create({
  shell: { flex: 1, flexDirection: 'row', backgroundColor: '#fff' }, narrow: { flexDirection: 'column' },
  sidebar: { width: 220, borderRightWidth: 1, borderColor: '#e1e4e8', padding: 20, paddingTop: 36 },
  topbar: { width: '100%', padding: 12, paddingTop: 16, borderRightWidth: 0, borderBottomWidth: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  brand: { fontSize: 32, fontWeight: '600', color: '#343941', marginBottom: 56 }, smallBrand: { fontSize: 23, marginBottom: 0 },
  links: { gap: 8 }, horizontal: { flexDirection: 'row', gap: 4 },
  link: { padding: 12, borderRadius: 12, fontSize: 17, color: '#343941' }, current: { backgroundColor: '#eff0f2', fontWeight: '600' },
  content: { flex: 1, minWidth: 0, minHeight: 0 },
});
