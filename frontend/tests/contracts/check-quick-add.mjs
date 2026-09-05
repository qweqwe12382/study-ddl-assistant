import assert from 'node:assert/strict'

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

// Chip due time is 23:59:59 local; a +08:00 machine exports 15:59:59Z.
const withDue = buildQuickAddPayload({ name: '实验报告', courseId: 3, dueChip: 'tomorrow', today: '2026-09-05' })
assert.equal(withDue.payload.course_id, 3)
assert.ok(withDue.payload.due_at.endsWith('T15:59:59.000Z'), withDue.payload.due_at)
assert.ok(withDue.payload.due_at.startsWith('2026-09-06'), withDue.payload.due_at)

// Custom date requires an actual date value
const custom = buildQuickAddPayload({ name: '读书笔记', dueChip: 'custom', customDate: '2026-09-10' })
assert.ok(custom.payload.due_at.startsWith('2026-09-10T15:59:59.000Z'), custom.payload.due_at)
assert.equal(buildQuickAddPayload({ name: '读书笔记', dueChip: 'custom', customDate: '' }).error, '请选择截止日期，或改用快捷选项')

// Validation paths
assert.equal(buildQuickAddPayload({ name: '   ' }).error, '请填写任务名称')
assert.equal(buildQuickAddPayload({ name: 'x'.repeat(201) }).error, '任务名称不能超过 200 字')
assert.equal(buildQuickAddPayload({ name: 'ok', courseId: '3' }).payload.course_id, null)

console.log('quick task add contract check passed')
