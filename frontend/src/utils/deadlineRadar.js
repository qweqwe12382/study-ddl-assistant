const TERMINAL_TASK_STATUSES = new Set(['completed', 'canceled'])
const NAVIGATION_KEY = /^[0-9a-f]{32}$/

export function actionableDeadlineTasks(tasks) {
  if (!Array.isArray(tasks)) return []
  return tasks.filter((task) => (
    task
    && !TERMINAL_TASK_STATUSES.has(task.status)
    && Number.isInteger(Number(task.id))
    && Number(task.id) > 0
    && NAVIGATION_KEY.test(String(task.navigation_key || ''))
    && Number.isInteger(Number(task.revision))
    && Number(task.revision) >= 1
  ))
}

export function deadlineRadarPayload(task, noticeText, referenceTime) {
  if (!task || !NAVIGATION_KEY.test(String(task.navigation_key || ''))) return null
  const taskId = Number(task.id)
  const revision = Number(task.revision)
  const notice = typeof noticeText === 'string' ? noticeText.trim() : ''
  const instant = referenceTime instanceof Date ? referenceTime.toISOString() : String(referenceTime || '')
  if (!Number.isInteger(taskId) || taskId < 1 || !Number.isInteger(revision) || revision < 1 || notice.length < 4 || !instant) return null
  return {
    task_id: taskId,
    task_navigation_key: task.navigation_key,
    task_revision: revision,
    notice_text: notice,
    reference_time: instant,
  }
}

export function pressureBarWidth(day, field) {
  const value = Number(day?.[field])
  const scale = Math.max(
    Number(day?.effective_capacity_minutes) || 0,
    Number(day?.before_minutes) || 0,
    Number(day?.after_minutes) || 0,
    1,
  )
  if (!Number.isFinite(value) || value <= 0) return 0
  return Math.min(100, Math.max(0, Math.round((value / scale) * 100)))
}

export function buildDeadlineRadarKey(taskId, token) {
  const safeTaskId = Number.isInteger(Number(taskId)) && Number(taskId) > 0 ? Number(taskId) : 'task'
  const safeToken = String(token || '')
    .replace(/[^A-Za-z0-9._-]/g, '')
    .slice(0, 48)
  return `ddl-${safeTaskId}-${safeToken || 'confirm'}`.slice(0, 64)
}
