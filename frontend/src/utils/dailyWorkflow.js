import { navigationKey, positiveMaterialId } from './materialSourceNavigation.js'

export function orderedPendingTasks(tasks) {
  const due = task => task.due_at && Number.isFinite(Date.parse(task.due_at)) ? Date.parse(task.due_at) : Infinity
  return (Array.isArray(tasks) ? tasks : [])
    .filter(task => task && !['completed', 'canceled'].includes(task.status))
    .sort((a, b) => (due(a) === due(b) ? 0 : due(a) < due(b) ? -1 : 1)
      || (b.priority || 0) - (a.priority || 0) || a.id - b.id)
}

export function focusTaskTarget(task) {
  const id = positiveMaterialId(task?.id)
  const key = navigationKey(task?.navigation_key)
  return id && key ? { path: '/focus', query: { task_id: String(id), navigation_key: key, start: '1' } } : null
}

// A stale link must never silently start another task, even if its numeric ID is reused.
export function resolveFocusTask(tasks, query) {
  const requested = Object.hasOwn(query, 'task_id') || Object.hasOwn(query, 'navigation_key')
  if (!requested) return { requested: false, task: null, start: false }
  const id = positiveMaterialId(query.task_id)
  const key = navigationKey(query.navigation_key)
  const task = id && key ? orderedPendingTasks(tasks).find(task => task.id === id && task.navigation_key === key) : null
  return { requested: true, task: task || null, start: Boolean(task && query.start === '1') }
}

export function isRoutineSetup(item) {
  return ['capacity_missing_estimate', 'capacity_start_task'].includes(item?.reason_code)
    || item?.action_type === 'set_task_estimate'
}

export function chooseHomeFocus({ decisions = [], actions = [], tasks = [], concise = true }) {
  const relevantDecisions = concise ? decisions.filter(item => !isRoutineSetup(item)) : decisions
  const task = concise ? orderedPendingTasks(tasks)[0] : null
  if (task) return { kind: 'task', item: task }
  const urgent = relevantDecisions.find(item => ['critical', 'high'].includes(item.priority))
  if (urgent) return { kind: 'decision', item: urgent }
  const action = actions.find(item => !concise || !isRoutineSetup(item))
  if (action) return { kind: 'action', item: action }
  return relevantDecisions.length ? { kind: 'decision', item: relevantDecisions[0] } : null
}

export function nextCourseExamDate(exams, courseId, now = new Date()) {
  if (!courseId) return ''
  const time = now.getTime()
  const exam = (Array.isArray(exams) ? exams : [])
    .filter(item => item.course_id === courseId && Date.parse(item.starts_at) > time)
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at))[0]
  if (!exam) return ''
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(exam.starts_at))
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}
