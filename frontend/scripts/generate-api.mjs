import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import openapiTS, { astToString } from 'openapi-typescript';

const backend = fileURLToPath(new URL('../../backend/', import.meta.url));
const output = new URL(
  '../src/adapters/http/generated/api.d.ts',
  import.meta.url,
);
const schema = execFileSync(
  'uv',
  ['run', '--locked', 'python', 'scripts/export_openapi.py'],
  {
    cwd: backend,
    encoding: 'utf8',
    env: { ...process.env, APP_TELEMETRY_ENABLED: 'false' },
  },
);
const generated = astToString(await openapiTS(JSON.parse(schema)));

if (process.argv.includes('--check')) {
  if (readFileSync(output, 'utf8') !== generated) {
    throw new Error('API types are stale. Run npm run api:generate.');
  }
  console.log('API types match OpenAPI.');
} else {
  mkdirSync(new URL('../src/adapters/http/generated/', import.meta.url), {
    recursive: true,
  });
  writeFileSync(output, generated);
  console.log('Generated API types.');
}
