import { execFileSync, spawnSync } from 'node:child_process';
import { writeFileSync, unlinkSync, mkdirSync } from 'node:fs';
import path from 'node:path';
const root = path.resolve(__dirname, '../..');
const eslint = path.join(root, 'node_modules/eslint/bin/eslint.js');

test.each([
  ['domain/_architecture_probe.ts', "import 'react';"],
  ['application/_architecture_probe.ts', "import '../adapters/outbound/api/mappers';"],
  ['adapters/inbound/ui/_architecture_probe.ts', "import '../../outbound/api/generated/zod.gen';"],
  ['adapters/inbound/ui/_architecture_probe.ts', "import '../../../bootstrap/container';"],
  ['app/_architecture_probe.tsx', "import '../bootstrap/Providers';"],
])('real ESLint rejects %s', (relative, source) => {
  const probe = path.join(root, 'src', relative);
  mkdirSync(path.dirname(probe), { recursive: true }); writeFileSync(probe, source);
  try {
    const result = spawnSync(process.execPath, [eslint, probe, '--no-cache'], { cwd: root, encoding: 'utf8' });
    expect(result.status).toBe(1); expect(result.stdout).toContain('boundaries/dependencies');
  } finally { unlinkSync(probe); }
});
test('real tree and layout composition pass ESLint', () => { execFileSync(process.execPath, [eslint, 'src', '--max-warnings=0'], { cwd: root }); });
