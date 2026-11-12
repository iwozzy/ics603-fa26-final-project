import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:8081' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command:
        'uv run --locked uvicorn lumiere.bootstrap:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/health',
      env: { APP_TELEMETRY_ENABLED: 'false' },
      timeout: 30_000,
    },
    {
      command: 'npm start -- --port 8081',
      url: 'http://127.0.0.1:8081',
      env: { CI: '1' },
      timeout: 120_000,
    },
  ],
});
