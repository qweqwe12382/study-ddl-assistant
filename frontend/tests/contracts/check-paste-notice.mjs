import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import { baseParse } from '@vue/compiler-dom'
import { parse as parseSfc } from '@vue/compiler-sfc'

import {
  buildPastedNotice,
  localReferenceDateTime,
  MAX_PASTE_NOTICE_CHARACTERS,
  pasteNoticeFilename,
  validLocalReferenceDateTime,
} from '../../src/utils/pasteNotice.js'

const validNotice = buildPastedNotice({
  title: '高等数学:作业通知',
  text: ' 明天上午前提交第二章习题。 ',
  sourceTime: '2026-09-09T10:30:00',
})
assert.deepEqual(validNotice, {
  filename: '高等数学 作业通知.txt',
  content: '明天上午前提交第二章习题。',
  sourceTime: '2026-09-09T10:30:00',
})
assert.equal(pasteNoticeFilename('  '), '粘贴资料.txt')
assert.deepEqual(buildPastedNotice({ title: '', text: '高数复习:第三章\n复习微分与积分。', sourceTime: '2026-09-09T10:30:00' }), { filename: '高数复习 第三章.txt', content: '高数复习:第三章\n复习微分与积分。', sourceTime: '2026-09-09T10:30:00' }, 'untitled pasted material receives a safe name from its first line without changing the content or reference time')
assert.equal(localReferenceDateTime(new Date(Date.UTC(2026, 8, 8, 23, 5, 3))), '2026-09-09T07:05:03')
assert.equal(validLocalReferenceDateTime('2024-02-29T23:59:59'), true)
assert.equal(validLocalReferenceDateTime('0001-01-01T00:00:00'), true)
for (const invalidTime of ['2025-02-29T12:00:00', '2026-09-31T12:00:00', '2026-09-09T24:00:00', '2026-09-09T12:60:00', '2026-09-09T12:00:60']) {
  assert.equal(validLocalReferenceDateTime(invalidTime), false, `${invalidTime} is not a calendar datetime`)
}

for (const draft of [
  { title: '', text: '   ', sourceTime: '2026-09-09T10:30:00' },
  { title: '', text: '通知', sourceTime: '' },
  { title: '', text: '通知', sourceTime: '2026-09-09' },
  { title: '', text: '通知', sourceTime: 'invalid' },
  { title: '', text: 'a'.repeat(MAX_PASTE_NOTICE_CHARACTERS + 1), sourceTime: '2026-09-09T10:30:00' },
]) {
  assert.ok(buildPastedNotice(draft).error, 'invalid notification drafts are rejected before upload')
}

const dialogSource = await readFile(new URL('../../src/components/PasteNoticeDialog.vue', import.meta.url), 'utf8')
const dialog = parseSfc(dialogSource, { filename: 'PasteNoticeDialog.vue' })
assert.deepEqual(dialog.errors, [], 'paste-notice dialog SFC parses')
assert.ok(dialog.descriptor.template?.content, 'paste-notice dialog has a template')
baseParse(dialog.descriptor.template.content)
assert.match(dialogSource, /通知标题（可选）/)
assert.match(dialogSource, /通知正文/)
assert.match(dialogSource, /通知参考时间/)
assert.match(dialogSource, /按北京时间（Asia\/Shanghai）处理/)
assert.match(dialogSource, /保留草稿并关闭/)
assert.match(dialogSource, /查看已有资料/)
assert.match(dialogSource, /:disabled="submitting"/)
assert.doesNotMatch(dialogSource, /<form\b/, 'the dialog keeps one Element Plus form instead of nesting native forms')

const apiSource = await readFile(new URL('../../src/api/index.js', import.meta.url), 'utf8')
assert.match(apiSource, /upload: \(files, courseId = null, materialType = null, sourceTime = null\)/)
assert.match(apiSource, /if \(sourceTime\) formData\.append\('source_time', sourceTime\)/)

