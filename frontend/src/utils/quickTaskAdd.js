/** Pure helpers for the one-line quick task add bar. */

const MAX_NAME_LENGTH = 200
const DAY_MS = 24 * 60 * 60 * 1000

export const QUICK_DUE_CHIPS = [
  { key: 'today', label: '今天' },
  { key: 'tomorrow', label: '明天' },
  { key: 'day_after', label: '后天' },
  { key: 'next_monday', label: '下周一' },
]

function dateOnly(value) {
  if (value instanceof Date) return new Date(value.getFullYear(), value.getMonth(), value.getDate())
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day)
  }
  return null
}

/** Local 'YYYY-MM-DD' for a quick due chip, or null for an unknown chip key. */
export function quickDueDate(chipKey, today = new Date()) {
  const base = dateOnly(today)
  if (!base) return null
  let offset = null
  if (chipKey === 'today') offset = 0
  else if (chipKey === 'tomorrow') offset = 1
  else if (chipKey === 'day_after') offset = 2
  else if (chipKey === 'next_monday') {
    const weekday = base.getDay() === 0 ? 7 : base.getDay()
    offset = ((8 - weekday) % 7) || 7
  } else return null
  const due = new Date(base.getTime() + offset * DAY_MS)
  const month = String(due.getMonth() + 1).padStart(2, '0')
  const day = String(due.getDate()).padStart(2, '0')
  return `${due.getFullYear()}-${month}-${day}`
}

/**
 * Build the POST /api/tasks payload from quick-add input. Returns
 * { payload } on success or { error } with a user-facing message.
 * The due time is always 23:59:59 local time on the chosen day.
 */
export function buildQuickAddPayload({ name, courseId, dueChip, customDate, today = new Date() }) {
  const trimmed = typeof name === 'string' ? name.trim() : ''
  if (!trimmed) return { error: '请填写任务名称' }
  if (trimmed.length > MAX_NAME_LENGTH) return { error: '任务名称不能超过 200 字' }

  let dueDate = null
  if (dueChip === 'custom') {
    dueDate = /^\d{4}-\d{2}-\d{2}$/.test(typeof customDate === 'string' ? customDate : '') ? customDate : null
    if (!dueDate) return { error: '请选择截止日期，或改用快捷选项' }
  } else if (dueChip) {
    dueDate = quickDueDate(dueChip, today)
    if (!dueDate) return { error: '截止选项无效，请重新选择' }
  }

  const dueAt = dueDate
    ? new Date(new Date(`${dueDate}T23:59:59`).getTime()).toISOString()
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
