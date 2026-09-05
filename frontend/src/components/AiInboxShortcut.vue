<template>
  <section class="inbox-shortcut" aria-labelledby="inbox-shortcut-title">
    <header class="inbox-heading">
      <div>
        <p class="inbox-kicker">AI INBOX / 资料入口</p>
        <h2 id="inbox-shortcut-title">先收好资料，再由你确认</h2>
      </div>
      <span class="inbox-status" :class="`is-${viewState}`">{{ statusLabel }}</span>
    </header>

    <p class="inbox-lede">文件或截图上传后，系统会整理课程、标签和截止任务候选；确认前不会创建正式任务。</p>

    <div class="inbox-flow" aria-label="资料进入、智能识别、人工确认">
       <span>上传资料</span><i aria-hidden="true">→</i><span>智能识别</span><i aria-hidden="true">→</i><span>人工确认</span>
    </div>

    <div v-if="viewState !== 'ready'" class="inbox-state" :class="`is-${viewState}`" role="status" aria-live="polite">
      <strong>{{ stateTitle }}</strong>
      <p>{{ stateDetail }}</p>
    </div>

    <template v-else>
      <dl v-if="countsKnown" class="inbox-metrics" aria-label="资料处理状态">
        <div>
          <dt>可确认</dt>
          <dd>{{ counts.ready }}</dd>
        </div>
        <div class="is-review">
          <dt>待确认</dt>
          <dd>{{ counts.review }}</dd>
        </div>
        <div class="is-failed">
          <dt>处理失败</dt>
          <dd>{{ counts.failed }}</dd>
        </div>
      </dl>
       <p v-if="countsKnown && totalCount === 0" class="inbox-empty" role="status">这里还没有待处理资料，可以先添加一份课程资料。</p>
       <p v-else-if="!countsKnown" class="inbox-empty" role="status">状态数字尚未同步，页面不会用 0 代替。</p>
    </template>

    <div class="inbox-actions">
       <button type="button" class="inbox-action is-primary" aria-label="添加资料并开始智能识别" @click="emit('upload')">添加资料</button>
      <button type="button" class="inbox-action" :aria-label="reviewActionLabel" @click="emit('open-inbox')">
        查看待确认<span v-if="counts.review !== null" class="action-count">{{ counts.review }}</span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

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

const emit = defineEmits(['upload', 'open-inbox'])

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
  return totalCount.value ? `${totalCount.value} 项待处理` : '没有待处理资料'
})
const stateTitle = computed(() => (viewState.value === 'loading' ? '正在读取资料状态' : '资料状态暂时无法读取'))
const stateDetail = computed(() => (viewState.value === 'loading' ? '正在同步资料处理状态。' : '仍可添加资料或进入资料页重试，当前不会显示猜测数字。'))
const reviewActionLabel = computed(() => (counts.value.review === null ? '查看待确认资料' : `查看 ${counts.value.review} 项待确认资料`))
</script>

<style scoped>
.inbox-shortcut { min-width: 0; padding: 18px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-left: 3px solid var(--ledger-indigo); border-radius: 8px; box-shadow: var(--ledger-shadow); }
.inbox-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; min-width: 0; }
.inbox-heading > div { min-width: 0; }
.inbox-kicker { margin: 0; color: var(--ledger-indigo); font-size: 10px; font-weight: 750; letter-spacing: .12em; line-height: 1.4; }
.inbox-heading h2 { margin: 6px 0 0; font-size: 18px; line-height: 1.4; overflow-wrap: anywhere; }
.inbox-status { flex: 0 0 auto; max-width: 120px; padding: 4px 7px; color: #356052; background: #f3faf6; border: 1px solid #cfe5d7; border-radius: 999px; font-size: 12px; font-weight: 700; line-height: 1.4; overflow-wrap: anywhere; text-align: center; }
.inbox-status.is-loading { color: #80531d; background: #fff8ec; border-color: #ead4ad; }
.inbox-status.is-error { color: #9e3f3f; background: #fff4f4; border-color: #e6c1c1; }
.inbox-lede { margin: 9px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.inbox-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; margin-top: 14px; color: #43516b; font-size: 12px; font-weight: 700; line-height: 1.5; }
.inbox-flow span { min-width: 0; padding: 4px 6px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 3px; overflow-wrap: anywhere; }
.inbox-flow i { color: var(--ledger-indigo); font-style: normal; }
.inbox-state, .inbox-empty { margin: 14px 0 0; padding: 11px 12px; color: var(--ledger-muted); background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 5px; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.inbox-state { border-left: 3px solid var(--ledger-amber); }
.inbox-state.is-error { border-left-color: var(--ledger-coral); }
.inbox-state strong { display: block; color: var(--ledger-ink); font-size: 13px; line-height: 1.45; }
.inbox-state p { margin: 3px 0 0; }
.inbox-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; min-width: 0; margin: 14px 0 0; padding: 0; }
.inbox-metrics > div { min-width: 0; padding: 9px; border-top: 2px solid #357862; }
.inbox-metrics > .is-review { border-top-color: var(--ledger-amber); }
.inbox-metrics > .is-failed { border-top-color: var(--ledger-coral); }
.inbox-metrics dt { color: var(--ledger-muted); font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; }
.inbox-metrics dd { margin: 4px 0 0; font-size: 18px; font-weight: 700; line-height: 1.25; }
.inbox-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.inbox-action { display: inline-flex; flex: 1 1 120px; align-items: center; justify-content: center; gap: 6px; min-width: 0; min-height: 44px; padding: 8px 11px; color: #43516b; background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 4px; font: inherit; font-size: 12px; font-weight: 700; line-height: 1.4; overflow-wrap: anywhere; cursor: pointer; }
.inbox-action.is-primary { color: var(--ledger-paper); background: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.inbox-action:hover { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.inbox-action.is-primary:hover { color: var(--ledger-paper); background: #4853cf; border-color: #4853cf; }
.inbox-action:focus-visible { outline: 3px solid rgba(89, 100, 237, .42); outline-offset: 3px; }
.action-count { display: inline-grid; min-width: 22px; min-height: 22px; place-items: center; padding: 2px 5px; color: var(--ledger-indigo); background: #eef0ff; border-radius: 999px; font-size: 11px; line-height: 1.2; }
@media (max-width: 560px) { .inbox-shortcut { padding: 16px; } .inbox-heading { flex-direction: column; gap: 8px; } .inbox-status { align-self: flex-start; } .inbox-actions { flex-direction: column; } .inbox-action { flex-basis: auto; width: 100%; } }
@media (prefers-reduced-motion: reduce) { .inbox-action { transition: none; } }
</style>
