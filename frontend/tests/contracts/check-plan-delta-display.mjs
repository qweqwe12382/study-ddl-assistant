import assert from 'node:assert/strict'

import { normalizePlanDeltaLines } from '../../src/utils/planDeltaDisplay.js'

const navigationKey = 'a'.repeat(32)
const finalNote = '智能体差异：实际用时反馈75分钟，请在确认后纳入本时段。'
const changes = Array.from({ length: 7 }, (_, index) => ({
  item_id: `day-${index + 1}`,
  before: {
    id: `day-${index + 1}`,
    title: `复习单元 ${index + 1}`,
    date: `2026-09-${String(index + 1).padStart(2, '0')}`,
    content: `原计划内容 ${index + 1}`,
    minutes: 30 + index,
    status: 'not_started',
    source_task_ids: [100 + index],
    source_material_ids: [200 + index],
    source_task_refs: [{ source_id: 100 + index, navigation_key: navigationKey }],
  },
  after: {
    id: `day-${index + 1}`,
    title: `复习单元 ${index + 1}`,
    date: `2026-09-${String(index + 1).padStart(2, '0')}`,
    content: `${'长内容 '.repeat(20)}${index === 6 ? finalNote : `调整 ${index + 1}`}`,
    minutes: 75,
    status: 'not_started',
    source_task_ids: [100 + index],
    source_material_ids: [200 + index],
    source_task_refs: [{ source_id: 100 + index, navigation_key: navigationKey }],
  },
}))

const lines = normalizePlanDeltaLines({ changes })
assert.ok(lines.before.includes('计划项 ID：day-7'), 'does not hide the seventh change')
assert.ok(lines.after.includes(`内容：${'长内容 '.repeat(20)}${finalNote}`), 'keeps the end of long changed content')
assert.ok(lines.after.includes('时长：75 分钟'))
assert.ok(lines.after.includes('状态：not_started'))
assert.ok(lines.after.includes('日期：2026-09-07'))
assert.ok(lines.after.includes('关联任务 ID：106'))
assert.ok(lines.after.includes('关联资料 ID：206'))
assert.equal(lines.after.some((line) => line.includes(navigationKey)), false, 'never exposes navigation keys')
assert.equal(lines.after.some((line) => line.includes('source_task_refs')), false, 'never exposes raw source references')

console.log('plan-delta display checks passed')
