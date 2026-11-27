import { useMemo } from 'react';
import { useColorScheme } from 'react-native';

const light = {
  background: '#fff',
  surface: '#eff0f2',
  text: '#22262c',
  heading: '#24282d',
  body: '#343941',
  secondary: '#59616b',
  muted: '#6c737c',
  hint: '#737b85',
  placeholder: '#9299a2',
  border: '#c3c7cc',
  divider: '#e1e4e8',
  avatarBorder: '#c8ccd1',
  silhouette: '#8a939e',
  focus: '#4279b2',
  button: '#e3e7ec',
  icon: '#697786',
  spinner: '#667180',
};

export type ThemeColors = typeof light;

const dark: ThemeColors = {
  background: '#15181d',
  surface: '#252b33',
  text: '#f0f2f5',
  heading: '#f0f2f5',
  body: '#d8dde5',
  secondary: '#b4becb',
  muted: '#aab4c1',
  hint: '#aab4c1',
  placeholder: '#9aa5b3',
  border: '#596575',
  divider: '#343d49',
  avatarBorder: '#596575',
  silhouette: '#9aa5b3',
  focus: '#80b7f0',
  button: '#343d49',
  icon: '#c3cedb',
  spinner: '#c3cedb',
};

export function useTheme(): ThemeColors {
  return useColorScheme() === 'dark' ? dark : light;
}

export function useThemedStyles<T>(createStyles: (colors: ThemeColors) => T): T {
  const colors = useTheme();
  return useMemo(() => createStyles(colors), [colors, createStyles]);
}
