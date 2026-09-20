<template>
  <section class="today-focus-stage" :class="{ 'has-attention': state === 'ready' && attentionItems.length }" aria-labelledby="today-focus-stage-title">
    <header class="stage-heading">
      <div>
        <h2 id="today-focus-stage-title">{{ focus && state === 'ready' ? '先做这件事' : '今日安排' }}</h2>
      </div>
      <button
        type="button"
        class="details-link"
        :aria-label="`打开完整记录，查看 ${detailsCount} 项内容`"
        @click="$emit('open-details')"
      >
        完整学习记录
      </button>
    </header>

    <div v-if="state !== 'ready'" class="stage-state" :class="`stage-state--${state}`" role="status" aria-live="polite">
      <strong>{{ stateTitle }}</strong>
      <p>{{ stateDetail }}</p>
      <button v-if="state === 'error' || state === 'invalid'" type="button" class="secondary-action" @click="$emit('retry')">重试</button>
    </div>

    <template v-else>
      <article v-if="focus" class="focus-ticket" :class="`tone-${focus.tone || 'neutral'}`">
        <img class="study-moment" :src="studyMoment" alt="" width="600" height="411" decoding="async" />
        <div class="ticket-stamp">
          <span v-if="focus.badge" class="ticket-badge">{{ focus.badge }}</span>
        </div>
        <div class="ticket-content">
          <h3>{{ focus.title }}</h3>
          <p v-if="focus.meta" class="ticket-meta">{{ focus.meta }}</p>
          <details v-if="focus.detail" class="ticket-context">
            <summary>为什么先做这件事</summary>
            <p class="ticket-detail">{{ focus.detail }}</p>
          </details>
        </div>
        <div class="ticket-actions">
          <button
            type="button"
            class="primary-action"
            :disabled="focus.actionDisabled || focus.actionLoading"
            :aria-busy="Boolean(focus.actionLoading)"
            @click="$emit('act-focus')"
          >
            {{ focus.actionLoading ? '正在处理…' : focus.actionLabel }}
          </button>
          <button v-if="focus.canComplete" type="button" class="secondary-action" :disabled="focus.completing" :aria-busy="Boolean(focus.completing)" @click="$emit('complete-focus')">
            {{ focus.completing ? '正在完成…' : '已完成' }}
          </button>
        </div>
      </article>

      <div v-else class="focus-empty" role="status">
        <img class="empty-study-moment" :src="studyMoment" alt="" width="600" height="411" decoding="async" />
        <strong>暂时没有需要优先处理的事</strong>
        <p>可以记下一项作业或复习任务。</p>
        <div class="empty-actions">
          <button type="button" class="secondary-action" @click="$emit('create-task')">记下一项任务</button>
          <button type="button" class="details-link" @click="$emit('open-tasks')">查看任务清单</button>
        </div>
      </div>

      <section v-if="attentionItems.length" class="attention-section" aria-labelledby="attention-title">
        <div class="section-heading">
          <h3 id="attention-title">还需要确认</h3>
        </div>
        <ul class="attention-list">
          <li v-for="item in attentionItems" :key="item.id" class="attention-item" :class="`tone-${item.tone || 'neutral'}`">
            <div class="attention-copy">
              <div class="attention-title-row">
                <strong>{{ item.title }}</strong>
                <span v-if="item.badge" class="attention-badge">{{ item.badge }}</span>
              </div>
              <details v-if="item.detail" class="attention-context"><summary>查看说明</summary><p>{{ item.detail }}</p></details>
            </div>
            <button
              type="button"
              class="secondary-action attention-action"
              :disabled="item.actionDisabled"
              @click="$emit('act-attention', item)"
            >
              {{ item.actionLabel }}
            </button>
          </li>
        </ul>
      </section>

      <dl v-if="summaryItems.length" class="summary-list" aria-label="今日摘要">
        <div v-for="item in summaryItems" :key="item.label" class="summary-item" :class="`summary-item--${item.state || 'default'}`">
          <dt>{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </div>
      </dl>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import studyMoment from '../assets/study-moment.webp'

const props = defineProps({
  state: { type: String, default: 'loading' },
  focus: { type: Object, default: null },
  attentionItems: { type: Array, default: () => [] },
  summaryItems: { type: Array, default: () => [] },
  detailsCount: { type: Number, default: 0 },
})

defineEmits(['retry', 'act-focus', 'complete-focus', 'act-attention', 'open-details', 'create-task', 'open-tasks'])

const stateTitle = computed(() => ({
  loading: '正在整理今天的学习安排',
  error: '暂时无法读取今天的安排',
  invalid: '今天的学习信息还不完整',
}[props.state] || '今天的学习信息还不完整'))

const stateDetail = computed(() => ({
  loading: '正在等待任务、提醒和风险信息。',
  error: '请重试后再安排下一步，避免按过期信息行动。',
  invalid: '等学习信息更新完整后，这里再给出下一步。',
}[props.state] || '等学习信息更新完整后，这里再给出下一步。'))
</script>

<style scoped>
.ticket-actions { display: flex; grid-column: 1; align-items: center; flex-wrap: wrap; clear: both; gap: 10px; margin-top: 12px; }
.ticket-actions .primary-action { margin: 0; }
.today-focus-stage { min-width: 0; margin: 0 0 24px; padding: 20px 28px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 10px; border-top: 3px solid var(--ledger-primary); box-shadow: 0 5px 20px -16px #182e2933; }
.stage-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.stage-heading h2 { margin: 0; font-size: 16px; font-weight: 700; line-height: 1.5; }
.details-link { min-height: 44px; flex: 0 0 auto; padding: 0 4px; color: var(--ledger-muted); background: transparent; border: 0; font: inherit; font-size: 13px; cursor: pointer; }
.details-link:hover { color: var(--ledger-indigo); text-decoration: underline; text-underline-offset: 3px; }
.stage-state, .focus-empty { display: grid; gap: 7px; margin-top: 18px; padding: 16px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 6px; }
.stage-state strong, .focus-empty strong { font-size: 14px; }
.empty-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.stage-state p, .focus-empty p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.65; }
.stage-state--error, .stage-state--invalid { border-color: #dfc7c2; }
.stage-state .secondary-action { justify-self: start; }
.focus-ticket { display: grid; position: relative; grid-template-columns: minmax(0, 1fr) 180px; column-gap: 24px; min-width: 0; padding: 12px 0 4px; }
.study-moment { grid-column: 2; grid-row: 1 / span 2; align-self: center; width: 100%; height: auto; }
.empty-study-moment { width: 150px; height: auto; justify-self: center; }
.focus-empty { text-align: center; background: transparent; border: 0; }
.focus-empty .empty-actions { justify-content: center; }
.ticket-context { grid-column: 1; margin-top: 6px; }
.ticket-context summary, .attention-context summary { width: fit-content; min-height: 32px; padding: 6px 0; color: var(--ledger-muted); font-size: 12px; cursor: pointer; }
.ticket-context[open] summary, .attention-context[open] summary { color: var(--ledger-link); }
.attention-item.tone-amber { border-left-color: var(--ledger-amber); }
.attention-item.tone-coral { border-left-color: var(--ledger-coral); }
.ticket-stamp { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; color: var(--ledger-muted); font-size: 13px; line-height: 1.5; }
.ticket-badge, .attention-badge { display: inline-flex; max-width: 100%; padding: 3px 7px; color: var(--ledger-link); background: #f0f6f2; border-radius: 4px; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.tone-amber .ticket-badge, .tone-amber .attention-badge { color: #805d22; background: #faf4e8; }
.tone-coral .ticket-badge, .tone-coral .attention-badge { color: #a24a42; background: #fcf0ee; }
.ticket-content { display: grid; grid-column: 1; align-content: center; min-width: 0; padding: 10px 0 12px; }
.ticket-content h3 { grid-column: 1; margin: 0; overflow-wrap: anywhere; font-family: var(--font-display); font-size: 28px; font-weight: 700; line-height: 1.45; letter-spacing: -.025em; }
.ticket-detail { grid-column: 1; max-width: 65ch; margin: 10px 0 0; color: var(--ledger-muted); font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.ticket-meta { grid-column: 1; margin: 8px 0 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.primary-action, .secondary-action { min-height: 44px; padding: 10px 18px; border-radius: 6px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.primary-action { grid-column: 1; justify-self: start; margin-top: 12px; max-width: 200px; color: #fff; background: var(--ledger-indigo); border: 1px solid var(--ledger-indigo); }
.primary-action:hover:not(:disabled) { background: var(--ledger-link); border-color: var(--ledger-link); }
.secondary-action { color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); }
.secondary-action:hover:not(:disabled) { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.primary-action:disabled, .secondary-action:disabled { color: var(--ledger-muted); background: #eef1f5; border-color: #dfe4eb; cursor: not-allowed; }
.attention-section { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--ledger-line); }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.section-heading h3 { margin: 0; font-size: 14px; }
.section-heading span { color: var(--ledger-muted); font-size: 12px; }
.attention-list { display: grid; margin: 8px 0 0; padding: 0; list-style: none; }
.attention-item { display: flex; align-items: center; justify-content: space-between; gap: 14px; min-width: 0; padding: 10px 0; }
.attention-copy { min-width: 0; }
.attention-title-row { display: flex; align-items: baseline; flex-wrap: wrap; gap: 7px; }
.attention-title-row strong { overflow-wrap: anywhere; font-size: 13px; line-height: 1.45; }
.attention-copy p { margin: 5px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.attention-action { flex: 0 0 auto; border-color: transparent; background: transparent; color: var(--ledger-link); }
.summary-list { display: flex; flex-wrap: wrap; gap: 12px 26px; margin: 20px 0 0; padding: 16px 0 0; border-top: 1px solid var(--ledger-line); }
.summary-item { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px; min-width: 0; }
.summary-item--warning dd { color: #805d22; }
.summary-item--danger dd { color: #a24a42; }
.summary-item--success dd { color: var(--ledger-link); }
.summary-item dt { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.summary-item dd { margin: 0; overflow-wrap: anywhere; font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.5; }
.details-link:focus-visible, .primary-action:focus-visible, .secondary-action:focus-visible { outline: 3px solid rgba(50, 120, 100, .35); outline-offset: 3px; }
@media (min-width: 1100px) {
  .today-focus-stage.has-attention { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr); column-gap: 26px; }
  .has-attention .stage-heading, .has-attention .summary-list { grid-column: 1 / -1; }
  .has-attention .focus-ticket, .has-attention .focus-empty { grid-column: 1; }
  .has-attention .focus-ticket { grid-template-columns: minmax(0, 1fr) 120px; gap: 12px; }
  .has-attention .attention-section { grid-column: 2; grid-row: 2; align-self: center; margin-top: 12px; padding: 0 0 0 24px; border-top: 0; border-left: 1px solid var(--ledger-line); }
  .has-attention .attention-list { margin-top: 4px; }
  .has-attention .attention-item { padding: 8px 0; }
  .has-attention .summary-list { margin-top: 12px; }
}
@media (max-width: 720px) { .focus-ticket { grid-template-columns: minmax(0, 1fr) 130px; gap: 12px; } .ticket-content { grid-template-columns: minmax(0, 1fr); } .primary-action { grid-column: 1; grid-row: auto; justify-self: start; margin-top: 12px; max-width: none; } }
@media (max-width: 560px) { .today-focus-stage { padding: 16px; } .stage-heading { align-items: flex-start; } .details-link { padding-right: 0; text-align: right; } .focus-ticket { display: block; } .study-moment { float: right; width: 94px; margin: 8px 0 4px 12px; } .ticket-content { display: block; } .ticket-content h3 { font-size: 22px; } .summary-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } .attention-item { gap: 10px; } .attention-action { padding: 8px; } .primary-action { max-width: none; } }
@media (prefers-reduced-motion: reduce) { .today-focus-stage *, .today-focus-stage *::before, .today-focus-stage *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; } }
</style>
