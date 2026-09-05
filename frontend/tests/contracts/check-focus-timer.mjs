import assert from 'node:assert/strict'

import {
  FOCUS_PRESET_MINUTES,
  formatClock,
  isRecordable,
  mergeActualMinutes,
  recordLabel,
  sessionMinutes,
} from '../../src/utils/focusTimer.js'

assert.deepEqual(FOCUS_PRESET_MINUTES, [15, 25, 45])

assert.equal(formatClock(0), '00:00')
assert.equal(formatClock(65), '01:05')
assert.equal(formatClock(25 * 60), '25:00')
assert.equal(formatClock(3599), '59:59')
assert.equal(formatClock(3600), '60:00')
assert.equal(formatClock(-5), '00:00')
assert.equal(formatClock(Number.NaN), '00:00')

assert.equal(sessionMinutes(0), 0)
assert.equal(sessionMinutes(14 * 60 + 59), 14)
assert.equal(sessionMinutes(15 * 60), 15)
assert.equal(sessionMinutes(Number.NaN), 0)

assert.equal(isRecordable(14 * 60 + 59), false)
assert.equal(isRecordable(15 * 60), true)
assert.equal(isRecordable(0), false)

assert.equal(mergeActualMinutes(undefined, 25), 25)
assert.equal(mergeActualMinutes(0, 25), 25)
assert.equal(mergeActualMinutes(20, 25), 45)
assert.equal(mergeActualMinutes(10071, 25), 10080)
assert.equal(mergeActualMinutes(Number.NaN, 25), 25)

assert.equal(recordLabel(25), '25 分钟')
assert.equal(recordLabel(Number.NaN), '0 分钟')

console.log('focus timer contract check passed')
