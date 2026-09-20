import assert from 'node:assert/strict'
import { QUICK_COMMANDS, filterWorkspaceCommands, isCommandShortcut } from '../../src/utils/workspaceCommands.js'

assert.equal(isCommandShortcut({ key: 'k', ctrlKey: true }), true)
assert.equal(isCommandShortcut({ key: 'K', metaKey: true }), true)
for (const extra of [{ isComposing: true }, { keyCode: 229 }, { repeat: true }, { altKey: true }, { shiftKey: true }]) {
  assert.equal(isCommandShortcut({ key: 'k', ctrlKey: true, ...extra }), false)
}
assert.equal(isCommandShortcut({ key: 'k' }), false)
assert.equal(isCommandShortcut({ key: 'j', ctrlKey: true }), false)
assert.equal(filterWorkspaceCommands(QUICK_COMMANDS, '   ').length, QUICK_COMMANDS.length)
assert.deepEqual(filterWorkspaceCommands(QUICK_COMMANDS, '作业 添加').map(item => item.id), ['quick-task'])
assert.deepEqual(filterWorkspaceCommands(QUICK_COMMANDS, 'FOCUS').map(item => item.id), ['start-focus'])
assert.deepEqual(filterWorkspaceCommands(QUICK_COMMANDS, '无匹配内容'), [])
assert.deepEqual(filterWorkspaceCommands(QUICK_COMMANDS, '通知')[0].to, { path: '/materials', query: { action: 'paste-notice' } })
assert.equal(new Set(QUICK_COMMANDS.map(item => item.id)).size, QUICK_COMMANDS.length)
console.log('Workspace command search and shortcut checks passed.')
