import assert from 'node:assert/strict'
import { resolveApiBaseUrl } from '../../src/utils/apiBaseUrl.js'

assert.equal(resolveApiBaseUrl('http://localhost:8000/api', '127.0.0.1', true), 'http://127.0.0.1:8000/api')
assert.equal(resolveApiBaseUrl(undefined, 'localhost', true), 'http://localhost:8000/api')
assert.equal(resolveApiBaseUrl('http://127.0.0.1:8010/api', 'localhost', true), 'http://localhost:8010/api')
assert.equal(resolveApiBaseUrl('http://localhost:8000/api', '127.0.0.1', false), 'http://localhost:8000/api')
assert.equal(resolveApiBaseUrl('https://localhost:8000/api', '127.0.0.1', true), 'https://localhost:8000/api')
assert.equal(resolveApiBaseUrl('https://api.example.test/api', 'localhost', true), 'https://api.example.test/api')
assert.equal(resolveApiBaseUrl('http://localhost:8000/api', 'example.test', true), 'http://localhost:8000/api')
assert.equal(resolveApiBaseUrl('/api', 'localhost', true), '/api')
console.log('API base URL contract check passed')
