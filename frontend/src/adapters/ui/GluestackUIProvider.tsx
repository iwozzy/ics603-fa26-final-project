import { useEffect, type PropsWithChildren } from 'react';
import { View } from 'react-native';
import { Uniwind } from 'uniwind';

export function GluestackUIProvider({ children }: PropsWithChildren) {
  useEffect(() => {
    Uniwind.setTheme('light');
  }, []);
  return <View className="flex-1 bg-white">{children}</View>;
}
