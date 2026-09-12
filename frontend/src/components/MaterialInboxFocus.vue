<template>
  <section class="material-inbox-focus" aria-labelledby="material-inbox-focus-title" :aria-busy="viewState === 'loading'">
    <header class="inbox-header">
      <div class="inbox-heading">
        <h2 id="material-inbox-focus-title">待整理的资料</h2>
        <p class="inbox-description">识别结果只是候选；核对后，才会创建正式截止任务。</p>
      </div>
      <span class="inbox-state-label" :class="`is-${viewState}`">{{ stateLabel }}</span>
    </header>

    <div v-if="viewState !== 'ready'" class="inbox-notice" :class="`is-${viewState}`" :role="viewState === 'error' ? 'alert' : 'status'" aria-live="polite">
      <strong>{{ stateTitle }}</strong>
      <p>{{ stateDescription }}</p>
      <button v-if="viewState === 'error'" type="button" class="inbox-button is-primary" @click="emit('retry-load')">重试读取资料</button>
    </div>

    <template v-else>
      <div v-if="visibleMaterials.length" class="inbox-queue" role="list" aria-label="资料确认优先队列">
        <article
          v-for="material in visibleMaterials"
          :key="material.id"
          class="inbox-item"
          :class="{ 'is-focused': material.source_focused }"
          role="listitem"
          :aria-current="material.source_focused ? 'true' : undefined"
          :tabindex="material.source_focused ? -1 : undefined"
        >
          <div class="inbox-item-main">
            <div class="inbox-item-heading">
              <h3>{{ displayFilename(material) }}</h3>
              <span class="file-type">{{ displayFileType(material) }}</span>
            </div>
            <dl class="material-meta">
              <div>
                <dt>课程</dt>
                <dd>{{ displayCourse(material) }}</dd>
              </div>
              <div>
                <dt>类型</dt>
                <dd>{{ displayMaterialType(material) }}</dd>
              </div>
            </dl>
            <p v-if="firstSnippet(material)" class="material-snippet">{{ firstSnippet(material) }}</p>
          </div>

          <div class="inbox-item-side">
            <div class="status-list" :aria-label="`${displayFilename(material)} 的资料状态`">
              <span class="status-chip" :class="`is-${processingTone(material.processing_status)}`">处理：{{ processingLabel(material.processing_status) }}</span>
              <span class="status-chip" :class="`is-${extractionTone(material.extraction_status)}`">识别：{{ extractionLabel(material.extraction_status) }}</span>
            </div>
            <div class="item-actions" role="group" :aria-label="`${displayFilename(material)} 的操作`">
              <button
                type="button"
                class="inbox-button is-primary"
                :disabled="isBusy(material)"
                :aria-label="`${primaryAction(material).label}：${displayFilename(material)}`"
                @click="runPrimaryAction(material)"
              >
                {{ isBusy(material) ? '正在处理…' : primaryAction(material).label }}
              </button>
              <button
                v-if="primaryAction(material).kind !== 'detail'"
                type="button"
                class="inbox-button is-detail"
                :disabled="isBusy(material)"
                :aria-label="`查看资料详情：${displayFilename(material)}`"
                @click="emit('detail-material', material)"
              >
                查看详情
              </button>
            </div>
          </div>
        </article>
      </div>

      <div v-else class="empty-inbox" role="status" aria-live="polite">
        <strong>{{ filteredEmpty ? '当前条件下没有需要处理的资料' : '添加第一份课程资料' }}</strong>
        <p>{{ filteredEmpty ? '可进入完整管理调整搜索或定位条件；页面不会把其他资料混入当前结果。' : '上传后会先完成资料处理，再把需要核对的截止任务候选放到这里。' }}</p>
        <button v-if="!filteredEmpty" type="button" class="inbox-button is-primary" @click="emit('upload-material')">上传资料</button>
      </div>

      <p v-if="hiddenCount" class="remaining-note" role="status">
        还有 {{ hiddenCount }} 份资料未在此处展开，可进入完整管理查看全部资料与操作记录。
      </p>
    </template>

    <footer class="inbox-footer">
      <button type="button" class="inbox-button is-manage" @click="emit('show-all')">进入完整管理</button>
    </footer>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  state: {
    type: String,
    default: 'loading',
  },
  materials: {
    type: Array,
    default: () => [],
  },
  maxItems: {
    type: Number,
    default: 6,
  },
  busyMaterialIds: {
    type: Array,
    default: () => [],
  },
  filteredEmpty: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'retry-material',
  'extract-material',
  'detail-material',
  'upload-material',
  'show-all',
  'retry-load',
])

