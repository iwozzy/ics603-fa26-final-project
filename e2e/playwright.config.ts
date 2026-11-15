import { defineConfig, devices } from '@playwright/test';
export default defineConfig({ testDir: './tests', timeout: 30000, expect: { timeout: 10000 }, workers: 1, retries: 0, globalSetup: './support/stack.ts', use: { baseURL: 'http://127.0.0.1:18080', ...devices['Desktop Chrome'], trace: 'off', screenshot: 'only-on-failure' }, reporter: 'list' });
