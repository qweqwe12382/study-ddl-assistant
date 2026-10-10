/** Pure helpers for the one-line quick task add bar. */

import { localReferenceDateTime, validLocalReferenceDateTime } from './pasteNotice.js'

const MAX_NAME_LENGTH = 200

export const QUICK_DUE_CHIPS = [
  { key: 'today', label: '今天' },
  { key: 'tomorrow', label: '明天' },
  { key: 'day_after', label: '后天' },
  { key: 'next_monday', label: '下周一' },
]

function dateOnly(value) {
  const dateText = value instanceof Date ? localReferenceDateTime(value).slice(0, 10) : value
  if (typeof dateText !== 'string' || !validLocalReferenceDateTime(`${dateText}T00:00:00`)) return null
  return new Date(`${dateText}T00:00:00Z`)
}

/** Shanghai 'YYYY-MM-DD' for a quick due chip, or null for an unknown chip key. */
export function quickDueDate(chipKey, today = new Date()) {
  const base = dateOnly(today)
  if (!base) return null
  let offset = null
  if (chipKey === 'today') offset = 0
  else if (chipKey === 'tomorrow') offset = 1
  else if (chipKey === 'day_after') offset = 2
  else if (chipKey === 'next_monday') {
    const weekday = base.getUTCDay() === 0 ? 7 : base.getUTCDay()
    offset = ((8 - weekday) % 7) || 7
  } else return null
  // Calendar arithmetic is independent of the browser timezone and DST.
  const due = new Date(base)
  due.setUTCDate(due.getUTCDate() + offset)
  const month = String(due.getUTCMonth() + 1).padStart(2, '0')
  const day = String(due.getUTCDate()).padStart(2, '0')
  return `${due.getUTCFullYear()}-${month}-${day}`
}

/**
 * Build the POST /api/tasks payload from quick-add input. Returns
 * { payload } on success or { error } with a user-facing message.
 * The due time is always 23:59:59 Shanghai time on the chosen day.
 */
export function buildQuickAddPayload({ name, courseId, dueChip, customDate, today = new Date() }) {
  const trimmed = typeof name === 'string' ? name.trim() : ''
  if (!trimmed) return { error: '请填写任务名称' }
  if (trimmed.length > MAX_NAME_LENGTH) return { error: '任务名称不能超过 200 字' }

  let dueDate = null
  if (dueChip === 'custom') {
    dueDate = (typeof customDate === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(customDate) && dateOnly(customDate)) ? customDate : null
    if (!dueDate) return { error: '请选择截止日期，或改用快捷选项' }
  } else if (dueChip) {
    dueDate = quickDueDate(dueChip, today)
    if (!dueDate) return { error: '截止选项无效，请重新选择' }
  }

  const dueAt = dueDate
    ? new Date(`${dueDate}T23:59:59+08:00`).toISOString()
    : null
  const course = Number.isInteger(courseId) && courseId > 0 ? courseId : null
  return {
    payload: {
      name: trimmed,
      course_id: course,
      due_at: dueAt,
      priority: 3,
      status: 'not_started',
    },
  }
}