const validStates = new Set(['pending', 'loading', 'ready', 'error', 'invalid'])
const processingLabels = Object.freeze({
  pending: '待处理',
  processing: '处理中',
  processed: '已处理',
  failed: '处理失败',
})
const extractionLabels = Object.freeze({
  not_started: '未识别',
  ready: '待确认',
  needs_review: '待确认',
  confirmed: '已确认',
  failed: '识别失败',
})

const viewState = computed(() => (validStates.has(props.state) ? props.state : 'invalid'))
const safeMaxItems = computed(() => {
  const value = Number(props.maxItems)
  return Number.isFinite(value) && value >= 1 ? Math.min(6, Math.floor(value)) : 6
})
const busyIds = computed(() => new Set((Array.isArray(props.busyMaterialIds) ? props.busyMaterialIds : []).map((id) => String(id))))

function priorityOf(material) {
  if (material?.processing_status === 'failed') return 0
  if (material?.extraction_status === 'needs_review') return 1
  if (material?.extraction_status === 'ready') return 2
  if (material?.processing_status === 'processed' && material?.extraction_status === 'failed') return 3
  if (material?.processing_status === 'processed' && material?.extraction_status === 'not_started') return 4
  if (['pending', 'processing'].includes(material?.processing_status)) return 5
  if (material?.extraction_status === 'confirmed') return 6
  return 7
}

const prioritizedMaterials = computed(() => {
  if (viewState.value !== 'ready' || !Array.isArray(props.materials)) return []
  return props.materials
    .map((material, index) => ({ material, index }))
    .sort((left, right) => priorityOf(left.material) - priorityOf(right.material) || left.index - right.index)
    .map(({ material }) => material)
})
const visibleMaterials = computed(() => prioritizedMaterials.value.slice(0, safeMaxItems.value))
const hiddenCount = computed(() => Math.max(prioritizedMaterials.value.length - visibleMaterials.value.length, 0))

const stateLabel = computed(() => ({
  pending: '等待资料',
  loading: '正在读取',
  ready: '待处理列表',
  error: '暂时不可用',
  invalid: '状态待确认',
}[viewState.value]))
const stateTitle = computed(() => ({
  pending: '资料状态正在准备',
  loading: '正在读取资料状态',
  error: '资料状态暂时无法读取',
  invalid: '资料状态暂时无法确认',
}[viewState.value]))
const stateDescription = computed(() => ({
  pending: '正在等待资料状态，当前不会展示上一次的资料项目。',
  loading: '正在同步资料状态，当前不会用猜测数量或旧资料代替。',
  error: '当前不会展示旧资料或不准确的数量；你仍可上传资料，或进入完整管理后重试。',
  invalid: '收到的资料状态不完整，当前不会展示可能不准确的资料项目。',
}[viewState.value]))

function displayFilename(material) {
  return typeof material?.original_filename === 'string' && material.original_filename.trim()
    ? material.original_filename
    : '未命名资料'
}

function displayFileType(material) {
  return typeof material?.file_type === 'string' && material.file_type.trim() ? material.file_type : '未知格式'
}

function displayCourse(material) {
  return typeof material?.course_name === 'string' && material.course_name.trim() ? material.course_name : '未归类课程'
}

function displayMaterialType(material) {
  return typeof material?.material_type === 'string' && material.material_type.trim() ? material.material_type : '未分类'
}

function firstSnippet(material) {
  if (!Array.isArray(material?.match_snippets)) return ''
  return material.match_snippets.find((snippet) => typeof snippet === 'string' && snippet.trim()) || ''
}

function processingLabel(status) {
  return processingLabels[status] || '状态待确认'
}

function extractionLabel(status) {
  return extractionLabels[status] || '状态待确认'
}

function processingTone(status) {
  return ({ failed: 'failed', processing: 'working', processed: 'complete', pending: 'pending' })[status] || 'unknown'
}

function extractionTone(status) {
  return ({ needs_review: 'review', ready: 'ready', confirmed: 'complete', failed: 'failed', not_started: 'pending' })[status] || 'unknown'
}

