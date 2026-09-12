import assert from 'node:assert/strict'

import { filterTaskCollection, hasTaskFilters } from '../../src/utils/taskFilters.js'

const now = new Date('2026-09-10T08:00:00+08:00').getTime()
const courses = new Map([
  ['1', '高等数学'],
  ['2', '大学英语'],
])
const tasks = [
  {
    id: 1,
    name: '完成极限练习',
    description: '整理错题并写出推导过程',
    task_type: '作业',
    course_id: 1,
    status: 'in_progress',
    due_at: '2026-09-11T09:00:00+08:00',
    source_context: { label: '第三章讲义.pdf' },
  },
  {
    id: 2,
    name: '准备口语展示',
    description: '练习开场白',
    task_type: '展示',
    course_id: 2,
    status: 'not_started',
    due_at: '2026-09-09T09:00:00+08:00',
  },
  {
    id: 3,
    name: '提交周记',
    course_id: 2,
    status: 'completed',
    due_at: '2026-09-08T09:00:00+08:00',
  },
  {
    id: 4,
    name: '已撤销的课堂展示',
    course_id: 2,
    status: 'canceled',
    due_at: '2026-09-08T09:00:00+08:00',
  },
]

const context = {
  now,
  courseName: (task) => courses.get(String(task.course_id)) || '',
  sourceLabel: (task) => task.source_context?.label || '',
}

assert.deepEqual(filterTaskCollection(tasks, { keyword: '高等数学' }, context).map((task) => task.id), [1])
assert.deepEqual(filterTaskCollection(tasks, { keyword: '推导过程' }, context).map((task) => task.id), [1])
assert.deepEqual(filterTaskCollection(tasks, { keyword: '第三章讲义' }, context).map((task) => task.id), [1])
assert.deepEqual(filterTaskCollection(tasks, { keyword: ' 口语 ' }, context).map((task) => task.id), [2])
assert.deepEqual(filterTaskCollection(tasks, { courseId: '2' }, context).map((task) => task.id), [2, 3, 4])
assert.deepEqual(filterTaskCollection(tasks, { status: 'overdue' }, context).map((task) => task.id), [2])
assert.deepEqual(filterTaskCollection(tasks, { courseId: 2, status: 'completed' }, context).map((task) => task.id), [3])
assert.deepEqual(filterTaskCollection(tasks, { status: 'canceled' }, context).map((task) => task.id), [4])
assert.deepEqual(filterTaskCollection(tasks, { status: 'overdue' }, { ...context, now: Date.parse('2026-09-20T08:00:00+08:00') }).map((task) => task.id), [1, 2])
assert.deepEqual(filterTaskCollection(tasks, { keyword: '不存在' }, context), [])
assert.deepEqual(filterTaskCollection(null, { keyword: '任务' }, context), [])

assert.equal(hasTaskFilters({ keyword: '  ', courseId: '', status: '' }), false)
assert.equal(hasTaskFilters({ keyword: '作业' }), true)
assert.equal(hasTaskFilters({ courseId: 1 }), true)
assert.equal(hasTaskFilters({ status: 'unsupported' }), false)

console.log('Task filter contract check passed.')
