const FILTER_STATUSES = new Set(['not_started', 'in_progress', 'completed', 'overdue', 'canceled'])

export function filterTaskCollection(tasks, filters = {}, context = {}) {
  if (!Array.isArray(tasks)) return []

  const keyword = normalizeText(filters.keyword)
  const courseId = normalizeCourseId(filters.courseId)
  const status = FILTER_STATUSES.has(filters.status) ? filters.status : ''
  const now = validTimestamp(context.now) ?? Date.now()
  const courseName = typeof context.courseName === 'function' ? context.courseName : () => ''
  const sourceLabel = typeof context.sourceLabel === 'function' ? context.sourceLabel : () => ''

  return tasks.filter((task) => {
    if (!task || typeof task !== 'object') return false
    if (courseId && String(task.course_id ?? '') !== courseId) return false
    if (status && !matchesStatus(task, status, now)) return false
    if (!keyword) return true

    return [
      task.name,
      task.description,
      task.task_type,
      courseName(task),
      sourceLabel(task),
    ].some((value) => normalizeText(value).includes(keyword))
  })
}

export function hasTaskFilters(filters = {}) {
  return Boolean(
    normalizeText(filters.keyword)
    || normalizeCourseId(filters.courseId)
    || FILTER_STATUSES.has(filters.status),
  )
}

function matchesStatus(task, status, now) {
  if (status !== 'overdue') return task.status === status
  if (['completed', 'canceled'].includes(task.status) || !task.due_at) return false
  const dueAt = new Date(task.due_at).getTime()
  return Number.isFinite(dueAt) && dueAt < now
}

function normalizeText(value) {
  return typeof value === 'string' ? value.trim().toLocaleLowerCase('zh-CN') : ''
}

function normalizeCourseId(value) {
  if (value === null || value === undefined || value === '') return ''
  return String(value)
}

function validTimestamp(value) {
  if (value === undefined || value === null) return null
  const timestamp = value instanceof Date ? value.getTime() : Number(value)
  return Number.isFinite(timestamp) ? timestamp : null
}