function hasText(material) {
  return typeof material?.extracted_text === 'string' && material.extracted_text.trim().length > 0
}

function primaryAction(material) {
  if (material?.processing_status === 'failed') return { kind: 'retry', label: '重试解析' }
  if (material?.processing_status === 'processed' && hasText(material) && ['ready', 'needs_review'].includes(material?.extraction_status)) {
    return { kind: 'extract', label: '核对并创建任务' }
  }
   if (material?.extraction_status === 'confirmed') return { kind: 'extract', label: '查看已确认任务' }
  if (material?.processing_status === 'processed' && hasText(material)) {
     return { kind: 'extract', label: material?.extraction_status === 'failed' ? '重新识别截止任务' : '识别截止任务' }
  }
  if (['pending', 'processing'].includes(material?.processing_status)) return { kind: 'detail', label: '查看处理进度' }
  return { kind: 'detail', label: '查看资料详情' }
}

function isBusy(material) {
  return material?.id !== null && material?.id !== undefined && busyIds.value.has(String(material.id))
}

function runPrimaryAction(material) {
  if (isBusy(material)) return
  const action = primaryAction(material)
  if (action.kind === 'retry') emit('retry-material', material)
  else if (action.kind === 'extract') emit('extract-material', material)
  else emit('detail-material', material)
}
</script>

