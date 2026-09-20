import assert from 'node:assert/strict'
import { chooseHomeFocus, focusTaskTarget, isRoutineSetup, nextCourseExamDate, orderedPendingTasks, resolveFocusTask } from '../../src/utils/dailyWorkflow.js'

const key = 'a'.repeat(32)
const tasks = [
  { id: 1, name: 'Later', navigation_key: key, status: 'not_started', priority: 5, due_at: '2026-10-02T12:00:00Z' },
  { id: 2, name: 'Today', navigation_key: 'b'.repeat(32), status: 'in_progress', priority: 2, due_at: '2026-09-20T12:00:00Z' },
  { id: 3, name: 'Undated', navigation_key: 'c'.repeat(32), status: 'not_started', priority: 4 },
  { id: 4, name: 'Finished', status: 'completed', due_at: '2026-09-01T00:00:00Z' },
  { id: 5, name: 'Canceled', status: 'canceled', due_at: '2026-09-01T00:00:00Z' },
]
assert.deepEqual(orderedPendingTasks(tasks).map(task => task.id), [2, 1, 3])
assert.equal(tasks[0].id, 1, 'Sorting never changes the source array')
assert.deepEqual(orderedPendingTasks(null), [])
assert.equal(orderedPendingTasks([{ ...tasks[0], due_at: 'invalid' }, tasks[1]])[0].id, 2)
assert.equal(orderedPendingTasks([{ ...tasks[0], due_at: null }, { ...tasks[2], priority: 5 }])[0].id, 1)

const target = focusTaskTarget(tasks[1])
assert.deepEqual(target, { path: '/focus', query: { task_id: '2', navigation_key: 'b'.repeat(32), start: '1' } })
assert.equal(focusTaskTarget({ id: 2 }), null)
assert.equal(resolveFocusTask(tasks, target.query).task, tasks[1])
assert.equal(resolveFocusTask(tasks, target.query).start, true)
assert.equal(resolveFocusTask(tasks, { ...target.query, start: undefined }).start, false, 'Consumed link does not restart a timer')
for (const query of [
  { ...target.query, navigation_key: key }, // reused numeric ID
  { ...target.query, task_id: '999' }, // deleted task
  { ...target.query, task_id: ['2'] }, // malformed route
  { task_id: '2', start: '1' }, // missing identity
  { task_id: '4', navigation_key: key, start: '1' }, // finished task
]) {
  const resolved = resolveFocusTask(tasks, query)
  assert.equal(resolved.requested, true)
  assert.equal(resolved.task, null)
  assert.equal(resolved.start, false)
}
assert.deepEqual(resolveFocusTask(tasks, {}), { requested: false, task: null, start: false })

const estimate = { priority: 'high', reason_code: 'capacity_missing_estimate' }
const urgent = { priority: 'critical', reason_code: 'deadline_changed' }
assert.equal(isRoutineSetup(estimate), true)
assert.equal(isRoutineSetup(urgent), false)
assert.equal(chooseHomeFocus({ decisions: [estimate, urgent], tasks }).item, tasks[1], 'Doing a task stays available while review notices remain in the attention area')
assert.equal(chooseHomeFocus({ decisions: [estimate, urgent], tasks: [] }).item, urgent)
assert.equal(chooseHomeFocus({ decisions: [estimate], actions: [{ action_type: 'set_task_estimate' }] }), null)
assert.equal(chooseHomeFocus({ decisions: [estimate], tasks, concise: false }).item, estimate, 'Full records retain estimation suggestions')

const now = new Date('2026-09-20T02:00:00Z')
const exams = [
  { course_id: 1, starts_at: '2026-09-10T09:00:00+08:00' },
  { course_id: 2, starts_at: '2026-09-21T09:00:00+08:00' },
  { course_id: 1, starts_at: '2026-10-05T09:00:00+08:00' },
  { course_id: 1, starts_at: '2026-10-01T18:00:00Z' }, // October 2 in China
  { course_id: 1, starts_at: 'invalid' },
]
assert.equal(nextCourseExamDate(exams, 1, now), '2026-10-02')
assert.equal(nextCourseExamDate(exams, 2, now), '2026-09-21')
assert.equal(nextCourseExamDate(exams, 3, now), '')
assert.equal(nextCourseExamDate(exams, null, now), '')
assert.equal(nextCourseExamDate(null, 1, now), '')
console.log('Daily task, focus identity, and exam defaults checks passed.')
