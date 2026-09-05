const countKeys = Object.freeze([
  'courses_count',
  'materials_count',
  'active_task_count',
  'completed_task_count',
])

export function strictNonNegativeInteger(value) {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null
}

export function isFirstLearningLoopIncomplete(progress) {
  if (!progress || typeof progress !== 'object' || Array.isArray(progress)) return false

  const counts = Object.fromEntries(countKeys.map((key) => [key, strictNonNegativeInteger(progress[key])]))
  if (Object.values(counts).some((count) => count === null)) return false

  const taskCount = counts.active_task_count + counts.completed_task_count
  return counts.courses_count < 1
    || counts.materials_count < 1
    || taskCount < 1
    || counts.completed_task_count < 1
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