<style scoped>
.material-inbox-focus {
  --inbox-ink: var(--ledger-ink, #1e2a44);
  --inbox-paper: var(--ledger-paper, #ffffff);
  --inbox-canvas: var(--ledger-canvas, #f7f8fb);
  --inbox-line: var(--ledger-line, #d9e0ea);
  --inbox-muted: var(--ledger-muted, #667085);
  --inbox-indigo: var(--ledger-indigo, #327864);
  --inbox-amber: var(--ledger-amber, #c9822e);
  --inbox-coral: var(--ledger-coral, #c94c4c);
  min-width: 0;
  padding: 0;
  color: var(--inbox-ink);
}

.inbox-header,
.inbox-item-heading,
.inbox-item-side,
.status-list,
.item-actions,
.inbox-footer {
  display: flex;
  min-width: 0;
}

.inbox-header { align-items: flex-start; justify-content: space-between; gap: 14px; }
.inbox-heading { min-width: 0; }
.inbox-kicker { margin: 0; color: var(--inbox-indigo); font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif; font-size: 10px; font-weight: 750; letter-spacing: .12em; line-height: 1.4; }
.inbox-heading h2 { margin: 5px 0 0; color: var(--inbox-ink); font-size: 18px; line-height: 1.4; overflow-wrap: anywhere; }
.inbox-description { margin: 6px 0 0; color: var(--inbox-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.inbox-state-label { flex: 0 1 auto; max-width: 126px; padding: 4px 7px; color: #43516b; background: var(--inbox-canvas); border: 1px solid var(--inbox-line); border-radius: 4px; font-size: 12px; font-weight: 700; line-height: 1.4; overflow-wrap: anywhere; text-align: center; }
.inbox-state-label.is-loading, .inbox-state-label.is-pending { color: #80531d; border-color: #ead4ad; }
.inbox-state-label.is-error, .inbox-state-label.is-invalid { color: #9e3f3f; border-color: #e6c1c1; }
.inbox-notice, .empty-inbox { margin-top: 16px; padding: 14px; color: var(--inbox-muted); background: var(--inbox-canvas); border: 1px solid var(--inbox-line); border-left: 3px solid var(--inbox-amber); border-radius: 5px; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.inbox-notice.is-error, .inbox-notice.is-invalid { border-left-color: var(--inbox-coral); }
.inbox-notice strong, .empty-inbox strong { display: block; color: var(--inbox-ink); font-size: 14px; line-height: 1.45; }
.inbox-notice p, .empty-inbox p { margin: 4px 0 0; }
.inbox-notice .inbox-button { margin-top: 12px; }
.inbox-queue { display: grid; gap: 10px; min-width: 0; margin-top: 16px; }
.inbox-item { display: grid; grid-template-columns: minmax(0, 1fr) minmax(210px, .6fr); gap: 14px; min-width: 0; padding: 16px; background: var(--inbox-paper); border: 0; border-bottom: 1px solid var(--inbox-line); border-left: 3px solid #c8ddd1; border-radius: 0 8px 8px 0; }
.inbox-item.is-focused { background: #f1f7f3; border-color: color-mix(in srgb, var(--ledger-indigo) 55%, transparent); box-shadow: inset 3px 0 0 var(--inbox-indigo); }
.inbox-item-main { min-width: 0; }
.inbox-item-heading { align-items: flex-start; flex-wrap: wrap; gap: 8px; }
.inbox-item-heading h3 { flex: 1 1 160px; min-width: 0; margin: 0; color: #2e3b54; font-size: 14px; font-weight: 700; line-height: 1.5; overflow-wrap: anywhere; word-break: break-word; }
.file-type { flex: 0 1 auto; max-width: 100%; padding: 3px 6px; color: var(--inbox-muted); background: #f3f6fa; border: 1px solid #e1e6ed; border-radius: 3px; font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }
.material-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 14px; min-width: 0; margin: 9px 0 0; }
.material-meta div { min-width: 0; }
.material-meta dt { color: var(--inbox-muted); font-size: 12px; line-height: 1.4; }
.material-meta dd { min-width: 0; margin: 2px 0 0; color: var(--inbox-ink); font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; word-break: break-word; }
.material-snippet { margin: 9px 0 0; padding-left: 8px; color: #52617a; border-left: 2px solid #c8ddd1; font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; word-break: break-word; }
.inbox-item-side { flex-direction: column; align-items: stretch; justify-content: space-between; gap: 12px; min-width: 0; }
.status-list { flex-wrap: wrap; align-items: flex-start; gap: 6px; }
.status-chip { max-width: 100%; padding: 4px 7px; color: #43516b; border: 1px solid var(--inbox-line); border-radius: 4px; font-size: 12px; font-weight: 650; line-height: 1.4; overflow-wrap: anywhere; }
.status-chip.is-working, .status-chip.is-review { color: #80531d; border-color: #e4c48f; }
.status-chip.is-ready { color: var(--ledger-link); border-color: #c8ddd1; }
.status-chip.is-complete { color: #356052; border-color: #b9d8c5; }
.status-chip.is-failed { color: #9e3f3f; border-color: #e6c1c1; }
.item-actions { flex-wrap: wrap; gap: 8px; }
.inbox-button { display: inline-flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; max-width: 100%; padding: 8px 12px; color: #43516b; background: var(--inbox-paper); border: 1px solid var(--inbox-line); border-radius: 4px; font: inherit; font-size: 13px; font-weight: 700; line-height: 1.4; overflow-wrap: anywhere; text-align: center; cursor: pointer; }
.inbox-button.is-primary { flex: 1 1 132px; color: var(--inbox-paper); background: var(--inbox-indigo); border-color: var(--inbox-indigo); }
.inbox-button.is-detail { flex: 1 1 96px; }
.inbox-button.is-manage { flex: 1 1 146px; color: var(--inbox-ink); border-color: #9faabc; }
.inbox-button:hover:not(:disabled) { color: var(--inbox-indigo); border-color: var(--inbox-indigo); }
.inbox-button.is-primary:hover:not(:disabled) { color: var(--inbox-paper); background: var(--ledger-link); border-color: var(--ledger-link); }
.inbox-button:disabled { color: #8490a3; background: #f2f4f7; border-color: #dce1e8; cursor: wait; }
.inbox-button:focus-visible { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 42%, transparent); outline-offset: 3px; }
.empty-inbox .inbox-button { margin-top: 12px; }
.remaining-note { margin: 12px 0 0; padding: 10px 12px; color: #52617a; background: #f1f7f3; border-left: 3px solid var(--inbox-indigo); font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
.inbox-footer { flex-wrap: wrap; gap: 8px; min-width: 0; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--inbox-line); }

@media (max-width: 680px) {
  .material-inbox-focus { padding: 0; }
  .inbox-header { flex-direction: column; gap: 8px; }
  .inbox-state-label { align-self: flex-start; }
  .inbox-item { grid-template-columns: minmax(0, 1fr); }
  .material-meta { grid-template-columns: minmax(0, 1fr); }
  .item-actions, .inbox-footer { flex-direction: column; }
  .inbox-button, .inbox-button.is-primary, .inbox-button.is-detail, .inbox-button.is-manage { flex-basis: auto; width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .inbox-button { transition: none; }
}
</style>
