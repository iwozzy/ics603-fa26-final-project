import '../../global.css';

import { Stack } from 'expo-router';
import { GluestackUIProvider } from '../adapters/ui/GluestackUIProvider';

export default function RootLayout() {
  return (
    <GluestackUIProvider>
      <Stack screenOptions={{ headerShown: false }} />
    </GluestackUIProvider>
  );
}
