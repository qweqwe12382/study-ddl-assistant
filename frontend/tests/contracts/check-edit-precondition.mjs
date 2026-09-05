import assert from 'node:assert/strict'

import { editBaseline, editRequestConfig, extractionPreviewBaseline, isEditConflict, isEntityGone } from '../../src/utils/editPrecondition.js'

const key = '0123456789abcdef0123456789abcdef'
const baseline = editBaseline({ id: 7, navigation_key: key, revision: 3 })
assert.deepEqual(baseline, { id: 7, navigation_key: key, revision: 3 })
assert.deepEqual(editRequestConfig(baseline), { headers: { 'If-Match': `"${key}:3"` } })

for (const invalid of [
  null,
  { id: 7, navigation_key: key, revision: 0 },
  { id: 7, navigation_key: key, revision: '3' },
  { id: 7, navigation_key: ` ${key}`, revision: 3 },
  { id: ['7'], navigation_key: key, revision: 3 },
]) {
  assert.equal(editBaseline(invalid), null)
  assert.equal(editRequestConfig(invalid), null)
}

assert.equal(isEditConflict({ code: 'EDIT_CONFLICT' }), true)
assert.equal(isEditConflict({ code: 'INVALID_EDIT_PRECONDITION' }), false)
assert.equal(isEntityGone({ status: 404, code: 'TASK_NOT_FOUND' }, 'TASK_NOT_FOUND'), true)
assert.equal(isEntityGone({ status: 404, code: 'MATERIAL_NOT_FOUND' }, 'TASK_NOT_FOUND'), false)
assert.equal(isEntityGone({ status: 404, code: 'FILE_NOT_FOUND' }, 'MATERIAL_NOT_FOUND'), false)

assert.deepEqual(
  extractionPreviewBaseline({ id: 7, navigation_key: key, revision: 3 }, { material_id: 7, material_navigation_key: key, material_revision: 4 }),
  { id: 7, navigation_key: key, revision: 4 },
)
for (const result of [
  { material_id: 8, material_navigation_key: key, material_revision: 4 },
  { material_id: 7, material_navigation_key: 'abcdefabcdefabcdefabcdefabcdefab', material_revision: 4 },
  { material_id: 7, material_navigation_key: key, material_revision: 0 },
]) {
  assert.equal(extractionPreviewBaseline({ id: 7, navigation_key: key, revision: 3 }, result), null)
}
console.log('Edit precondition check passed.')
