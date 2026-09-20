<template>
    <details class="material-flow">
      <summary class="material-flow-toggle"><span>资料、任务与计划</span><span>识别后，由你确认创建</span></summary>
      <div class="material-flow-heading">
        <div>
          <h2 id="material-flow-heading">先整理内容，再安排学习</h2>
        </div>
          <p class="material-flow-heading-note">识别只提供候选，正式任务仍由你确认</p>
      </div>
      <ol class="material-flow-list">
        <li class="material-flow-item">
          <article class="material-flow-card material-flow-card--intake">
            <div class="material-flow-label">
              <span class="material-flow-index" aria-hidden="true">01</span>
              <span>保存资料</span>
            </div>
            <h3>先把资料保存好</h3>
            <p class="material-flow-action"><strong>你要做</strong> 上传文件，或手动补充文件名、正文和标签。</p>
            <p class="material-flow-state" :class="`is-${materialIntakeState.tone}`" aria-live="polite">{{ materialIntakeState.label }}</p>
            <p class="material-flow-boundary"><strong>这里会发生什么</strong> 这一步只保存资料；处理失败时，需要你重试或补充正文。</p>
          </article>
        </li>
        <li class="material-flow-item">
          <article class="material-flow-card material-flow-card--recognition">
            <div class="material-flow-label">
              <span class="material-flow-index" aria-hidden="true">02</span>
              <span>核对结果</span>
            </div>
            <h3>区分学习内容与任务要求</h3>
            <p class="material-flow-action"><strong>你要做</strong> 保存后直接查看整理结果，核对任务名称、日期和来源。</p>
            <p class="material-flow-state" :class="`is-${extractionFlowState.tone}`" aria-live="polite">{{ extractionFlowState.label }}</p>
            <div v-if="extractionFlowStatuses.length" class="material-flow-statuses" role="list" aria-label="智能识别状态统计">
              <span v-for="status in extractionFlowStatuses" :key="status.key" class="material-flow-status" :class="`is-${status.tone}`" role="listitem">
                <span>{{ status.label }}</span><strong>{{ status.count }}</strong>
              </span>
            </div>
            <p class="material-flow-boundary"><strong>确认边界</strong> 识别结果只是候选，不会自动写入正式任务。</p>
          </article>
        </li>
        <li class="material-flow-item">
          <article class="material-flow-card material-flow-card--confirmation">
            <div class="material-flow-label">
              <span class="material-flow-index" aria-hidden="true">03</span>
            <span>按需安排学习</span>
            </div>
            <h3>保留资料，或继续安排复习</h3>
            <p class="material-flow-action"><strong>你要做</strong> 需要完成的事项确认加入任务，学习资料可按课程安排复习。</p>
            <p class="material-flow-state" :class="`is-${confirmationFlowState.tone}`" aria-live="polite">{{ confirmationFlowState.label }}</p>
            <div v-if="confirmationFlowStatuses.length" class="material-flow-statuses" role="list" aria-label="人工确认状态统计">
              <span v-for="status in confirmationFlowStatuses" :key="status.key" class="material-flow-status" :class="`is-${status.tone}`" role="listitem">
                <span>{{ status.label }}</span><strong>{{ status.count }}</strong>
              </span>
            </div>
            <p class="material-flow-boundary"><strong>确认边界</strong> 只有点击“确认加入任务”，勾选的事项才会成为正式任务。</p>
          </article>
        </li>
      </ol>
    </details>
</template>

<script setup>
import { computed, toRefs } from 'vue'
const props = defineProps({ materials: { type: Array, default: () => [] }, ready: Boolean, busy: Boolean, error: { type: String, default: '' }, filtered: Boolean })
const { materials: flowMaterials, ready: materialsSummaryReady, busy: loading, error, filtered: hasActiveMaterialFilter } = toRefs(props)
const extractionFlowStatusMeta = Object.freeze({
  not_started: { label: '未识别', tone: 'neutral' },
  ready: { label: '待确认', tone: 'ready' },
  needs_review: { label: '待确认', tone: 'review' },
  confirmed: { label: '已确认', tone: 'confirmed' },
  failed: { label: '识别失败', tone: 'failed' },
  unknown: { label: '状态待确认', tone: 'unknown' },
})
const extractionFlowStatusOrder = Object.freeze(['not_started', 'ready', 'needs_review', 'confirmed', 'failed', 'unknown'])
const processingFlowStatusMeta = Object.freeze({
  pending: { label: '待处理', tone: 'neutral' },
  processing: { label: '处理中', tone: 'ready' },
  processed: { label: '已处理', tone: 'confirmed' },
  failed: { label: '处理失败', tone: 'failed' },
  unknown: { label: '状态待确认', tone: 'unknown' },
})
function flowStatusKey(value, statusMeta) {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(statusMeta, value) ? value : 'unknown'
}

function summarizeFlowStatuses(rows, field, statusMeta, statusOrder) {
  const counts = Object.fromEntries(statusOrder.map((status) => [status, 0]))
  rows.forEach((row) => {
    const status = flowStatusKey(row?.[field], statusMeta)
    counts[status] += 1
  })
  return statusOrder
    .filter((status) => counts[status] > 0)
    .map((status) => ({ key: status, count: counts[status], ...statusMeta[status] }))
}

