const countKeys = Object.freeze([
  'courses_count',
  'materials_count',
  'active_task_count',
  'completed_task_count',
])

export function strictNonNegativeInteger(value) {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null
}

export function firstLearningProgress(progress) {
  if (!progress || typeof progress !== 'object' || Array.isArray(progress)) return null

  const counts = Object.fromEntries(countKeys.map((key) => [key, strictNonNegativeInteger(progress[key])]))
  if (Object.values(counts).some((count) => count === null)) return null

  const taskCount = counts.active_task_count + counts.completed_task_count
  return { started: taskCount > 0, completed: counts.completed_task_count > 0 }
}

export function isFirstLearningLoopIncomplete(progress) {
  const status = firstLearningProgress(progress)
  return status !== null && !status.completed
}

export function shouldPrioritizeFirstLearningLoop({
  dashboardState,
  agentState,
  decisionQueueStatus,
  hasFocus,
  attentionCount,
  progress,
} = {}) {
  if (dashboardState !== 'ready' || agentState !== 'ready') return false
  if (!['available', 'empty'].includes(decisionQueueStatus)) return false
  // Any unknown focus/attention state keeps the real agent surface first.
  if (hasFocus !== false || strictNonNegativeInteger(attentionCount) !== 0) return false
  return isFirstLearningLoopIncomplete(progress)
}
