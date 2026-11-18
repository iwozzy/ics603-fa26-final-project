import { createPeopleSearch } from '../adapters/http/search-people';
import { SearchScreen } from '../adapters/ui/SearchScreen';

const search = createPeopleSearch(
  process.env.EXPO_PUBLIC_API_URL ?? 'http://127.0.0.1:8000',
);

export default function Index() {
  return <SearchScreen search={search} />;
}
