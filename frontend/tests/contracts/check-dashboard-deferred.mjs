import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'
import { parse as parseJs } from '@babel/parser'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import { createRenderer, defineComponent, h, nextTick } from 'vue'

const frontend = fileURLToPath(new URL('../..', import.meta.url))
const componentPaths = [
  'src/views/DashboardView.vue',
  'src/components/dashboard/DashboardDeferredPanel.vue',
  'src/components/dashboard/DashboardReviewInsights.vue',
  'src/components/dashboard/EstimateActionDialog.vue',
]
const descriptors = new Map()
for (const componentPath of componentPaths) {
  const source = await readFile(path.join(frontend, componentPath), 'utf8')
  const { descriptor, errors } = parse(source, { filename: componentPath })
  assert.deepEqual(errors, [], `${componentPath} parses`)
  const script = compileScript(descriptor, { id: componentPath })
  const template = compileTemplate({
    source: descriptor.template.content,
    filename: componentPath,
    id: componentPath,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(template.errors, [], `${componentPath} compiles with its bindings`)
  descriptors.set(componentPath, descriptor)
}

// Mount the real deferred boundary with a tiny renderer. A failed download
// must stay retryable, and cancel must work both before and after loading.
const deferred = descriptors.get(componentPaths[1])
const compiled = compileScript(deferred, { id: 'deferred-test', inlineTemplate: true }).content
  .replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
const { default: DeferredPanel } = await import(`data:text/javascript,${encodeURIComponent(compiled)}`)
function node(type, text = '') { return { type, text, props: {}, children: [], parent: null } }
const renderer = createRenderer({
  createElement: (tag) => node(tag),
  createText: (text) => node('text', text),
  createComment: (text) => node('comment', text),
  setText: (target, text) => { target.text = text },
  setElementText: (target, text) => { target.text = text; target.children = [] },
  patchProp: (target, key, _previous, value) => { target.props[key] = value },
  parentNode: (target) => target.parent,
  nextSibling: (target) => target.parent?.children[target.parent.children.indexOf(target) + 1] || null,
  insert(target, parent, anchor = null) {
    if (target.parent) target.parent.children.splice(target.parent.children.indexOf(target), 1)
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, target)
    target.parent = parent
  },
  remove(target) {
    target.parent?.children.splice(target.parent.children.indexOf(target), 1)
    target.parent = null
  },
})
function find(root, predicate) {
  if (predicate(root)) return root
  for (const child of root.children) {
    const match = find(child, predicate)
    if (match) return match
  }
  return null
}
async function flush() { await Promise.resolve(); await nextTick(); await nextTick() }
let attempts = 0
let cancels = 0
let failFirst
let childValue
const loadedChild = defineComponent({
  props: { value: Number },
  emits: ['cancel'],
  setup(props, { emit }) {
    childValue = props.value
    return () => h('button', { onClick: () => emit('cancel') }, '已加载的取消按钮')
  },
})
const app = renderer.createApp(DeferredPanel, {
  label: '复盘',
  cancelable: true,
  value: 7,
  onCancel: () => { cancels++ },
  loader: () => {
    attempts++
    return attempts === 1
      ? new Promise((_resolve, reject) => { failFirst = reject })
      : Promise.resolve({ default: loadedChild })
  },
})
assert.equal(attempts, 0, 'does not start fetching before the boundary is mounted')
const root = node('root')
app.mount(root)
assert.equal(attempts, 1)
find(root, (item) => item.type === 'button' && item.text === '取消').props.onClick()
assert.equal(cancels, 1, 'can cancel while the component download is pending')
failFirst(new Error('temporary chunk download failure'))
await flush()
assert.ok(find(root, (item) => item.props.role === 'alert'), 'announces failed downloads')
const retry = find(root, (item) => item.type === 'button' && item.text.includes('重新加载'))
retry.props.onClick()
await flush()
assert.equal(attempts, 2, 'retry requests the component again')
assert.equal(childValue, 7, 'forwards component props after loading')
find(root, (item) => item.type === 'button').props.onClick()
assert.equal(cancels, 2, 'forwards child cancel events after loading')
app.unmount()

// Check the built dependency graph, rather than just looking for import().
// Neither low-frequency panel may be reachable via an initial static import.
const assets = path.join(frontend, 'dist/assets')
const assetNames = await readdir(assets)
function assetFor(name) {
  const matches = assetNames.filter((file) => file.startsWith(`${name}-`) && file.endsWith('.js'))
  assert.equal(matches.length, 1, `${name} has one separate production chunk`)
  return matches[0]
}
const dashboard = assetFor('DashboardView')
const deferredAssets = [assetFor('DashboardReviewInsights'), assetFor('EstimateActionDialog')]
const visited = new Set()
async function visit(file) {
  if (visited.has(file)) return
  visited.add(file)
  const source = await readFile(path.join(assets, file), 'utf8')
  const imports = parseJs(source, { sourceType: 'module' }).program.body
    .filter((item) => item.type === 'ImportDeclaration' || item.source)
    .map((item) => item.source.value)
    .filter((value) => value.startsWith('./') && value.endsWith('.js'))
  await Promise.all(imports.map((value) => visit(path.basename(value))))
}
await visit(dashboard)
for (const file of deferredAssets) assert.ok(!visited.has(file), `${file} stays outside the initial import graph`)
const gzipBytes = gzipSync(await readFile(path.join(assets, dashboard))).byteLength
assert.ok(gzipBytes <= 39 * 1024, `Dashboard entry stays below 39 KiB after extraction (${gzipBytes} bytes)`)
console.log(`Dashboard deferred panels passed: retry/cancel/props, separate lazy chunks; entry ${(gzipBytes / 1024).toFixed(2)} KiB gzip.`)