function flowStatusCount(statuses, key) {
  return statuses.find((status) => status.key === key)?.count || 0
}

const processingFlowStatusOrder = Object.freeze(['pending', 'processing', 'processed', 'failed', 'unknown'])
const processingFlowStatuses = computed(() => {
  if (!materialsSummaryReady.value) return []
  return summarizeFlowStatuses(flowMaterials.value, 'processing_status', processingFlowStatusMeta, processingFlowStatusOrder)
})
const extractionFlowStatuses = computed(() => {
  if (!materialsSummaryReady.value) return []
  return summarizeFlowStatuses(flowMaterials.value, 'extraction_status', extractionFlowStatusMeta, extractionFlowStatusOrder)
})
const confirmationFlowStatuses = computed(() => extractionFlowStatuses.value.filter((status) => ['ready', 'needs_review', 'confirmed', 'unknown'].includes(status.key)))

const materialIntakeState = computed(() => {
  if (!materialsSummaryReady.value) {
    return { label: error.value ? '资料列表暂不可用' : loading.value ? '正在读取资料列表…' : '等待资料列表', tone: 'unknown' }
  }
  if (!flowMaterials.value.length) {
    return { label: hasActiveMaterialFilter.value ? '当前筛选没有匹配资料' : '还没有资料', tone: 'neutral' }
  }
  const failed = flowStatusCount(processingFlowStatuses.value, 'failed')
  const pending = flowStatusCount(processingFlowStatuses.value, 'pending')
    + flowStatusCount(processingFlowStatuses.value, 'processing')
  const unknown = flowStatusCount(processingFlowStatuses.value, 'unknown')
  if (failed) return { label: `当前列表 ${flowMaterials.value.length} 份资料 · ${failed} 份处理失败`, tone: 'failed' }
  if (pending) return { label: `当前列表 ${flowMaterials.value.length} 份资料 · ${pending} 份待处理`, tone: 'review' }
  if (unknown) return { label: `当前列表 ${flowMaterials.value.length} 份资料 · ${unknown} 份状态待确认`, tone: 'unknown' }
  return { label: `当前列表 ${flowMaterials.value.length} 份资料`, tone: 'ready' }
})

const extractionFlowState = computed(() => {
  if (!materialsSummaryReady.value) {
    return { label: error.value ? '资料列表暂不可用' : loading.value ? '正在读取资料列表…' : '等待资料列表', tone: 'unknown' }
  }
  if (!flowMaterials.value.length) {
    return { label: hasActiveMaterialFilter.value ? '当前筛选没有可识别资料' : '还没有可识别资料', tone: 'neutral' }
  }
  const needsReview = flowStatusCount(extractionFlowStatuses.value, 'needs_review')
  const ready = flowStatusCount(extractionFlowStatuses.value, 'ready')
  const notStarted = flowStatusCount(extractionFlowStatuses.value, 'not_started')
  const failed = flowStatusCount(extractionFlowStatuses.value, 'failed')
  const confirmed = flowStatusCount(extractionFlowStatuses.value, 'confirmed')
  const unknown = flowStatusCount(extractionFlowStatuses.value, 'unknown')
  if (needsReview) return { label: `${needsReview} 份结果待确认`, tone: 'review' }
  if (ready) return { label: `${ready} 份结果待确认`, tone: 'ready' }
  if (notStarted) return { label: `${notStarted} 份资料尚未识别`, tone: 'neutral' }
  if (failed) return { label: `${failed} 份资料识别失败`, tone: 'failed' }
  if (confirmed) return { label: `${confirmed} 份识别结果已确认`, tone: 'confirmed' }
  if (unknown) return { label: `${unknown} 份识别状态待确认`, tone: 'unknown' }
  return { label: '识别状态待确认', tone: 'unknown' }
})

const confirmationFlowState = computed(() => {
  if (!materialsSummaryReady.value) {
    return { label: error.value ? '资料列表暂不可用' : loading.value ? '正在读取资料列表…' : '等待资料列表', tone: 'unknown' }
  }
  if (!flowMaterials.value.length) {
    return { label: hasActiveMaterialFilter.value ? '当前筛选没有待确认资料' : '还没有待确认结果', tone: 'neutral' }
  }
  const ready = flowStatusCount(extractionFlowStatuses.value, 'ready')
  const needsReview = flowStatusCount(extractionFlowStatuses.value, 'needs_review')
  const confirmed = flowStatusCount(extractionFlowStatuses.value, 'confirmed')
  const failed = flowStatusCount(extractionFlowStatuses.value, 'failed')
  const notStarted = flowStatusCount(extractionFlowStatuses.value, 'not_started')
  const unknown = flowStatusCount(extractionFlowStatuses.value, 'unknown')
  if (ready + needsReview) return { label: `待人工确认 ${ready + needsReview} 份候选`, tone: 'review' }
  if (failed) return { label: `${failed} 份识别失败，暂不能确认`, tone: 'failed' }
  if (notStarted) return { label: `${notStarted} 份资料尚未产生识别结果`, tone: 'neutral' }
  if (unknown) return { label: `${unknown} 份状态待确认`, tone: 'unknown' }
  if (confirmed) return { label: `${confirmed} 份结果已确认`, tone: 'confirmed' }
  return { label: '确认状态尚未确定', tone: 'unknown' }
})

