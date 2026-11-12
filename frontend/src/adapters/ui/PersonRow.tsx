import { useState } from 'react';
import { Image, Text, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';

import type { PersonSummary } from '../../application/search-people';
import { Button } from './Button';

export function PersonRow({ person }: { person: PersonSummary }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const [hovered, setHovered] = useState(false);
  const hints = [person.department, person.knownFor.slice(0, 3).join(', ')]
    .filter(Boolean)
    .join(' • ');
  return (
    <View
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      className="flex-row items-center gap-3 rounded-xl py-4"
    >
      <View className="h-12 w-12 shrink-0 overflow-hidden rounded-full bg-slate-100">
        {person.portraitUrl && failedUrl !== person.portraitUrl ? (
          <Image
            testID="portrait"
            accessible={false}
            accessibilityElementsHidden
            source={{ uri: person.portraitUrl }}
            onError={() => setFailedUrl(person.portraitUrl)}
            className="h-12 w-12"
          />
        ) : (
          <View
            testID="portrait-fallback"
            accessible={false}
            accessibilityElementsHidden
          >
            <Svg width={48} height={48} viewBox="0 0 48 48">
              <Circle cx={24} cy={17} r={8} fill="#94a3b8" />
              <Path d="M8 46v-5a16 16 0 0 1 32 0v5" fill="#94a3b8" />
            </Svg>
          </View>
        )}
      </View>
      <View className="min-w-0 flex-1">
        <Text className="text-base font-semibold text-slate-900">
          {person.name}
        </Text>
        {hints ? (
          <Text className="mt-1 text-sm leading-5 text-slate-500">{hints}</Text>
        ) : null}
      </View>
      <Button
        isDisabled
        accessibilityLabel={`Follow ${person.name}`}
        style={{ opacity: hovered ? 1 : 0 }}
        className="rounded-lg border border-slate-300 px-3 py-2"
      >
        <Text className="text-slate-500">Follow +</Text>
      </Button>
    </View>
  );
}
