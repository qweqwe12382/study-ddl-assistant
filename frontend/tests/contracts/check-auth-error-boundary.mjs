import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'

// Run the real Axios interceptors. Only Vite's build-time env is substituted;
// the adapter replaces network transport with explicit server responses.
const hooks = registerHooks({
  resolve(specifier, context, next) {
    if (specifier === '../utils/apiBaseUrl' && context.parentURL.endsWith('/src/api/http.js')) {
      return next(`${specifier}.js`, context)
    }
    return next(specifier, context)
  },
  load(url, context, next) {
    const loaded = next(url, context)
    if (!url.endsWith('/src/api/http.js')) return loaded
    return { ...loaded, source: loaded.source.toString().replaceAll('import.meta.env', '({ DEV: true })') }
  },
})
const events = []
globalThis.window = {
  location: { hostname: 'localhost' },
  FormData,
  CustomEvent: class { constructor(type) { this.type = type } },
  dispatchEvent(event) { events.push(event.type) },
}
globalThis.document = { cookie: '' }

try {
  const { default: http } = await import('../../src/api/http.js')
  for (const [code, status, expired] of [
    ['NJUST_AUTH_FAILED', 401, false],
    ['INVALID_CREDENTIALS', 401, false],
    ['UPSTREAM_UNAUTHORIZED', 401, false],
    ['AUTH_REQUIRED', 401, true],
    ['CSRF_INVALID', 403, false],
  ]) {
    events.length = 0
    await assert.rejects(http.get('/test', { adapter: async (config) => {
      throw { config, response: { status, data: { error: { code, message: `message:${code}` } } } }
    } }), (error) => {
      assert.equal(error.code, code)
      assert.equal(error.status, status)
      assert.equal(error.message, `message:${code}`)
      return true
    })
    assert.deepEqual(events, expired ? ['study-auth-expired'] : [], code)
  }
} finally {
  hooks.deregister()
  delete globalThis.window
  delete globalThis.document
}
console.log('Authentication error boundary passed: only site session expiry clears login.')
