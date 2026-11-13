import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 20_000,
  use: { baseURL: 'http://127.0.0.1:8765', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'uv run uvicorn server:app --app-dir tests/support --host 127.0.0.1 --port 8765 --no-access-log',
    env: { PYTHONPATH: 'backend' },
    url: 'http://127.0.0.1:8765',
    reuseExistingServer: false,
  },
});
