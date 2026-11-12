import { Text, View } from 'react-native';

export function StartupScreen() {
  return (
    <View className="flex-1 items-center justify-center bg-white p-6">
      <Text role="heading" className="text-3xl font-semibold text-slate-900">
        Lumiere
      </Text>
      <Text className="mt-3 text-base text-slate-600">
        Application scaffold is ready.
      </Text>
    </View>
  );
}
