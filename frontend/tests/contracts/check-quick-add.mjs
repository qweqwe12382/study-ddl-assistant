import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { QUICK_DUE_CHIPS, buildQuickAddPayload, quickDueDate } from '../../src/utils/quickTaskAdd.js'

assert.deepEqual(QUICK_DUE_CHIPS.map((chip) => chip.key), ['today', 'tomorrow', 'day_after', 'next_monday'])

// 2026-09-05 is a Saturday: next Monday is +2 days.
assert.equal(quickDueDate('today', '2026-09-05'), '2026-09-05')
assert.equal(quickDueDate('tomorrow', '2026-09-05'), '2026-09-06')
assert.equal(quickDueDate('day_after', '2026-09-05'), '2026-09-07')
assert.equal(quickDueDate('next_monday', '2026-09-05'), '2026-09-07')
// Monday rolls a full week forward; Sunday is already the day before.
assert.equal(quickDueDate('next_monday', '2026-08-31'), '2026-09-07')
assert.equal(quickDueDate('next_monday', '2026-09-06'), '2026-09-07')
assert.equal(quickDueDate('unknown', '2026-09-05'), null)
assert.equal(quickDueDate('today', 'not-a-date'), null)

// Calendar dates must remain stable through both US and European DST
// transitions. Adding a fixed 24 hours fails on the 25-hour autumn day.
for (const [today, tomorrow] of [
  ['2026-03-08', '2026-03-09'],
  ['2026-03-29', '2026-03-30'],
  ['2026-10-25', '2026-10-26'],
  ['2026-11-01', '2026-11-02'],
]) {
  assert.equal(quickDueDate('today', today), today)
  assert.equal(quickDueDate('tomorrow', today), tomorrow)
  assert.equal(quickDueDate('next_monday', today), tomorrow)
}
assert.equal(quickDueDate('day_after', '2026-10-24'), '2026-10-26')
assert.equal(quickDueDate('day_after', '2026-10-31'), '2026-11-02')
assert.equal(quickDueDate('tomorrow', new Date(2026, 8, 5, 23, 45)), '2026-09-06')

function assertLocalEndOfDay(iso, year, month, day) {
  const due = new Date(iso)
  assert.equal(due.toISOString(), iso, 'payload uses an ISO instant')
  assert.deepEqual([
    due.getFullYear(), due.getMonth() + 1, due.getDate(),
    due.getHours(), due.getMinutes(), due.getSeconds(), due.getMilliseconds(),
  ], [year, month, day, 23, 59, 59, 0], 'deadline is 23:59:59 on the selected local date')
}

// Minimal payload: name only
const minimal = buildQuickAddPayload({ name: ' 高数作业 ' })
assert.equal(minimal.error, undefined)
assert.deepEqual(minimal.payload, {
  name: '高数作业',
  course_id: null,
  due_at: null,
  priority: 3,
  status: 'not_started',
})

// Assert the user's local deadline, not a fixed +08:00 UTC representation.
const withDue = buildQuickAddPayload({ name: '实验报告', courseId: 3, dueChip: 'tomorrow', today: '2026-09-05' })
assert.equal(withDue.payload.course_id, 3)
assertLocalEndOfDay(withDue.payload.due_at, 2026, 9, 6)

const autumnDue = buildQuickAddPayload({ name: '复习', dueChip: 'tomorrow', today: '2026-11-01' })
assertLocalEndOfDay(autumnDue.payload.due_at, 2026, 11, 2)

// Custom date requires an actual date value
const custom = buildQuickAddPayload({ name: '读书笔记', dueChip: 'custom', customDate: '2026-09-10' })
assertLocalEndOfDay(custom.payload.due_at, 2026, 9, 10)
assert.equal(buildQuickAddPayload({ name: '读书笔记', dueChip: 'custom', customDate: '' }).error, '请选择截止日期，或改用快捷选项')

// Validation paths
assert.equal(buildQuickAddPayload({ name: '   ' }).error, '请填写任务名称')
assert.equal(buildQuickAddPayload({ name: 'x'.repeat(201) }).error, '任务名称不能超过 200 字')
assert.equal(buildQuickAddPayload({ name: 'ok', courseId: '3' }).payload.course_id, null)

if (!process.argv.includes('--timezone-child')) {
  for (const timezone of ['UTC', 'Asia/Shanghai', 'America/Los_Angeles', 'Europe/Berlin']) {
    const result = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--timezone-child'], {
      env: { ...process.env, TZ: timezone },
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, `${timezone}: ${result.error?.message || result.stderr || result.stdout}`)
  }
  console.log('quick task add contract check passed (local timezone and UTC/Shanghai/Los Angeles/Berlin)')
}
