import { rm } from 'node:fs/promises';

// npm ci removes existing packages without retrying transient filesystem errors.
await rm(new URL('../node_modules', import.meta.url), {
  recursive: true,
  force: true,
  maxRetries: 5,
  retryDelay: 200,
});
