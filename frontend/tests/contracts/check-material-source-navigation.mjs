import assert from 'node:assert/strict'

import {
  dashboardMaterialSourceContext,
  navigationSourceCacheKey,
  positiveMaterialId,
  normalizedNavigationSourceRef,
  validatedMaterialTarget,
  validatedSourceNavigationTarget,
} from '../../src/utils/materialSourceNavigation.js'

const materialKey = '0123456789abcdef0123456789abcdef'
const taskKey = 'fedcba9876543210fedcba9876543210'

const validResponse = {
  items: [{
    available: true,
    source_ref: { source_type: 'material', source_id: '7', navigation_key: materialKey },
    target: { path: '/materials', query: { material_id: '7', navigation_key: materialKey } },
  }],
}

assert.deepEqual(
  validatedMaterialTarget(validResponse, 7, materialKey),
  { path: '/materials', query: { material_id: '7', navigation_key: materialKey } },
)

const rejectedResponses = [
  null,
  { items: [] },
  { items: [validResponse.items[0], validResponse.items[0]] },
  { items: [{ ...validResponse.items[0], available: false }] },
  { items: [{ ...validResponse.items[0], source_ref: { source_type: 'task', source_id: '7', navigation_key: materialKey } }] },
  { items: [{ ...validResponse.items[0], source_ref: { source_type: 'material', source_id: '8', navigation_key: materialKey } }] },
  { items: [{ ...validResponse.items[0], source_ref: { source_type: 'material', source_id: ['7'], navigation_key: materialKey } }] },
  { items: [{ ...validResponse.items[0], source_ref: { source_type: 'material', source_id: { id: 7 }, navigation_key: materialKey } }] },
  { items: [{ ...validResponse.items[0], source_ref: { source_type: 'material', source_id: '07', navigation_key: materialKey } }] },
  { items: [{ ...validResponse.items[0], source_ref: { source_type: 'material', source_id: '7' } }] },
  { items: [{ ...validResponse.items[0], source_ref: { source_type: 'material', source_id: '7', navigation_key: taskKey } }] },
  { items: [{ ...validResponse.items[0], target: { path: '/materials', query: { material_id: '7', navigation_key: taskKey } } }] },
  { items: [{ ...validResponse.items[0], target: { path: '/materials', query: { material_id: ['7'], navigation_key: materialKey } } }] },
  { items: [{ ...validResponse.items[0], target: { path: 'https://example.invalid', query: { material_id: '7' } } }] },
  { items: [{ ...validResponse.items[0], target: { path: '/tasks', query: { material_id: '7' } } }] },
  { items: [{ ...validResponse.items[0], target: { path: '/materials', query: { material_id: '8' } } }] },
  { items: [{ ...validResponse.items[0], target: { path: '/materials', query: { material_id: '7', navigation_key: materialKey, q: 'override' } } }] },
  { items: [{ ...validResponse.items[0], target: { path: '/materials', query: { material_id: '7' } } }] },
]

for (const response of rejectedResponses) {
  assert.equal(validatedMaterialTarget(response, 7, materialKey), null)
}

for (const value of [null, {}, 0, -1, 1.5, '01', ' 1', '1e1', '99999999999']) {
  assert.equal(positiveMaterialId(value), null)
}
assert.equal(positiveMaterialId(7), 7)
assert.equal(positiveMaterialId('7'), 7)

assert.equal(dashboardMaterialSourceContext({
  material_id: 7,
  material_name: '讲义.pdf',
  source_available: true,
  material_navigation_key: materialKey,
}).state, 'available')
assert.equal(dashboardMaterialSourceContext({
  material_id: null,
  material_name: '历史讲义.pdf',
  source_available: false,
}).state, 'deleted')
assert.equal(dashboardMaterialSourceContext({
  material_id: null,
  material_name: null,
  source_available: false,
}).state, 'missing')
assert.equal(dashboardMaterialSourceContext({
  material_id: 7,
  material_name: '旧讲义.pdf',
  source_available: true,
}).state, 'identity_missing')

for (const contradictory of [
  { material_id: 7, material_name: '讲义.pdf', source_available: false },
  { material_id: null, material_name: '讲义.pdf', source_available: true },
  { material_id: '1e1', material_name: '讲义.pdf', source_available: true },
  { material_id: 'invalid', material_name: '讲义.pdf', source_available: false },
  { source_available: false },
]) {
  assert.equal(dashboardMaterialSourceContext(contradictory).state, 'contradictory')
}

const taskRef = { source_type: 'task', source_id: '12', navigation_key: taskKey }
assert.deepEqual(normalizedNavigationSourceRef(taskRef), { ...taskRef, source_id: 12 })
assert.equal(normalizedNavigationSourceRef({ source_type: 'task', source_id: '12' }), null)
assert.equal(normalizedNavigationSourceRef({ source_type: 'task', source_id: '12', navigation_key: ` ${taskKey}` }), null)
assert.equal(normalizedNavigationSourceRef({ source_type: 'task', source_id: '12x', navigation_key: taskKey }), null)
assert.equal(normalizedNavigationSourceRef({ source_type: 'study_plan_item', source_id: '1:item', navigation_key: taskKey }).source_id, '1:item')
assert.equal(normalizedNavigationSourceRef({ source_type: 'study_plan_item', source_id: '1:\nitem', navigation_key: taskKey }), null)
assert.notEqual(navigationSourceCacheKey(taskRef), navigationSourceCacheKey({ ...taskRef, navigation_key: materialKey }))
assert.deepEqual(validatedSourceNavigationTarget({
  items: [{ available: true, source_ref: taskRef, target: { path: '/tasks', query: { task_id: '12', navigation_key: taskKey } } }],
}, taskRef), { path: '/tasks', query: { task_id: '12', navigation_key: taskKey } })
assert.equal(validatedSourceNavigationTarget({
  items: [{ available: true, source_ref: taskRef, target: { path: '/tasks', query: { task_id: '13', navigation_key: taskKey } } }],
}, taskRef), null)
assert.equal(validatedSourceNavigationTarget({
  items: [{ available: true, source_ref: taskRef, target: { path: '/tasks', query: { task_id: ['12'], navigation_key: taskKey } } }],
}, taskRef), null)
assert.equal(validatedSourceNavigationTarget({
  items: [{ available: true, source_ref: taskRef, target: { path: '/tasks', query: { task_id: '12', navigation_key: materialKey } } }],
}, taskRef), null)

console.log('Material source navigation check passed.')
