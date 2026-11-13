const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');
const prettierConfig = require('eslint-config-prettier/flat');

module.exports = defineConfig([
  expoConfig,
  {
    rules: {
      complexity: ['error', { max: 10 }],
    },
  },
  {
    ignores: [
      'dist/**',
      '.expo/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      'src/api.generated.ts',
    ],
  },
  prettierConfig,
]);
