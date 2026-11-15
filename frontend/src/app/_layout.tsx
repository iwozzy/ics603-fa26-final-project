import { Stack } from 'expo-router';
import { Providers } from '../bootstrap/Providers';
export default function Layout() { return <Providers><Stack screenOptions={{ headerShown: false, title: 'Lumiere' }} /></Providers>; }
