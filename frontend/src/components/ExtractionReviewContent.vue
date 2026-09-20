<template>
  <section class="learning-preview" aria-label="资料内容">
    <div class="preview-heading"><span class="preview-icon" aria-hidden="true">▤</span><div><strong>{{ kindLabel }}</strong><p>{{ result.content_kind === 'review_outline' ? '这是一份已有的复习安排。可作参考，原日期不会直接导入新计划。' : '资料用于学习；需要提交或参加的事项在下方单独确认。' }}</p></div></div>
    <details v-if="result.learning_points?.length"><summary>查看内容摘录 · {{ result.learning_points.length }} 条</summary><ul><li v-for="point in result.learning_points" :key="point">{{ point }}</li></ul></details>
  </section>
  <section v-if="tasks.length" class="task-preview" aria-label="待确认任务">
    <h3>{{ result.status === 'confirmed' ? '已加入任务' : '核对任务' }} <span>{{ tasks.length }} 条</span></h3>
    <ul v-if="result.status === 'confirmed'" class="confirmed-task-list" aria-label="已加入的任务">
      <li v-for="(task, index) in tasks" :key="task.candidate_id || index"><strong>{{ task.name }}</strong><span>截止：{{ displayDueAt(task.due_at) }}</span><details><summary>查看来源与任务信息</summary><p>{{ task.source_quote || '无来源原文' }}</p><p>{{ task.task_type || '任务' }} · {{ task.estimated_minutes ? `预计 ${task.estimated_minutes} 分钟` : '用时待补充' }}</p></details></li>
    </ul>
    <template v-else>
      <p class="task-selection-help">只把需要完成的事项勾选加入。请核对截止时间；不明确的可以留空，之后再补充。</p>
        <div class="table-wrap extraction-table-wrap extraction-desktop-table">
          <el-table :data="tasks" empty-text="暂未识别到任务" aria-label="智能识别任务结果">
          <el-table-column label="确认" width="70">
            <template #default="{ row }"><el-checkbox v-model="row.selected" :aria-label="`选择智能识别任务：${row.name || '未命名任务'}`" /></template>
          </el-table-column>
          <el-table-column label="任务名称" min-width="210">
            <template #default="{ row }"><el-input v-model="row.name" size="small" :aria-label="`任务名称：${row.name || '未命名任务'}`" /></template>
          </el-table-column>
          <el-table-column label="截止时间" width="205">
            <template #default="{ row }">
              <el-date-picker v-model="row.due_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" size="small" placeholder="待补充" :aria-label="`截止时间：${row.name || '未命名任务'}`" />
            </template>
          </el-table-column>
          <el-table-column label="来源 / 提示" min-width="230">
            <template #default="{ row }">
              <div class="row-meta">{{ row.source_quote || '无来源原文' }}</div>
              <el-tag v-for="warning in row.warnings || []" :key="warning" size="small" type="warning" class="tag-gap extraction-warning-tag">{{ extractionWarningLabel(warning) }}</el-tag>
              <details class="task-extra-fields"><summary>类型、用时与识别信息</summary><label>类型<el-input v-model="row.task_type" size="small" :aria-label="`任务类型：${row.name || '未命名任务'}`" /></label><label>预计用时（分钟）<el-input-number v-model="row.estimated_minutes" :min="15" :max="10080" :step="15" size="small" controls-position="right" placeholder="可留空" :aria-label="`预计用时：${row.name || '未命名任务'}`" /></label><p>识别置信度 {{ `${Math.round((row.confidence || 0) * 100)}%` }}</p></details>
            </template>
          </el-table-column>
          </el-table>
        </div>
        <ExtractionCandidatesEditor :tasks="tasks" />
    </template>
  </section>
  <p v-else class="no-tasks" role="status">{{ result.status === 'confirmed' ? '已按你的选择保存资料，未创建任务。' : '没有需要提交或参加的明确事项，保留为学习资料即可。' }}<span v-if="result.status !== 'confirmed' && result.warnings?.length">{{ result.warnings.map(extractionWarningLabel).join('；') }}</span></p>
</template>
<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { ElTable, ElTableColumn, ElCheckbox, ElInput, ElInputNumber, ElDatePicker, ElTag } from 'element-plus'
import { extractionWarningLabel } from '../utils/extractionWarning'
const props = defineProps({ result: { type: Object, required: true }, tasks: { type: Array, required: true } })
const kindLabel = computed(() => ({ study_material: '学习资料', review_outline: '复习安排 · 参考', task_notice: '任务通知', mixed: '学习内容与任务要求' })[props.result.content_kind] || '资料内容')
const ExtractionCandidatesEditor = defineAsyncComponent(() => import('./ExtractionCandidatesEditor.vue'))
function displayDueAt(value) {
  if (!value) return '待补充'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}
</script>
<style scoped>
.learning-preview { padding: 16px; margin: 18px 0; background: var(--accent-soft, #eff5f0); border-radius: 12px; }
.preview-heading { display: flex; gap: 12px; align-items: flex-start; }
.preview-icon { font-size: 24px; color: var(--ledger-primary); }
p { margin: 6px 0 0; line-height: 1.65; color: var(--ledger-muted); font-size: 13px; }
summary { cursor: pointer; margin-top: 12px; font-size: 13px; padding: 6px 0; }
li { line-height: 1.7; margin: 6px 0; overflow-wrap: anywhere; }
h3 { margin: 20px 0 12px; font-size: 15px; } h3 span { font-size: 12px; font-weight: 400; color: var(--ledger-muted); }
.extraction-table-wrap { overflow-x: auto; }
.extraction-duration-input { width: 120px; }
.extraction-warning-tag { margin: 4px 4px 0 0; height: auto; white-space: normal; }
.no-tasks { padding: 10px 0; }
.no-tasks span { display: block; }
.task-selection-help { margin-bottom: 12px; }
.task-extra-fields label { display: grid; gap: 6px; margin: 10px 0; color: var(--ledger-muted); font-size: 12px; }
.confirmed-task-list { list-style: none; padding: 0; }
.confirmed-task-list li { padding: 12px 0; border-bottom: 1px solid var(--ledger-line, #d9e0ea); }
.confirmed-task-list strong, .confirmed-task-list li > span { display: block; }
.confirmed-task-list li > span { font-size: 13px; color: var(--ledger-muted); }
@media (max-width: 680px) { .extraction-desktop-table { display: none; } }
</style>
