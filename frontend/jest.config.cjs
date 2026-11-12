module.exports = {
  preset: 'jest-expo',
  testMatch: ['<rootDir>/tests/**/*.test.ts?(x)'],
  moduleNameMapper: { '\\.(css)$': '<rootDir>/tests/style-mock.cjs' },
};
