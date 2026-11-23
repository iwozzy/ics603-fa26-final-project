import { Stack } from 'expo-router';
import { AppShell } from '../adapters/inbound/ui/AppShell';
import { Providers } from '../bootstrap/Providers';
export default function Layout() { return <Providers><AppShell><Stack screenOptions={{ headerShown: false, title: 'Lumiere' }} /></AppShell></Providers>; }
