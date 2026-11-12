import assert from 'node:assert/strict';

import { ESLint } from 'eslint';

const eslint = new ESLint();
const filePath = 'src/application/boundary-probe.ts';
for (const code of [
  "import 'react';",
  "import 'expo-router';",
  "import '../adapters/http/search-people';",
  "fetch('https://example.invalid');",
  'window.location;',
  'localStorage.clear();',
]) {
  const [result] = await eslint.lintText(code, { filePath });
  assert(
    result.messages.some((message) =>
      ['no-restricted-imports', 'no-restricted-globals'].includes(
        message.ruleId,
      ),
    ),
    `Boundary accepted: ${code}`,
  );
}
const [allowed] = await eslint.lintText('export const value = 1;', {
  filePath,
});
assert.equal(allowed.errorCount, 0);
console.log(
  'Frontend dependency boundaries reject forbidden imports and browser globals.',
);
