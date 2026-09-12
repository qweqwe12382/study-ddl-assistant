import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import { baseParse, NodeTypes } from '@vue/compiler-dom'
import { parse as parseSfc } from '@vue/compiler-sfc'

import {
  firstLearningProgress,
  isFirstLearningLoopIncomplete,
  shouldPrioritizeFirstLearningLoop,
  strictNonNegativeInteger,
} from '../../src/utils/firstLearningLoopPlacement.js'
import { buildQuickAddPayload } from '../../src/utils/quickTaskAdd.js'

const freshProgress = {
  courses_count: 0,
  materials_count: 0,
  active_task_count: 0,
  completed_task_count: 0,
}

assert.equal(strictNonNegativeInteger(0), 0)
for (const invalid of [null, undefined, false, true, '', '0', 1.2, -1, Number.NaN, Number.POSITIVE_INFINITY]) {
  assert.equal(strictNonNegativeInteger(invalid), null, `does not coerce ${String(invalid)} into a count`)
}

// The shortest student path is one named task. Courses, materials, dates, and
// estimates stay optional throughout the first learning loop.
const nameOnlyTask = buildQuickAddPayload({ name: ' 复习第一章 ' })
assert.equal(nameOnlyTask.error, undefined)
assert.deepEqual(nameOnlyTask.payload, {
  name: '复习第一章',
  course_id: null,
  due_at: null,
  priority: 3,
  status: 'not_started',
})

const nameOnlyTaskCreated = {
  ...freshProgress,
  active_task_count: 1,
}
assert.deepEqual(firstLearningProgress(freshProgress), { started: false, completed: false })
assert.deepEqual(firstLearningProgress(nameOnlyTaskCreated), { started: true, completed: false })
assert.equal(isFirstLearningLoopIncomplete(nameOnlyTaskCreated), true)

const nameOnlyTaskCompleted = {
  ...freshProgress,
  completed_task_count: 1,
}
assert.deepEqual(firstLearningProgress(nameOnlyTaskCompleted), { started: true, completed: true })
assert.equal(isFirstLearningLoopIncomplete(nameOnlyTaskCompleted), false)

// Optional organization cannot start or finish the task-based loop by itself.
const organizedWithoutTasks = {
  courses_count: 3,
  materials_count: 8,
  active_task_count: 0,
  completed_task_count: 0,
}
assert.deepEqual(firstLearningProgress(organizedWithoutTasks), { started: false, completed: false })
assert.equal(isFirstLearningLoopIncomplete(organizedWithoutTasks), true)

assert.equal(isFirstLearningLoopIncomplete(freshProgress), true)
for (const unknownProgress of [
  null,
  {},
  { ...freshProgress, courses_count: false },
  { ...freshProgress, materials_count: '' },
  { ...freshProgress, active_task_count: null },
  { courses_count: 0, materials_count: 0, active_task_count: 0 },
]) {
  assert.equal(firstLearningProgress(unknownProgress), null, 'invalid dashboard counts stay unknown')
  assert.equal(isFirstLearningLoopIncomplete(unknownProgress), false, 'unknown progress is not treated as an empty account')
}
assert.equal(isFirstLearningLoopIncomplete({ courses_count: 1, materials_count: 1, active_task_count: 0, completed_task_count: 1 }), false)

const readyContext = {
  dashboardState: 'ready',
  agentState: 'ready',
  decisionQueueStatus: 'empty',
  hasFocus: false,
  attentionCount: 0,
  progress: freshProgress,
}
assert.equal(shouldPrioritizeFirstLearningLoop(readyContext), true)
for (const [label, override] of [
  ['a real focus item', { hasFocus: true }],
  ['one risk or attention item', { attentionCount: 1 }],
  ['several risk or attention items', { attentionCount: 3 }],
  ['focus plus risk items', { hasFocus: true, attentionCount: 2 }],
]) {
  assert.equal(
    shouldPrioritizeFirstLearningLoop({ ...readyContext, ...override }),
    false,
    `${label} stays ahead of onboarding`,
  )
}
assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, attentionCount: false }), false)
assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, attentionCount: null }), false)
assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, progress: { ...freshProgress, courses_count: '0' } }), false)
for (const state of ['loading', 'error', 'invalid']) {
  assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, dashboardState: state }), false)
  assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, agentState: state }), false)
}
for (const decisionQueueStatus of ['unavailable', 'invalid']) {
  assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, decisionQueueStatus }), false)
}

