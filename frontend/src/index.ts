import { registerRootComponent } from 'expo';
import { createElement } from 'react';
import App from './App';
import { httpPeopleSearch } from './search/backend';

function Root() {
  return createElement(App, { peopleSearch: httpPeopleSearch });
}

registerRootComponent(Root);
