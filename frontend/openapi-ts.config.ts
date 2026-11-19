import { defineConfig } from '@hey-api/openapi-ts';
export default defineConfig({ input: '../openapi.json', output: 'src/adapters/outbound/api/generated', plugins: ['@hey-api/typescript', { name: 'zod', definitions: true, requests: false, responses: false }] });
