import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'

// Exercise the public API and download function while isolating HTTP and UI
// dependencies. The configured host must also be used by file downloads.
const httpModule = `data:text/javascript,${encodeURIComponent(`
  export const apiBaseUrl = 'http://localhost:8123/custom/api';
  export const requests = [];
  export let failure;
  export function failWith(error) { failure = error; }
  export default { async get(url, config) {
    requests.push({ url, config });
    if (failure) throw failure;
    return new Blob(['测试内容'], { type: 'text/plain' });
  }};
`)}`
const messageModule = `data:text/javascript,${encodeURIComponent(`
  export const messages = [];
  export const ElMessage = { error: message => messages.push(message) };
`)}`
const hooks = registerHooks({
  resolve(specifier, context, next) {
    if ((specifier === './http' && context.parentURL.endsWith('/src/api/index.js'))
      || (specifier === '../api/http' && context.parentURL.endsWith('/src/utils/download.js'))) {
      return { url: httpModule, shortCircuit: true }
    }
    if (specifier === 'element-plus' && context.parentURL.endsWith('/src/utils/download.js')) {
      return { url: messageModule, shortCircuit: true }
    }
    return next(specifier, context)
  },
})

const anchors = []
const timers = []
const blobs = []
const revoked = []
globalThis.window = {
  location: { href: 'http://localhost:5191/tasks' },
  URL: class extends URL {
    static createObjectURL(blob) { blobs.push(blob); return 'blob:verified-download' }
    static revokeObjectURL(url) { revoked.push(url) }
  },
  setTimeout: (callback, delay) => timers.push({ callback, delay }),
}
globalThis.document = {
  body: { appendChild: link => anchors.push(link) },
  createElement: tag => {
    assert.equal(tag, 'a')
    return { click() { this.clicked = true }, remove() { this.removed = true } }
  },
}

try {
  const { materialsApi, exportsApi } = await import('../../src/api/index.js')
  const { downloadFile } = await import('../../src/utils/download.js')
  const { requests, failWith } = await import(httpModule)
  const { messages } = await import(messageModule)
  assert.deepEqual([
    materialsApi.fileUrl(4), exportsApi.tasksCsvUrl(), exportsApi.tasksCalendarUrl(),
    exportsApi.materialsMarkdownUrl(), exportsApi.studyPlanMarkdownUrl(3),
  ], [
    '/materials/4/file', '/exports/tasks.csv', '/exports/tasks.ics',
    '/exports/materials.md', '/exports/study-plans/3.md',
  ].map(path => `http://localhost:8123/custom/api${path}`))

  assert.equal(await downloadFile(exportsApi.tasksCsvUrl()), true)
  assert.deepEqual(requests[0], { url: exportsApi.tasksCsvUrl(), config: { responseType: 'blob' } })
  assert.equal(await blobs[0].text(), '测试内容')
  assert.equal(anchors[0].download, 'tasks.csv')
  assert.equal(anchors[0].href, 'blob:verified-download')
  assert.equal(anchors[0].target, undefined, 'downloads do not require a popup')
  assert.equal(anchors[0].clicked, true)
  assert.equal(anchors[0].removed, true)
  assert.equal(revoked.length, 0, 'retain the blob while the browser starts saving')
  timers[0].callback()
  assert.deepEqual(revoked, ['blob:verified-download'])

  assert.equal(await downloadFile(materialsApi.fileUrl(4), '英语复习提纲.txt'), true)
  assert.equal(anchors[1].download, '英语复习提纲.txt', 'keep the original filename')
  failWith(new Error('请求超时，请稍后重试'))
  assert.equal(await downloadFile(exportsApi.tasksCsvUrl()), false)
  assert.equal(anchors.length, 2, 'do not save an error response as a file')
  assert.deepEqual(messages, ['请求超时，请稍后重试'])
  assert.equal(timers.length, 2, 'failed requests do not create blob cleanup jobs')
} finally {
  hooks.deregister()
  delete globalThis.window
  delete globalThis.document
}
console.log('Authenticated download URLs, files, cleanup, and failures passed.')
