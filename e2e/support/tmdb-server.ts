import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';

interface Scenario { delayMs?: number; empty?: boolean; status?: number; prefix?: string; }
const fixture = JSON.parse(await readFile(process.env.FIXTURE_PATH ?? new URL('../../docs/samples/api/tmdb/v3/search/person.json', import.meta.url), 'utf8')) as { results: { name: string; [key: string]: unknown }[] };
let scenarios: Record<string, Scenario> = {};
let total = 0;
let completed = 0;
let byQuery: Record<string, number> = {};
createServer(async (request, response) => {
  const url = new URL(request.url ?? '/', 'http://fixture.test');
  response.setHeader('Content-Type', 'application/json'); response.setHeader('Cache-Control', 'no-store');
  if (url.pathname === '/health') { response.end('{}'); return; }
  if (url.pathname === '/__counts') { response.end(JSON.stringify({ total, completed, byQuery })); return; }
  if (url.pathname === '/__control' && request.method === 'POST') {
    let body = ''; for await (const chunk of request) body += String(chunk);
    scenarios = (JSON.parse(body || '{}') as { scenarios?: Record<string, Scenario> }).scenarios ?? {};
    total = 0; completed = 0; byQuery = {}; response.end('{}'); return;
  }
  if (url.pathname !== '/3/search/person') { response.statusCode = 404; response.end('{}'); return; }
  const query = url.searchParams.get('query') ?? '';
  total++; byQuery[query] = (byQuery[query] ?? 0) + 1;
  const scenario = scenarios[query] ?? {};
  if (scenario.delayMs) await new Promise(resolve => setTimeout(resolve, scenario.delayMs));
  completed++;
  response.statusCode = scenario.status ?? 200;
  const results = scenario.empty ? [] : fixture.results.map(person => ({ ...person, name: (scenario.prefix ?? '') + person.name }));
  response.end(JSON.stringify({ ...fixture, results }));
}).listen(9000, '0.0.0.0');
