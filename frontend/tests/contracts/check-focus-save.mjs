import assert from 'node:assert/strict'

import { buildFocusSaveAttempt, sendFocusSaveAttempt } from '../../src/utils/focusSave.js'

const task = { id: 7, name: '报告', navigation_key: 'a'.repeat(32), revision: 3, status: 'in_progress', actual_minutes: 25 }
const attempt = buildFocusSaveAttempt(task, 30, false, 'focus-session-one')
assert.deepEqual(attempt.payload, { minutes: 30, idempotency_key: 'focus-session-one' })
assert.equal(attempt.config.headers['If-Match'], `"${task.navigation_key}:3"`)
let requests = []
const services = {
  recordFocus: async (...args) => {
    requests.push(structuredClone(args))
    if (requests.length === 1) throw new Error('response lost after save')
    return { ...task, actual_minutes: 55 }
  },
  completeFocus: () => { throw new Error('Recording focus must not complete a task') },
}
await assert.rejects(sendFocusSaveAttempt(attempt, services), /response lost/)
// A refreshed task may expose the previous request's committed total. Retry
// the saved request rather than calculating a second cumulative addition.
task.actual_minutes = 55
task.revision = 4
const saved = await sendFocusSaveAttempt(attempt, services)
assert.equal(saved.actual_minutes, 55)
assert.deepEqual(requests[0], requests[1])

const completion = buildFocusSaveAttempt(task, 25, true, 'complete-next-session')
assert.deepEqual(completion.payload, { actual_minutes: 80, idempotency_key: 'complete-next-session' })
requests = []
const completionServices = {
  recordFocus: () => { throw new Error('Completion must use its own confirmed action') },
  completeFocus: async (...args) => {
    requests.push(structuredClone(args))
    if (requests.length === 1) throw new Error('response lost')
    return { status: 'completed', actual_minutes: 80 }
  },
}
await assert.rejects(sendFocusSaveAttempt(completion, completionServices), /response lost/)
await sendFocusSaveAttempt(completion, completionServices)
assert.deepEqual(requests[0], requests[1])
assert.equal(requests[1][1].actual_minutes, 80)
assert.throws(() => buildFocusSaveAttempt({ ...task, status: 'canceled' }, 25, false, 'x'), /恢复/)
assert.throws(() => buildFocusSaveAttempt({ ...task, revision: null }, 25, false, 'x'), /版本/)
assert.throws(() => buildFocusSaveAttempt(task, 14, false, 'x'), /15/)
assert.throws(() => buildFocusSaveAttempt({ ...task, actual_minutes: 10070 }, 15, true, 'x'), /10080/)

console.log('focus save retry and cumulative total contract check passed')
