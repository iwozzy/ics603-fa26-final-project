import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppShell } from '../adapters/inbound/ui/AppShell';
import { useTheme } from '../adapters/inbound/ui/theme';
import { Providers } from '../bootstrap/Providers';
export default function Layout() {
  const colors = useTheme();
  return <Providers><AppShell>
    <StatusBar style="auto" />
    <Stack screenOptions={{ headerShown: false, title: 'Lumiere', contentStyle: { backgroundColor: colors.background } }}>
      <Stack.Screen name="index" dangerouslySingular />
      <Stack.Screen name="timeline" dangerouslySingular />
      <Stack.Screen name="following" dangerouslySingular />
    </Stack>
  </AppShell></Providers>;
}
