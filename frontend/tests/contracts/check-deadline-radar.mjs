import assert from 'node:assert/strict'

import {
  actionableDeadlineTasks,
  buildDeadlineRadarKey,
  deadlineRadarPayload,
  pressureBarWidth,
} from '../../src/utils/deadlineRadar.js'

const active = {
  id: 7,
  navigation_key: 'a'.repeat(32),
  revision: 3,
  name: '实验报告',
  status: 'not_started',
}

assert.deepEqual(actionableDeadlineTasks([
  active,
  { ...active, id: 8, status: 'completed' },
  { ...active, id: 9, status: 'canceled' },
  { ...active, id: 10, navigation_key: null },
]), [active])

assert.deepEqual(
  deadlineRadarPayload(active, '  截止时间延期至 2026 年 9 月 18 日。  ', '2026-09-11T01:00:00.000Z'),
  {
    task_id: 7,
    task_navigation_key: 'a'.repeat(32),
    task_revision: 3,
    notice_text: '截止时间延期至 2026 年 9 月 18 日。',
    reference_time: '2026-09-11T01:00:00.000Z',
  },
)
assert.equal(deadlineRadarPayload(active, '短', '2026-09-11T01:00:00.000Z'), null)
assert.equal(pressureBarWidth({ effective_capacity_minutes: 120, before_minutes: 60, after_minutes: 180 }, 'before_minutes'), 33)
assert.equal(pressureBarWidth({ effective_capacity_minutes: 120, before_minutes: 60, after_minutes: 180 }, 'effective_capacity_minutes'), 67)
assert.equal(pressureBarWidth({ effective_capacity_minutes: 120, before_minutes: 60, after_minutes: 180 }, 'after_minutes'), 100)
assert.equal(buildDeadlineRadarKey(7, 'token:/unsafe'), 'ddl-7-tokenunsafe')
assert.ok(buildDeadlineRadarKey(7, 'x'.repeat(100)).length <= 64)

console.log('Deadline radar contract check passed.')
