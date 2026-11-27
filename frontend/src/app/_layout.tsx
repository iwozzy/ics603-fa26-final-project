import { Stack } from 'expo-router';
import { AppShell } from '../adapters/inbound/ui/AppShell';
import { Providers } from '../bootstrap/Providers';
export default function Layout() {
  return <Providers><AppShell>
    <Stack screenOptions={{ headerShown: false, title: 'Lumiere' }}>
      <Stack.Screen name="index" dangerouslySingular />
      <Stack.Screen name="timeline" dangerouslySingular />
      <Stack.Screen name="following" dangerouslySingular />
    </Stack>
  </AppShell></Providers>;
}
