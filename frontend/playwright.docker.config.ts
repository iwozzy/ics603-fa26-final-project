import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './docker-e2e',
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  use: {
    baseURL: process.env.LUMIERE_DOCKER_URL ?? 'http://127.0.0.1:8080',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
