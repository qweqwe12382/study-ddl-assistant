import { editRequestConfig } from './editPrecondition.js'

/** Keep one exact, identity-bound request until its result is confirmed. */
export function buildFocusSaveAttempt(task, minutes, asComplete, key) {
  const config = editRequestConfig(task)
  if (!config) throw new Error('任务版本无法确认，请刷新后重试。')
  if (['completed', 'canceled'].includes(task.status)) throw new Error('请先恢复任务，再记录专注。')
  if (!Number.isInteger(minutes) || minutes < 15 || minutes > 10080) throw new Error('本次专注需满 15 分钟。')
  const actual = (task.actual_minutes || 0) + minutes
  if (actual > 10080) throw new Error('累计实际用时不能超过 10080 分钟，请先核对任务记录。')
  return {
    taskId: task.id,
    taskName: task.name,
    minutes,
    asComplete,
    config,
    payload: asComplete ? { actual_minutes: actual, idempotency_key: key } : { minutes, idempotency_key: key },
  }
}

export function sendFocusSaveAttempt(attempt, { recordFocus, completeFocus }) {
  const save = attempt.asComplete ? completeFocus : recordFocus
  return save(attempt.taskId, attempt.payload, attempt.config)
}
