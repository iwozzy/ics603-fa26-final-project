import { defineConfig } from 'eslint/config';
import expo from 'eslint-config-expo/flat.js';
import boundaries from 'eslint-plugin-boundaries';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const element = type => ({ element: { type } });
const layers = [
  ['domain', ['domain']],
  ['application', ['domain', 'application']],
  ['api', ['domain', 'application', 'api', 'generated']],
  ['ui', ['domain', 'application', 'ui']],
  ['route', ['ui', 'route']],
  ['bootstrap', ['domain', 'application', 'api', 'ui', 'bootstrap']],
  ['generated', ['generated']],
];
const policies = [
  ...layers.map(([from, to]) => ({ from: element(from), allow: { to: element(to) } })),
  { from: element(['api', 'ui', 'route', 'bootstrap', 'generated']), allow: { to: { module: { origin: 'external' } } } },
];
const isolateGenerated = { from: element(['domain','application','ui','route','bootstrap','test']), disallow: { to: element('generated') } };
const rule = extra => ['error', { default: 'disallow', checkAllOrigins: true, checkInternals: true, checkUnknownLocals: true, policies: [...policies, ...extra, isolateGenerated] }];
export default defineConfig([
  expo,
  { ignores: ['dist/**', '.expo/**'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: { boundaries },
    settings: {
      'boundaries/root-path': path.dirname(fileURLToPath(import.meta.url)),
      'boundaries/elements': [
        { type: 'generated', pattern: 'src/adapters/outbound/api/generated', partialMatch: false },
        { type: 'api', pattern: 'src/adapters/outbound/api', partialMatch: false },
        { type: 'ui', pattern: 'src/adapters/inbound/ui', partialMatch: false },
        ...['domain','application','bootstrap'].map(type => ({ type, pattern: 'src/' + type, partialMatch: false })),
        { type: 'route', pattern: 'src/app', partialMatch: false },
        { type: 'test', pattern: 'src/test-utils', partialMatch: false },
      ],
    },
    rules: {
      'boundaries/dependencies': rule([]),
      'boundaries/no-unknown-files': 'error',
      'boundaries/no-unknown-dependencies': 'error',
    },
  },
  { files: ['src/app/_layout.tsx'], rules: { 'boundaries/dependencies': rule([{ from: element('route'), allow: { to: element('bootstrap') } }]) } },
  { files: ['src/**/*.test.{ts,tsx}', 'src/test-utils/**/*.{ts,tsx}'], rules: { 'boundaries/dependencies': rule([{ allow: { to: { module: { origin: ['local', 'external', 'core'] } } } }]) } },
  { files: ['src/adapters/outbound/api/generated/*.ts'], rules: { '@typescript-eslint/array-type': 'off' } },
  { files: ['src/domain/**/*.ts', 'src/application/**/*.ts'], ignores: ['**/*.test.ts'], rules: { 'no-restricted-globals': ['error', 'fetch', 'XMLHttpRequest'] } },
]);