const firstLearningLoopSource = await readFile(new URL('../../src/components/FirstLearningLoop.vue', import.meta.url), 'utf8')
const firstLearningLoopSfc = parseSfc(firstLearningLoopSource, { filename: 'FirstLearningLoop.vue' })
assert.deepEqual(firstLearningLoopSfc.errors, [], 'First-learning-loop SFC parses without compiler errors')
assert.ok(firstLearningLoopSfc.descriptor.template?.content, 'First-learning-loop has a parseable template')
const firstLearningLoopAst = baseParse(firstLearningLoopSfc.descriptor.template.content)
const loopSteps = []
function collectElements(node) {
  if (node?.type === NodeTypes.ELEMENT) {
    if (node.tag === 'li') loopSteps.push(node)
    node.children.forEach(collectElements)
    return
  }
  if (Array.isArray(node?.children)) node.children.forEach(collectElements)
  if (Array.isArray(node?.branches)) node.branches.forEach(collectElements)
}
firstLearningLoopAst.children.forEach(collectElements)
assert.equal(loopSteps.length, 2, 'onboarding presents exactly the create-and-complete task steps')
assert.match(firstLearningLoopSfc.descriptor.template.content, /记下一项任务/)
assert.match(firstLearningLoopSfc.descriptor.template.content, /做完后标记完成/)
assert.match(firstLearningLoopSfc.descriptor.template.content, /课程、日期和预计用时，都可以稍后补充/)
assert.match(firstLearningLoopSfc.descriptor.template.content, /添加课程<\/button>，也可以以后再安排/)
assert.match(firstLearningLoopSfc.descriptor.template.content, /status\.started \? 'complete' : 'task'/)

const dashboardSource = await readFile(new URL('../../src/views/DashboardView.vue', import.meta.url), 'utf8')
const { descriptor, errors } = parseSfc(dashboardSource, { filename: 'DashboardView.vue' })
assert.deepEqual(errors, [], 'Dashboard SFC parses without compiler errors')
assert.ok(descriptor.template?.content, 'Dashboard has a parseable template')
const ast = baseParse(descriptor.template.content)
const dashboardRoot = ast.children.find((node) => node.type === NodeTypes.ELEMENT && node.tag === 'div')
assert.ok(dashboardRoot, 'Dashboard template has a root element')
const directChildren = dashboardRoot.children.filter((node) => node.type === NodeTypes.ELEMENT)
const todayFocusStage = directChildren.find((node) => node.tag === 'TodayFocusStage')
assert.ok(todayFocusStage, 'Dashboard keeps its real focus stage')
const focusVisibility = todayFocusStage.props.find((prop) => prop.type === NodeTypes.DIRECTIVE && prop.name === 'if')
assert.equal(
  focusVisibility?.exp?.content,
  '!firstLearningLoopPriority || isDetailedView',
  'the focus stage is hidden only when onboarding has earned priority in concise view',
)
const teleportIndex = directChildren.findIndex((node) => node.tag === 'Teleport')
assert.notEqual(teleportIndex, -1, 'Dashboard renders one Teleport for the first-learning loop')
const teleport = directChildren[teleportIndex]
assert.ok(teleport.props.some((prop) => prop.type === NodeTypes.ATTRIBUTE && prop.name === 'defer'), 'First-learning-loop Teleport defers its first target lookup')

for (const targetId of ['dashboard-first-learning-loop-priority', 'dashboard-first-learning-loop-default']) {
  const targetIndex = directChildren.findIndex((node) => (
    node.tag === 'div'
    && node.props.some((prop) => prop.type === NodeTypes.ATTRIBUTE && prop.name === 'id' && prop.value?.content === targetId)
  ))
  assert.ok(targetIndex >= 0 && targetIndex < teleportIndex, `${targetId} is emitted before the Teleport`)
}
assert.match(
  dashboardSource,
  /task:\s*\{\s*path:\s*'\/tasks',\s*query:\s*\{\s*action:\s*'quick-task'\s*}\s*}/,
  'the first onboarding action opens the name-only quick-task path',
)

console.log('first-learning-loop placement checks passed')
