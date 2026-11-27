import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';

interface Scenario { delayMs?: number; empty?: boolean; status?: number; prefix?: string; personIds?: number[] }
interface Filmography { body?: object; status?: number; delayMs?: number; retryAfter?: string }
interface Control {
  scenarios?: Record<string, Scenario>;
  filmographies?: Record<string, Filmography>;
}
const fixture = JSON.parse(await readFile(process.env.LUMIERE_TEST_FIXTURE_PATH ?? new URL('../../docs/samples/api/tmdb/v3/search/person.json', import.meta.url), 'utf8')) as { results: { name: string; [key: string]: unknown }[] };

function emptyCounts() {
  return {
    total: 0, completed: 0, byQuery: {} as Record<string, number>,
    filmographyTotal: 0, filmographyCompleted: 0, byPerson: {} as Record<string, number>,
  };
}
let control: Control = {};
let counts = emptyCounts();
createServer(async (request, response) => {
  const url = new URL(request.url ?? '/', 'http://fixture.test');
  response.setHeader('Content-Type', 'application/json');
  response.setHeader('Cache-Control', 'no-store');
  if (url.pathname === '/health') { response.end('{}'); return; }
  if (url.pathname === '/__counts') { response.end(JSON.stringify(counts)); return; }
  if (url.pathname === '/__control' && request.method === 'POST') {
    let body = '';
    for await (const chunk of request) body += String(chunk);
    control = JSON.parse(body || '{}') as Control;
    counts = emptyCounts();
    response.end('{}');
    return;
  }

  // A delayed response belongs to the test that started it, even after a fixture reset.
  const current = counts;
  const person = /^\/3\/person\/(\d+)$/.exec(url.pathname)?.[1];
  if (request.method === 'GET' && person && url.searchParams.get('append_to_response') === 'movie_credits') {
    const film = control.filmographies?.[person] ?? { status: 404 };
    current.filmographyTotal++;
    current.byPerson[person] = (current.byPerson[person] ?? 0) + 1;
    if (film.delayMs) await new Promise(resolve => setTimeout(resolve, film.delayMs));
    current.filmographyCompleted++;
    response.statusCode = film.status ?? 200;
    if (film.retryAfter !== undefined) response.setHeader('Retry-After', film.retryAfter);
    response.end(JSON.stringify(film.body ?? {}));
    return;
  }
  if (url.pathname !== '/3/search/person') { response.statusCode = 404; response.end('{}'); return; }
  const query = url.searchParams.get('query') ?? '';
  current.total++;
  current.byQuery[query] = (current.byQuery[query] ?? 0) + 1;
  const scenario = control.scenarios?.[query] ?? {};
  if (scenario.delayMs) await new Promise(resolve => setTimeout(resolve, scenario.delayMs));
  current.completed++;
  response.statusCode = scenario.status ?? 200;
  const selected = scenario.personIds ? fixture.results.filter(person => scenario.personIds!.includes(Number(person.id))) : fixture.results;
  const results = scenario.empty ? [] : selected.map(person => ({ ...person, name: (scenario.prefix ?? '') + person.name }));
  response.end(JSON.stringify({ ...fixture, results }));
}).listen(9000, '0.0.0.0');
