import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import { baseParse, NodeTypes } from '@vue/compiler-dom'
import { parse as parseSfc } from '@vue/compiler-sfc'

import {
  isFirstLearningLoopIncomplete,
  shouldPrioritizeFirstLearningLoop,
  strictNonNegativeInteger,
} from '../../src/utils/firstLearningLoopPlacement.js'

const freshProgress = {
  courses_count: 0,
  materials_count: 0,
  active_task_count: 0,
  completed_task_count: 0,
}

assert.equal(strictNonNegativeInteger(0), 0)
for (const invalid of [null, undefined, false, true, '', '0', 1.2, -1, Number.NaN]) {
  assert.equal(strictNonNegativeInteger(invalid), null, `does not coerce ${String(invalid)} into a count`)
}

assert.equal(isFirstLearningLoopIncomplete(freshProgress), true)
for (const incompleteOrUnknown of [
  null,
  {},
  { ...freshProgress, courses_count: false },
  { ...freshProgress, materials_count: '' },
  { ...freshProgress, active_task_count: null },
  { courses_count: 0, materials_count: 0, active_task_count: 0 },
]) {
  assert.equal(isFirstLearningLoopIncomplete(incompleteOrUnknown), false)
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
assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, hasFocus: true }), false)
assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, attentionCount: 1 }), false)
assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, attentionCount: false }), false)
assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, attentionCount: null }), false)
for (const state of ['loading', 'error', 'invalid']) {
  assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, dashboardState: state }), false)
  assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, agentState: state }), false)
}
for (const decisionQueueStatus of ['unavailable', 'invalid']) {
  assert.equal(shouldPrioritizeFirstLearningLoop({ ...readyContext, decisionQueueStatus }), false)
}

const dashboardSource = await readFile(new URL('../../src/views/DashboardView.vue', import.meta.url), 'utf8')
const { descriptor, errors } = parseSfc(dashboardSource, { filename: 'DashboardView.vue' })
assert.deepEqual(errors, [], 'Dashboard SFC parses without compiler errors')
assert.ok(descriptor.template?.content, 'Dashboard has a parseable template')
const ast = baseParse(descriptor.template.content)
const dashboardRoot = ast.children.find((node) => node.type === NodeTypes.ELEMENT && node.tag === 'div')
assert.ok(dashboardRoot, 'Dashboard template has a root element')
const directChildren = dashboardRoot.children.filter((node) => node.type === NodeTypes.ELEMENT)
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

console.log('first-learning-loop placement checks passed')
