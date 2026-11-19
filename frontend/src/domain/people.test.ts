import { InvalidQuery } from './errors';
import { normalizeQuery } from './people';
test.each([[' x ', 'x'], ['😀'.repeat(200), '😀'.repeat(200)], [" Timothée O'Neil & 李😀 ", "Timothée O'Neil & 李😀"]])('normalizes code points %s', (raw, expected) => { expect(normalizeQuery(raw)).toBe(expected); });
test.each(['', '   ', '😀'.repeat(201)])('rejects invalid query', (raw) => { expect(() => normalizeQuery(raw)).toThrow(InvalidQuery); });
