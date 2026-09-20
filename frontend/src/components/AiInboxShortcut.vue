<template>
  <section class="inbox-shortcut" aria-labelledby="inbox-shortcut-title">
    <header class="inbox-heading">
      <h2 id="inbox-shortcut-title">课程通知，随手收好</h2>
      <span class="inbox-status" :class="`is-${viewState}`">{{ statusLabel }}</span>
    </header>
    <p class="inbox-lede">提取作业与截止，核对后保存。</p>

    <div class="inbox-actions">
      <button type="button" class="inbox-action" @click="emit('paste-notice')"><el-icon aria-hidden="true"><Document /></el-icon>粘贴通知</button>
      <button type="button" class="inbox-action" aria-label="上传文件或截图并开始识别" @click="emit('upload')"><el-icon aria-hidden="true"><Upload /></el-icon>上传资料</button>
    </div>

    <div v-if="viewState !== 'ready'" class="inbox-state" :class="`is-${viewState}`" role="status" aria-live="polite">
      <strong>{{ stateTitle }}</strong>
      <p>{{ stateDetail }}</p>
    </div>
    <template v-else>
      <dl v-if="countsKnown && totalCount > 0" class="inbox-metrics" aria-label="资料处理状态">
        <div><dt>已识别</dt><dd>{{ counts.ready }}</dd></div>
        <div class="is-review"><dt>待核对</dt><dd>{{ counts.review }}</dd></div>
        <div class="is-failed"><dt>处理失败</dt><dd>{{ counts.failed }}</dd></div>
      </dl>
      <p v-if="!countsKnown" class="inbox-empty" role="status">资料数量暂未同步，请进入收件箱查看。</p>
    </template>
    <button type="button" class="inbox-review-link" :aria-label="reviewActionLabel" @click="emit('open-inbox')">打开资料收件箱</button>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Document, Upload } from '@element-plus/icons-vue'

const props = defineProps({
  state: {
    type: String,
    default: 'loading',
    validator: (value) => ['loading', 'ready', 'error'].includes(value),
  },
  readyCount: { type: Number, default: null },
  reviewCount: { type: Number, default: null },
  failedCount: { type: Number, default: null },
})
const emit = defineEmits(['upload', 'paste-notice', 'open-inbox'])
const viewState = computed(() => (['loading', 'ready', 'error'].includes(props.state) ? props.state : 'error'))
const validCount = (value) => (Number.isInteger(value) && value >= 0 ? value : null)
const counts = computed(() => ({
  ready: validCount(props.readyCount),
  review: validCount(props.reviewCount),
  failed: validCount(props.failedCount),
}))
const countsKnown = computed(() => Object.values(counts.value).every((value) => value !== null))
const totalCount = computed(() => (countsKnown.value ? Object.values(counts.value).reduce((sum, value) => sum + value, 0) : null))
const statusLabel = computed(() => {
  if (viewState.value === 'loading') return '正在同步'
  if (viewState.value === 'error') return '暂时不可用'
  if (!countsKnown.value) return '状态待同步'
  return totalCount.value ? `${totalCount.value} 项待处理` : '已整理好'
})
const stateTitle = computed(() => (viewState.value === 'loading' ? '正在读取资料状态' : '资料状态暂时无法读取'))
const stateDetail = computed(() => (viewState.value === 'loading' ? '稍等片刻，资料状态同步后会显示在这里。' : '可以继续添加资料，或进入资料收件箱重试。'))
const reviewActionLabel = computed(() => (totalCount.value === null ? '打开资料收件箱' : `打开资料收件箱，查看 ${totalCount.value} 项待处理资料`))
</script>

<style scoped>
.inbox-shortcut { display: flex; flex-direction: column; min-width: 0; padding: 24px; color: var(--ledger-ink); background: #f2f6f3; border: 1px solid #e0e9e3; border-radius: var(--ledger-radius); }
.inbox-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; min-width: 0; }
.inbox-heading h2 { min-width: 0; margin: 0; font-size: 16px; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; }
.inbox-status { flex: 0 0 auto; max-width: 105px; padding-top: 3px; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.inbox-status.is-loading { color: #805d22; }
.inbox-status.is-error { color: #a24a42; }
.inbox-lede { margin: 12px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; }
.inbox-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.inbox-action { display: inline-flex; flex: 1 1 100px; align-items: center; justify-content: center; gap: 8px; min-width: 0; min-height: 44px; padding: 10px; color: var(--ledger-link); background: var(--ledger-paper); border: 1px solid #ceded3; border-radius: 8px; font: inherit; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; cursor: pointer; }
.inbox-action:hover { border-color: var(--ledger-indigo); }
.inbox-state, .inbox-empty { margin: 18px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.inbox-state { padding: 8px 0 8px 12px; border-left: 2px solid var(--ledger-amber); }
.inbox-state.is-error { border-left-color: var(--ledger-coral); }
.inbox-state strong { display: block; color: var(--ledger-ink); font-size: 13px; line-height: 1.5; }
.inbox-state p { margin: 3px 0 0; }
.inbox-metrics { display: flex; flex-wrap: wrap; gap: 8px 16px; min-width: 0; margin: 18px 0 0; padding: 0; }
.inbox-metrics > div { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
.inbox-metrics > .is-review dd { color: #805d22; }
.inbox-metrics > .is-failed dd { color: #a24a42; }
.inbox-metrics dt { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.inbox-metrics dd { margin: 0; font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.5; }
.inbox-review-link { align-self: flex-start; min-height: 44px; margin-top: 8px; padding: 8px 0; color: var(--ledger-link); border: 0; background: transparent; font: inherit; font-size: 13px; cursor: pointer; }
.inbox-review-link:hover { text-decoration: underline; text-underline-offset: 4px; }
.inbox-action:focus-visible, .inbox-review-link:focus-visible { outline: 3px solid rgba(50, 120, 100, .35); outline-offset: 3px; }
@media (max-width: 560px) { .inbox-shortcut { padding: 18px; } .inbox-actions { flex-direction: column; } .inbox-action { flex-basis: auto; width: 100%; } }
</style>