</script>

<style scoped>

.material-flow {
  min-width: 0;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--materials-line);
}

.material-flow-toggle {
  min-height: 40px;
  color: var(--materials-ink);
  cursor: pointer;
  font-size: 13px;
  line-height: 40px;
}

.material-flow-toggle span + span {
  margin-left: 20px;
  color: var(--materials-muted);
  font-size: 12px;
}

.material-flow-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 18px;
  min-width: 0;
  margin: 14px 0 11px;
}

.material-flow-eyebrow,
.material-toolbar-kicker {
  margin: 0 0 4px;
  color: var(--materials-muted);
  font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.material-flow-heading h2 {
  margin: 0;
  color: var(--materials-ink);
  font-size: 16px;
  letter-spacing: .01em;
}

.material-flow-heading-note {
  max-width: 360px;
  margin: 0;
  color: var(--materials-muted);
  font-size: 12px;
  line-height: 1.5;
  text-align: right;
}

.material-flow-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.material-flow-item {
  position: relative;
  min-width: 0;
}

.material-flow-item:not(:last-child)::after {
  content: none;
}

.material-flow-card {
  box-sizing: border-box;
  height: 100%;
  min-width: 0;
  padding: 8px 14px 8px 0;
  color: var(--materials-ink);
  border-right: 1px solid var(--materials-line);
}

.material-flow-item:last-child .material-flow-card { border-right: 0; }

.material-flow-label {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  min-width: 0;
  color: var(--materials-ink);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .03em;
}

.material-flow-index {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: 24px;
  height: 24px;
  color: var(--materials-indigo);
  background: #edf5f0;
  border-radius: 4px;
  font-family: inherit;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  letter-spacing: .08em;
}

.material-flow-card h3 {
  margin: 14px 0 7px;
  color: var(--materials-ink);
  font-size: 15px;
  line-height: 1.35;
}

.material-flow-action,
.material-flow-boundary {
  overflow-wrap: anywhere;
}

.material-flow-action {
  min-height: 40px;
  margin: 0;
  color: var(--materials-muted);
  font-size: 13px;
  line-height: 1.65;
}

.material-flow-action strong,
.material-flow-boundary strong {
  margin-right: 4px;
  color: var(--materials-ink);
  font-size: 12px;
  font-weight: 700;
}

.material-flow-state {
  display: flex;
  align-items: baseline;
  min-width: 0;
  min-height: 18px;
  margin: 12px 0 0;
  color: var(--materials-ink);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.material-flow-state.is-ready { color: var(--materials-indigo); }
.material-flow-state.is-review { color: var(--materials-amber-text); }
.material-flow-state.is-failed { color: var(--materials-coral); }
.material-flow-state.is-unknown { color: var(--materials-muted); }

.material-flow-statuses {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  margin-top: 8px;
}

.material-flow-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 3px 7px;
  color: var(--materials-ink);
  border: 1px solid rgba(30, 42, 68, .22);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.35;
}

.material-flow-status strong { font-variant-numeric: tabular-nums; }
.material-flow-status.is-ready { color: var(--materials-indigo); border-color: color-mix(in srgb, var(--ledger-indigo) 38%, transparent); }
.material-flow-status.is-review { color: var(--materials-amber-text); border-color: rgba(201, 130, 46, .46); }
.material-flow-status.is-confirmed { color: var(--materials-ink); border-color: rgba(30, 42, 68, .32); }
.material-flow-status.is-failed { color: var(--materials-coral); border-color: rgba(201, 76, 76, .42); }
.material-flow-status.is-unknown { color: var(--materials-muted); border-color: rgba(102, 112, 133, .38); }

.material-flow-boundary {
  min-height: 37px;
  margin: 12px 0 0;
  padding-top: 10px;
  color: var(--materials-muted);
  border-top: 1px solid var(--materials-line);
  font-size: 13px;
  line-height: 1.55;
}

.material-flow-toggle:focus-visible { outline: 3px solid color-mix(in srgb, var(--materials-indigo) 38%, transparent); outline-offset: 3px; }
@media (max-width: 680px) {
  .material-flow-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .material-flow-heading-note {
    max-width: none;
    text-align: left;
  }

  .material-flow-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .material-flow-item:not(:last-child)::after {
    display: none;
  }

  .material-flow-card {
    padding: 12px 0;
    border-right: 0;
    border-bottom: 1px solid var(--materials-line);
  }

  .material-flow-item:last-child .material-flow-card { border-bottom: 0; }
  .material-flow-toggle { line-height: 1.6; padding: 8px 0; }
  .material-flow-toggle span + span { display: block; margin: 2px 0 0 16px; }

}
</style>
