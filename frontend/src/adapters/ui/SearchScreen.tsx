import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import Svg, { Circle, Line } from 'react-native-svg';

import {
  SearchController,
  type SearchPeople,
} from '../../application/search-people';
import { Button } from './Button';
import { PersonRow } from './PersonRow';

const examples = [
  ['Timothée Chalamet', 'Actor'],
  ['Hayao Miyazaki', 'Director, Writer'],
  ['Autumn Durald Arkapaw', 'Cinematographer'],
] as const;

export function SearchScreen({
  search,
  logFailure = console.info,
}: {
  search: SearchPeople;
  logFailure?: (message: string) => void;
}) {
  const controller = useRef<SearchController | null>(null);
  const [state, setState] = useState(() => new SearchController(search).state);
  useEffect(() => {
    const current = new SearchController(search, logFailure);
    controller.current = current;
    const unsubscribe = current.subscribe(() => setState(current.state));
    return () => {
      unsubscribe();
      current.dispose();
      controller.current = null;
    };
  }, [search, logFailure]);
  const submit = () => {
    void controller.current?.submit();
  };
  return (
    <ScrollView
      className="flex-1 bg-white"
      contentContainerClassName="min-h-screen items-center px-5 pb-10 pt-24 md:pt-40"
    >
      <View className="w-full max-w-3xl">
        <View className="mb-7 flex-row items-center justify-center gap-6">
          <Text
            role="heading"
            className="border-b-2 border-slate-900 pb-2 text-xl font-semibold text-slate-900"
          >
            Cast &amp; Crew
          </Text>
          <Button isDisabled accessibilityLabel="Movies" className="pb-2">
            <Text className="text-xl text-slate-400">Movies</Text>
          </Button>
        </View>
        <View className="flex-row items-center gap-2 rounded-2xl border border-slate-300 p-3">
          <TextInput
            accessibilityLabel="Search people"
            placeholder="Search for actors, directors, or creative team to follow"
            placeholderTextColor="#64748b"
            value={state.draft}
            onChangeText={(value) => controller.current?.edit(value)}
            onSubmitEditing={submit}
            className="min-w-0 flex-1 rounded-lg p-2 text-base text-slate-900"
          />
          <Button
            accessibilityLabel="Search"
            onPress={submit}
            className="h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-200"
          >
            <View
              testID="search-icon"
              accessible={false}
              accessibilityElementsHidden
            >
              <Svg
                width={20}
                height={20}
                viewBox="0 0 24 24"
                fill="none"
                stroke="#64748b"
                strokeWidth={1.75}
              >
                <Circle cx={10} cy={10} r={6} />
                <Line
                  x1={14.5}
                  y1={14.5}
                  x2={21}
                  y2={21}
                  strokeLinecap="round"
                />
              </Svg>
            </View>
          </Button>
          {state.loading ? (
            <ActivityIndicator accessibilityLabel="Searching" />
          ) : null}
        </View>
        <Text accessibilityLiveRegion="polite" className="sr-only">
          {state.loading
            ? 'Searching'
            : state.results.length
              ? `${state.results.length} ${state.results.length === 1 ? 'person' : 'people'} found`
              : ''}
        </Text>
        {state.results.length ? (
          <View className="mt-5">
            {state.results.map((person, index) => (
              <PersonRow key={`${state.submitted}-${index}`} person={person} />
            ))}
          </View>
        ) : (
          <View className="mt-8 gap-3">
            <Text className="mb-1 text-sm text-slate-500">Try a search</Text>
            {examples.map(([name, role]) => (
              <Button
                key={name}
                accessibilityLabel={`Search for ${name}`}
                onPress={() => {
                  controller.current?.edit(name);
                  submit();
                }}
                className="rounded-xl p-3"
              >
                <View className="min-w-0 flex-1">
                  <Text className="text-base font-medium text-slate-800">
                    {name}
                  </Text>
                  <Text className="mt-1 text-sm text-slate-500">{role}</Text>
                </View>
              </Button>
            ))}
          </View>
        )}
      </View>
    </ScrollView>
  );
}
