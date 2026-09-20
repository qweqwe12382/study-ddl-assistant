import assert from 'node:assert/strict'
import { createFolioEntrance, vFolioEnter } from '../../src/directives/folioEnter.js'

function eventTarget(extra = {}) {
  const listeners = new Map()
  return {
    ...extra,
    addEventListener(type, listener) {
      if (!listeners.has(type)) listeners.set(type, new Set())
      listeners.get(type).add(listener)
    },
    removeEventListener(type, listener) { listeners.get(type)?.delete(listener) },
    emit(type) { for (const listener of [...(listeners.get(type) || [])]) listener() },
    listenerCount() { return [...listeners.values()].reduce((sum, entries) => sum + entries.size, 0) },
  }
}

function fixture({ reduced = false, hidden = false, observer = true, supported = true } = {}) {
  const preference = eventTarget({ matches: reduced })
  const page = eventTarget({ hidden })
  let finish
  let fail
  let cancellations = 0
  let disconnected = 0
  let intersection
  const calls = []
  const animation = { finished: new Promise((resolve, reject) => { finish = resolve; fail = reject }), cancel() { cancellations++ } }
  const element = eventTarget({ isConnected: true, animate: supported ? (...args) => { calls.push(args); return animation } : undefined })
  const platform = {
    document: page,
    matchMedia: () => preference,
    IntersectionObserver: observer ? class {
      constructor(callback) { intersection = callback }
      observe(target) { assert.equal(target, element) }
      disconnect() { disconnected++ }
    } : undefined,
  }
  return { preference, page, element, platform, calls, finish, fail,
    intersect: visible => intersection?.([{ isIntersecting: visible }]),
    cancellations: () => cancellations,
    disconnected: () => disconnected,
    listeners: () => preference.listenerCount() + page.listenerCount() + element.listenerCount(),
  }
}

for (const options of [{ reduced: true }, { supported: false }]) {
  const f = fixture(options)
  createFolioEntrance(f.element, f.platform)()
  assert.equal(f.calls.length, 0, 'reduced motion and unsupported browsers keep the static content')
  assert.equal(f.listeners(), 0)
}

{
  const f = fixture()
  createFolioEntrance(f.element, f.platform)
  f.intersect(false)
  assert.equal(f.calls.length, 0, 'mobile content must wait until it enters the viewport')
  f.intersect(true)
  f.intersect(true)
  assert.equal(f.calls.length, 1, 'a handout opens only once')
  assert.equal(f.calls[0][1].duration, 640)
  assert.equal(f.calls[0][1].fill, undefined, 'animation must not leave persistent hidden or transformed content')
  f.finish()
  await Promise.resolve()
  assert.equal(f.listeners(), 0)
  assert.ok(f.disconnected() > 0)
}

for (const interruption of ['preference', 'background', 'pointer', 'keyboard', 'unmount']) {
  const f = fixture()
  const stop = createFolioEntrance(f.element, f.platform)
  f.intersect(true)
  if (interruption === 'preference') { f.preference.matches = true; f.preference.emit('change') }
  if (interruption === 'background') { f.page.hidden = true; f.page.emit('visibilitychange') }
  if (interruption === 'pointer') f.element.emit('pointerdown')
  if (interruption === 'keyboard') f.element.emit('focusin')
  if (interruption === 'unmount') stop()
  stop()
  f.intersect(true)
  assert.equal(f.cancellations(), 1, `${interruption} cancels without replaying or double cleanup`)
  assert.equal(f.listeners(), 0)
  assert.equal(f.calls.length, 1)
}

{
  const f = fixture()
  const stop = createFolioEntrance(f.element, f.platform)
  stop()
  f.intersect(true)
  assert.equal(f.calls.length, 0, 'leaving before the preview becomes visible must not animate detached content')
  assert.equal(f.listeners(), 0)
}

for (const options of [{ observer: false }, { hidden: true }]) {
  const f = fixture(options)
  const stop = createFolioEntrance(f.element, f.platform)
  f.intersect(true)
  assert.equal(f.calls.length, options.hidden ? 0 : 1)
  stop()
  assert.equal(f.listeners(), 0)
}

{
  const f = fixture()
  createFolioEntrance(f.element, f.platform)
  f.intersect(true)
  f.fail(new Error('interrupted animation'))
  await Promise.resolve()
  assert.equal(f.listeners(), 0, 'rejected animations clean up without an unhandled rejection')
}

{
  const f = fixture()
  f.element.animate = () => { throw new Error('unsupported keyframe') }
  createFolioEntrance(f.element, f.platform)
  f.intersect(true)
  assert.equal(f.listeners(), 0, 'an animation failure must leave the page usable')
}

{
  const f = fixture()
  const previousWindow = globalThis.window
  try {
    globalThis.window = f.platform
    vFolioEnter.mounted(f.element)
    f.intersect(true)
    vFolioEnter.beforeUnmount(f.element)
    assert.equal(f.cancellations(), 1)
    assert.equal(f.listeners(), 0)
  } finally {
    if (previousWindow === undefined) delete globalThis.window
    else globalThis.window = previousWindow
  }
}

console.log('Motion lifecycle, reduced-motion, interruption and visibility checks passed.')