const materialsSource = await readFile(new URL('../../src/views/MaterialsView.vue', import.meta.url), 'utf8')
// Exercise the real candidate-to-form conversion: a browser in Los Angeles
// must still send 20:00 Shanghai, including on US daylight-saving boundaries.
const conversionSource = materialsSource.match(/function toLocalDateTimeInput\(value\) \{[\s\S]*?\n\}/)?.[0]
assert.ok(conversionSource)
const convertDeadline = new Function('localReferenceDateTime', `${conversionSource}; return toLocalDateTimeInput`)(localReferenceDateTime)
const priorTimezone = process.env.TZ
try {
  for (const timezone of ['America/Los_Angeles', 'Asia/Shanghai', 'UTC']) {
    process.env.TZ = timezone
    for (const [instant, wallClock] of [
      ['2026-10-15T12:00:00Z', '2026-10-15T20:00:00'],
      ['2026-03-07T18:30:00Z', '2026-03-08T02:30:00'],
      ['2026-10-31T17:30:00Z', '2026-11-01T01:30:00'],
    ]) {
      assert.equal(convertDeadline(instant), wallClock, timezone)
      assert.equal(new Date(`${convertDeadline(instant)}+08:00`).toISOString(), new Date(instant).toISOString())
    }
    assert.equal(convertDeadline(null), '')
    assert.equal(convertDeadline('invalid'), '')
  }
} finally {
  if (priorTimezone === undefined) delete process.env.TZ
  else process.env.TZ = priorTimezone
}
assert.match(materialsSource, /action === 'paste-notice'/)
assert.match(materialsSource, /<PasteNoticeDialog/)
assert.match(materialsSource, /new File\(\[notice\.content\], notice\.filename, \{ type: 'text\/plain;charset=utf-8' \}\)/)
assert.match(materialsSource, /materialsApi\.upload\(\[file\], uploadCourseId\.value \|\| positiveRouteId\(route\.query\.course_id\), route\.query\.intent === 'plan' \? '复习安排' : null, notice\.sourceTime\)/, 'pasted content preserves reference time and course or plan-import context, while ordinary text is classified from its content')
assert.match(materialsSource, /err\?\.status === 409 && err\?\.code === 'DUPLICATE_FILE'/)
assert.match(materialsSource, /await openExtraction\(savedMaterial\)/)
assert.match(materialsSource, /const existingMaterials = await materialsApi\.list\(\)/)
assert.match(materialsSource, /confirmed_task_refs/)
assert.match(materialsSource, /<ExtractionReviewContent :result="extractionResult" :tasks="extractionTasks"/)
const reviewSource = await readFile(new URL('../../src/components/ExtractionReviewContent.vue', import.meta.url), 'utf8')
assert.match(reviewSource, /const ExtractionCandidatesEditor = defineAsyncComponent/)
assert.match(reviewSource, /<ExtractionCandidatesEditor :tasks="tasks"/)
assert.match(reviewSource, /<el-table :data="tasks"/)
assert.match(materialsSource, /const extractionEvidenceExpanded = ref\(false\)/)
assert.match(materialsSource, /:aria-expanded="extractionEvidenceExpanded"/)
assert.match(materialsSource, /v-if="extractionEvidenceExpanded"/)
assert.match(materialsSource, /extractionEvidenceExpanded\.value = false/)

