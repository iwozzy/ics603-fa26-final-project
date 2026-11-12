const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    rules: {
      complexity: ['error', { max: 10 }],
    },
  },
  {
    files: ['**/*.cjs'],
    languageOptions: { globals: { __dirname: 'readonly' } },
  },
  {
    ignores: [
      'dist/**',
      '.expo/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      'src/adapters/http/generated/**',
      'src/uniwind-types.d.ts',
    ],
  },
  {
    files: ['src/application/**/*.{ts,tsx}', 'src/domain/**/*.{ts,tsx}'],
    languageOptions: {
      globals: {
        window: 'off',
        document: 'off',
        fetch: 'off',
        localStorage: 'off',
        navigator: 'off',
      },
    },
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: [
                'react',
                'react/**',
                'react-*',
                'react-*/**',
                'react-dom',
                'react-dom/**',
                'react-native',
                'react-native/**',
                'expo',
                'expo-*',
                'expo/**',
                '@expo/**',
                '@gluestack-ui/**',
                'uniwind',
                'uniwind/**',
              ],
              message: 'Core modules must be independent of UI frameworks.',
            },
            {
              group: [
                '**/adapters',
                '**/adapters/**',
                '**/bootstrap*',
                '**/app',
                '**/app/**',
              ],
              message:
                'Core modules must not depend on adapters or composition roots.',
            },
          ],
        },
      ],
      'no-restricted-globals': [
        'error',
        'window',
        'document',
        'fetch',
        'localStorage',
        'sessionStorage',
        'navigator',
        'XMLHttpRequest',
      ],
    },
  },
]);
