import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../../', import.meta.url));
async function compose(args: string[]) {
  await new Promise<void>((resolve, reject) => {
    const child = spawn('docker', ['compose', '--env-file', '/dev/null', '-p', 'lumiere-e2e', '-f', 'compose.test.yaml', '--profile', 'e2e', ...args], { cwd: root, stdio: 'inherit', env: { ...process.env, LUMIERE_TEST_DB_PORT: '15433' } });
    child.once('error', reject);
    child.once('exit', code => code === 0 ? resolve() : reject(new Error(`isolated Compose exited ${code}`)));
  });
}
export default async function setup() {
  try {
    await compose(['up', '-d', '--build', '--wait', 'postgres', 'tmdb', 'backend', 'web']);
    await compose(['run', '--rm', '--no-deps', 'backend', 'alembic', 'upgrade', 'head']);
  } catch (error) { await compose(['down', '--volumes', '--remove-orphans']); throw error; }
  return async () => { await compose(['down', '--volumes', '--remove-orphans']); };
}