const submitStart = materialsSource.indexOf('async function submitPastedNotice()')
const submitEnd = materialsSource.indexOf('\nasync function showExistingPastedNotice()', submitStart)
assert.ok(submitStart >= 0 && submitEnd > submitStart, 'paste submit handler is delimited')
const submitSource = materialsSource.slice(submitStart, submitEnd)
assert.doesNotMatch(submitSource, /materialsApi\.extract\(/, 'saving a notification never starts a second extraction')
assert.ok(submitSource.indexOf('clearPastedNoticeDraft()') < submitSource.indexOf('await openExtraction(savedMaterial)'), 'draft clears only after upload returned a saved material')

const createdTaskStart = materialsSource.indexOf('async function openCreatedTasks()')
const createdTaskEnd = materialsSource.indexOf('\nasync function openConfirmedTaskTarget', createdTaskStart)
assert.ok(createdTaskStart >= 0 && createdTaskEnd > createdTaskStart, 'created-task action is delimited')
const createdTaskSource = materialsSource.slice(createdTaskStart, createdTaskEnd)
assert.doesNotMatch(createdTaskSource, /tasksApi\.list|material_id|router\.push/, 'created-task action never reconstructs an identity or bypasses source resolution')

const confirmedSource = await readFile(new URL('../../src/components/ConfirmedTasksDialog.vue', import.meta.url), 'utf8')
const confirmed = parseSfc(confirmedSource, { filename: 'ConfirmedTasksDialog.vue' })
assert.deepEqual(confirmed.errors, [], 'confirmed-tasks dialog SFC parses')
assert.match(confirmedSource, /navigationKey\(item\?\.navigation_key\)/)
assert.match(confirmedSource, /agentApi\.resolveSourceRefs\(\[sourceRef\]\)/)
assert.match(confirmedSource, /validatedSourceNavigationTarget\(resolved, sourceRef\)/)
assert.match(confirmedSource, /查看任务清单/)
assert.match(confirmedSource, /选择一项任务，继续安排或记录进度/)
assert.match(confirmedSource, /这项任务已删除或暂时无法打开/)
assert.doesNotMatch(confirmedSource, /tasksApi\.list|material_id/, 'confirmed task links do not recover identities from a mutable task list')

const candidatesSource = await readFile(new URL('../../src/components/ExtractionCandidatesEditor.vue', import.meta.url), 'utf8')
const candidates = parseSfc(candidatesSource, { filename: 'ExtractionCandidatesEditor.vue' })
assert.deepEqual(candidates.errors, [], 'mobile extraction-candidate editor SFC parses')
assert.ok(candidates.descriptor.template?.content, 'mobile extraction-candidate editor has a template')
baseParse(candidates.descriptor.template.content)
assert.match(candidatesSource, /v-for="\(task, index\) in tasks"/)
assert.match(candidatesSource, /v-model="task\.selected"/)
assert.match(candidatesSource, /v-model="task\.name"/)
assert.match(candidatesSource, /v-model="task\.due_at"/)
assert.match(candidatesSource, /task\.source_quote \|\| '无来源原文'/)
assert.match(candidatesSource, /v-for="warning in task\.warnings"/)
assert.match(candidatesSource, /<details class="extraction-candidate-card__secondary">/)
assert.match(candidatesSource, /v-model="task\.task_type"/)
assert.match(candidatesSource, /v-model="task\.estimated_minutes"/)
assert.match(candidatesSource, /@media \(max-width: 680px\)/)
assert.doesNotMatch(candidatesSource, /tasksApi|materialsApi|emit\(/, 'mobile editor shares rows with the existing confirmation path without creating a second submit path')



const taskEditorSource = await readFile(new URL('../../src/views/TasksView.vue', import.meta.url), 'utf8')
const taskFunctions = ['parseLocalDateTime', 'toUtcIso', 'toLocalDateTimeInput'].map(name => taskEditorSource.match(new RegExp(`function ${name}\\(value\\) \\{[\\s\\S]*?\\n\\}`))?.[0]).join('\n')
const editor = new Function('localReferenceDateTime', 'validLocalReferenceDateTime', `${taskFunctions}; return {toUtcIso, toLocalDateTimeInput}`)(localReferenceDateTime, validLocalReferenceDateTime)
assert.equal(editor.toLocalDateTimeInput('2026-10-15T12:00:00Z'), '2026-10-15T20:00:00')
assert.equal(editor.toUtcIso('2026-10-15T20:00:00'), '2026-10-15T12:00:00.000Z')
assert.equal(editor.toUtcIso('2026-03-08T02:30:00'), '2026-03-07T18:30:00.000Z')
assert.equal(editor.toUtcIso('2026-02-30T12:00:00'), null)

// Test the actual list formatting and day bucketing against Shanghai midnight.
const flowSource = await readFile(new URL('../../src/components/DeadlineFlow.vue', import.meta.url), 'utf8')
const flowFormat = flowSource.match(/function formatDueAt\(value\) \{[\s\S]*?\n\}/)[0]
const formatFlow = new Function(`${flowFormat}; return formatDueAt`)()
assert.match(formatFlow(new Date('2026-10-15T12:00:00Z')), /20:00/)
const agendaSource = await readFile(new URL('../../src/components/TaskAgenda.vue', import.meta.url), 'utf8')
const dayFunction = agendaSource.match(/function localDayKey\(date\) \{[\s\S]*?\n\}/)[0]
const dayKey = new Function(`${dayFunction}; return localDayKey`)()
assert.equal(dayKey(new Date('2026-10-15T16:30:00Z')), Date.UTC(2026, 9, 16))
console.log('Paste-notice and Shanghai task-time contracts passed.')
