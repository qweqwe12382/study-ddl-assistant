<template>
  <section class="extraction-candidates-mobile" aria-label="智能识别任务结果">
    <p class="extraction-candidates-mobile__hint">逐项核对名称、截止时间和来源；需要留意的提示会直接显示。只有勾选的候选会参与校验和创建。</p>
    <article v-for="(task, index) in tasks" :key="task.candidate_id || `candidate-${index}`" class="extraction-candidate-card">
      <div class="extraction-candidate-card__heading">
        <el-checkbox v-model="task.selected" :aria-label="`选择智能识别任务：${task.name || '未命名任务'}`">加入任务</el-checkbox>
        <span class="extraction-candidate-card__confidence">置信度 {{ confidenceLabel(task.confidence) }}</span>
      </div>

      <div class="extraction-candidate-card__field">
        <label :for="fieldId(index, 'name')">任务名称</label>
        <el-input :id="fieldId(index, 'name')" v-model="task.name" :aria-label="`任务名称：${task.name || '未命名任务'}`" />
      </div>
      <div class="extraction-candidate-card__field">
        <label :for="fieldId(index, 'due-at')">截止时间</label>
        <el-date-picker
          :id="fieldId(index, 'due-at')"
          v-model="task.due_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="待补充"
          :aria-label="`截止时间：${task.name || '未命名任务'}`"
        />
      </div>

      <div class="extraction-candidate-card__source">
        <span>来源原文</span>
        <p>{{ task.source_quote || '无来源原文' }}</p>
        <div v-if="task.warnings?.length" class="extraction-candidate-card__warnings" aria-label="需要留意的提示">
          <span>需要留意</span>
          <el-tag v-for="warning in task.warnings" :key="warning" size="small" type="warning" class="extraction-warning-tag">{{ extractionWarningLabel(warning) }}</el-tag>
        </div>
      </div>

      <details class="extraction-candidate-card__secondary">
        <summary>补充信息：类型和预计用时</summary>
        <div class="extraction-candidate-card__secondary-fields">
          <div class="extraction-candidate-card__field">
            <label :for="fieldId(index, 'type')">任务类型</label>
            <el-input :id="fieldId(index, 'type')" v-model="task.task_type" :aria-label="`任务类型：${task.name || '未命名任务'}`" />
          </div>
          <div class="extraction-candidate-card__field">
            <label :for="fieldId(index, 'duration')">预计用时（分钟）</label>
            <el-input-number
              :id="fieldId(index, 'duration')"
              v-model="task.estimated_minutes"
              :min="15"
              :max="10080"
              :step="15"
              controls-position="right"
              placeholder="可留空"
              :aria-label="`预计用时：${task.name || '未命名任务'}`"
            />
          </div>
        </div>
      </details>
    </article>
  </section>
</template>

<script setup>
import { ElCheckbox, ElDatePicker, ElInput, ElInputNumber, ElTag } from 'element-plus'
import { extractionWarningLabel } from '../utils/extractionWarning'

defineProps({
  tasks: { type: Array, default: () => [] },
})

function confidenceLabel(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`
}

function fieldId(index, field) {
  return `extraction-candidate-${index}-${field}`
}
</script>

<style scoped>
.extraction-candidates-mobile { display: none; }

@media (max-width: 680px) {
  .extraction-candidates-mobile { display: grid; gap: 10px; min-width: 0; }
  .extraction-candidates-mobile__hint { margin: 0; padding: 9px 11px; color: #52617a; background: #f4f5ff; border-left: 3px solid var(--ledger-indigo, #5964ed); font-size: 12px; line-height: 1.55; }
  .extraction-candidate-card { display: grid; gap: 14px; min-width: 0; padding: 14px; color: #344054; background: #fff; border: 1px solid #dfe5f0; border-radius: 9px; }
  .extraction-candidate-card__heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-width: 0; padding-bottom: 10px; border-bottom: 1px solid #edf0f6; }
  .extraction-candidate-card__heading :deep(.el-checkbox) { min-width: 0; font-weight: 700; }
  .extraction-candidate-card__confidence { flex: 0 0 auto; color: #667085; font-size: 12px; line-height: 1.45; }
  .extraction-candidate-card__field { display: grid; gap: 6px; min-width: 0; }
  .extraction-candidate-card__field > label,
  .extraction-candidate-card__source > span,
  .extraction-candidate-card__warnings > span { color: #475467; font-size: 12px; font-weight: 700; line-height: 1.45; }
  .extraction-candidate-card__field :deep(.el-input__wrapper),
  .extraction-candidate-card__field :deep(.el-date-editor),
  .extraction-candidate-card__field :deep(.el-input-number) { width: 100%; min-height: 44px; }
  .extraction-candidate-card__source { display: grid; gap: 5px; min-width: 0; padding: 10px 11px; background: #f8fafc; border-left: 3px solid #c9c2ff; }
  .extraction-candidate-card__source p { margin: 0; color: #475467; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; white-space: pre-wrap; }
  .extraction-candidate-card__warnings { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
  .extraction-warning-tag { max-width: 100%; height: auto; line-height: 1.45; vertical-align: top; white-space: normal; }
  .extraction-warning-tag :deep(.el-tag__content) { overflow-wrap: anywhere; white-space: normal; }
  .extraction-candidate-card__secondary { min-width: 0; color: #475467; border-top: 1px solid #edf0f6; }
  .extraction-candidate-card__secondary > summary { min-height: 44px; padding-top: 12px; color: #475467; cursor: pointer; font-size: 13px; font-weight: 650; line-height: 1.5; }
  .extraction-candidate-card__secondary > summary:focus-visible { outline: 3px solid rgba(89, 100, 237, .5); outline-offset: 3px; }
  .extraction-candidate-card__secondary-fields { display: grid; gap: 12px; padding-top: 7px; }
}
</style>
