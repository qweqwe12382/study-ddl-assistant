<template>
  <section class="today-focus-stage" aria-labelledby="today-focus-stage-title">
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
        <div class="ticket-stamp">
          <span>{{ focus.kind || focus.kicker || '当前行动' }}</span>
          <span v-if="focus.kind && focus.kicker && focus.kind !== focus.kicker">{{ focus.kicker }}</span>
          <span v-if="focus.badge" class="ticket-badge">{{ focus.badge }}</span>
        </div>
        <div class="ticket-content">
          <h3>{{ focus.title }}</h3>
          <p v-if="focus.detail" class="ticket-detail">{{ focus.detail }}</p>
          <p v-if="focus.meta" class="ticket-meta">{{ focus.meta }}</p>
          <button
            type="button"
            class="primary-action"
            :disabled="focus.actionDisabled || focus.actionLoading"
            :aria-busy="Boolean(focus.actionLoading)"
            @click="$emit('act-focus')"
          >
            {{ focus.actionLoading ? '正在处理…' : focus.actionLabel }}
          </button>
        </div>
      </article>

      <div v-else class="focus-empty" role="status">
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
              <p v-if="item.detail">{{ item.detail }}</p>
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

const props = defineProps({
  state: { type: String, default: 'loading' },
  focus: { type: Object, default: null },
  attentionItems: { type: Array, default: () => [] },
  summaryItems: { type: Array, default: () => [] },
  detailsCount: { type: Number, default: 0 },
})

defineEmits(['retry', 'act-focus', 'act-attention', 'open-details', 'create-task', 'open-tasks'])

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
.today-focus-stage { min-width: 0; margin: 0 0 24px; padding: 24px 28px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-top: 3px solid var(--ledger-indigo); border-radius: var(--ledger-radius); box-shadow: none; }
.stage-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.stage-heading h2 { margin: 0; font-size: 16px; font-weight: 600; line-height: 1.5; }
.details-link { min-height: 44px; flex: 0 0 auto; padding: 0 4px; color: var(--ledger-muted); background: transparent; border: 0; font: inherit; font-size: 13px; cursor: pointer; }
.details-link:hover { color: var(--ledger-indigo); text-decoration: underline; text-underline-offset: 3px; }
.stage-state, .focus-empty { display: grid; gap: 7px; margin-top: 18px; padding: 16px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 6px; }
.stage-state strong, .focus-empty strong { font-size: 14px; }
.empty-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.stage-state p, .focus-empty p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.65; }
.stage-state--error, .stage-state--invalid { border-left: 3px solid var(--ledger-coral); }
.stage-state--invalid { border-left-color: var(--ledger-amber); }
.focus-ticket { display: grid; grid-template-columns: minmax(0, 1fr); min-width: 0; padding: 18px 0 4px; }
.attention-item.tone-amber { border-left-color: var(--ledger-amber); }
.attention-item.tone-coral { border-left-color: var(--ledger-coral); }
.ticket-stamp { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; color: var(--ledger-muted); font-size: 13px; line-height: 1.5; }
.ticket-badge, .attention-badge { display: inline-flex; max-width: 100%; padding: 3px 7px; color: var(--ledger-link); background: #f0f6f2; border-radius: 4px; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.tone-amber .ticket-badge, .tone-amber .attention-badge { color: #805d22; background: #faf4e8; }
.tone-coral .ticket-badge, .tone-coral .attention-badge { color: #a24a42; background: #fcf0ee; }
.ticket-content { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-content: center; column-gap: 28px; min-width: 0; padding: 10px 0 12px; }
.ticket-content h3 { grid-column: 1; margin: 0; overflow-wrap: anywhere; font-size: 25px; font-weight: 600; line-height: 1.5; }
.ticket-detail { grid-column: 1; max-width: 65ch; margin: 10px 0 0; color: var(--ledger-muted); font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.ticket-meta { grid-column: 1; margin: 8px 0 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.primary-action, .secondary-action { min-height: 44px; padding: 10px 16px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.primary-action { grid-column: 2; grid-row: 1 / span 3; align-self: center; max-width: 200px; color: #fff; background: var(--ledger-indigo); border: 1px solid var(--ledger-indigo); }
.primary-action:hover:not(:disabled) { background: var(--ledger-link); border-color: var(--ledger-link); }
.secondary-action { color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); }
.secondary-action:hover:not(:disabled) { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.primary-action:disabled, .secondary-action:disabled { color: var(--ledger-muted); background: #eef1f5; border-color: #dfe4eb; cursor: not-allowed; }
.attention-section { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--ledger-line); }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.section-heading h3 { margin: 0; font-size: 14px; }
.section-heading span { color: var(--ledger-muted); font-size: 12px; }
.attention-list { display: grid; margin: 8px 0 0; padding: 0; list-style: none; }
.attention-item { display: flex; align-items: center; justify-content: space-between; gap: 14px; min-width: 0; margin-top: 10px; padding: 4px 0 4px 12px; border-left: 2px solid var(--ledger-line); }
.attention-copy { min-width: 0; }
.attention-title-row { display: flex; align-items: baseline; flex-wrap: wrap; gap: 7px; }
.attention-title-row strong { overflow-wrap: anywhere; font-size: 13px; line-height: 1.45; }
.attention-copy p { margin: 5px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.attention-action { flex: 0 0 auto; }
.summary-list { display: flex; flex-wrap: wrap; gap: 12px 26px; margin: 20px 0 0; padding: 16px 0 0; border-top: 1px solid var(--ledger-line); }
.summary-item { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px; min-width: 0; }
.summary-item--warning dd { color: #805d22; }
.summary-item--danger dd { color: #a24a42; }
.summary-item--success dd { color: var(--ledger-link); }
.summary-item dt { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.summary-item dd { margin: 0; overflow-wrap: anywhere; font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.5; }
.details-link:focus-visible, .primary-action:focus-visible, .secondary-action:focus-visible { outline: 3px solid rgba(50, 120, 100, .35); outline-offset: 3px; }
@media (max-width: 720px) { .ticket-content { grid-template-columns: minmax(0, 1fr); } .primary-action { grid-column: 1; grid-row: auto; justify-self: start; margin-top: 18px; max-width: none; } }
@media (max-width: 560px) { .today-focus-stage { padding: 16px; } .stage-heading { align-items: flex-start; } .details-link { padding-right: 0; text-align: right; } .ticket-content h3 { font-size: 22px; } .summary-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } .attention-item { align-items: stretch; flex-direction: column; } .attention-action, .primary-action, .secondary-action { width: 100%; } }
@media (prefers-reduced-motion: reduce) { .today-focus-stage *, .today-focus-stage *::before, .today-focus-stage *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; } }
</style>
