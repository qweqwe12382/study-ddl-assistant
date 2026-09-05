<template>
  <section class="today-focus-stage" aria-labelledby="today-focus-stage-title">
    <header class="stage-heading">
      <div>
        <p class="stage-kicker">TODAY / FOCUS</p>
        <h2 id="today-focus-stage-title">今天先做什么</h2>
      </div>
      <button
        type="button"
        class="details-link"
        :aria-label="`打开完整记录，查看 ${detailsCount} 项内容`"
        @click="$emit('open-details')"
      >
        查看完整记录
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
          <span>{{ focus.kicker || '当前行动' }}</span>
          <span v-if="focus.badge" class="ticket-badge">{{ focus.badge }}</span>
        </div>
        <div class="ticket-content">
          <p class="ticket-kind">{{ focus.kind }}</p>
          <h3>{{ focus.title }}</h3>
          <p v-if="focus.detail" class="ticket-detail">{{ focus.detail }}</p>
          <p v-if="focus.meta" class="ticket-meta">{{ focus.meta }}</p>
          <ol class="agent-thread" aria-label="从信息到行动的处理过程">
            <li>
              <span>事实</span>
              <strong>已记录数据</strong>
            </li>
            <li>
              <span>判断</span>
              <strong>当前一步</strong>
            </li>
            <li>
              <span>行动</span>
              <strong>由你触发</strong>
            </li>
          </ol>
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
        <strong>今天暂时没有最需要处理的事。</strong>
         <p>先记下课程、资料和任务；有需要处理的安排时，会显示在这里。</p>
      </div>

      <section v-if="attentionItems.length" class="attention-section" aria-labelledby="attention-title">
        <div class="section-heading">
          <h3 id="attention-title">还需要确认</h3>
          <span>请逐项处理</span>
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

defineEmits(['retry', 'act-focus', 'act-attention', 'open-details'])

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
.today-focus-stage { min-width: 0; margin: 0 0 18px; padding: 20px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 8px; box-shadow: var(--ledger-shadow); }
.stage-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.stage-kicker { margin: 0; color: var(--ledger-indigo); font-size: 10px; font-weight: 750; letter-spacing: .14em; }
.stage-heading h2 { margin: 6px 0 0; font-size: 19px; line-height: 1.35; }
.details-link { min-height: 44px; flex: 0 0 auto; padding: 0 10px; color: #43516b; background: transparent; border: 0; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.details-link:hover { color: var(--ledger-indigo); text-decoration: underline; text-underline-offset: 3px; }
.stage-state, .focus-empty { display: grid; gap: 7px; margin-top: 18px; padding: 16px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 6px; }
.stage-state strong, .focus-empty strong { font-size: 14px; }
.stage-state p, .focus-empty p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.65; }
.stage-state--error, .stage-state--invalid { border-left: 3px solid var(--ledger-coral); }
.stage-state--invalid { border-left-color: var(--ledger-amber); }
.focus-ticket { display: grid; grid-template-columns: 112px minmax(0, 1fr); min-width: 0; margin-top: 18px; border: 1px solid var(--ledger-line); border-left: 4px solid var(--ledger-indigo); border-radius: 6px; overflow: hidden; }
.focus-ticket.tone-amber, .attention-item.tone-amber { border-left-color: var(--ledger-amber); }
.focus-ticket.tone-coral, .attention-item.tone-coral { border-left-color: var(--ledger-coral); }
.ticket-stamp { display: flex; align-items: flex-start; flex-direction: column; justify-content: space-between; gap: 10px; padding: 14px 12px; color: #43516b; background: var(--ledger-canvas); border-right: 1px dashed var(--ledger-line); font-size: 10px; font-weight: 750; letter-spacing: .08em; line-height: 1.45; text-transform: uppercase; }
.ticket-badge, .attention-badge { display: inline-flex; max-width: 100%; padding: 3px 6px; color: #43516b; background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: 0; line-height: 1.5; overflow-wrap: anywhere; text-transform: none; }
.ticket-content { min-width: 0; padding: 16px; }
.ticket-kind { margin: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; }
.ticket-content h3 { margin: 5px 0 0; overflow-wrap: anywhere; font-size: 17px; line-height: 1.4; }
.ticket-detail { margin: 8px 0 0; color: #43516b; font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.ticket-meta { margin: 8px 0 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; }
.agent-thread { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); min-width: 0; margin: 15px 0 0; padding: 0; list-style: none; }
.agent-thread li { position: relative; display: grid; gap: 3px; min-width: 0; padding: 8px 14px 8px 0; border-top: 2px solid var(--ledger-line); }
.agent-thread li:not(:last-child)::after { content: ''; position: absolute; top: -2px; right: 0; width: 14px; border-top: 2px solid var(--ledger-indigo); }
.agent-thread li:first-child { border-top-color: var(--ledger-indigo); }
.agent-thread span { color: var(--ledger-muted); font-size: 12px; line-height: 1.45; }
.agent-thread strong { color: #43516b; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.primary-action, .secondary-action { min-height: 44px; padding: 0 14px; border-radius: 4px; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; }
.primary-action { margin-top: 15px; color: var(--ledger-paper); background: var(--ledger-indigo); border: 1px solid var(--ledger-indigo); }
.primary-action:hover:not(:disabled) { background: #4853cf; border-color: #4853cf; }
.secondary-action { color: #43516b; background: var(--ledger-paper); border: 1px solid var(--ledger-line); }
.secondary-action:hover:not(:disabled) { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.primary-action:disabled, .secondary-action:disabled { color: var(--ledger-muted); background: #eef1f5; border-color: #dfe4eb; cursor: not-allowed; }
.attention-section { margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--ledger-line); }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.section-heading h3 { margin: 0; font-size: 14px; }
.section-heading span { color: var(--ledger-muted); font-size: 12px; }
.attention-list { display: grid; gap: 8px; margin: 12px 0 0; padding: 0; list-style: none; }
.attention-item { display: flex; align-items: center; justify-content: space-between; gap: 14px; min-width: 0; padding: 12px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-left: 3px solid var(--ledger-indigo); border-radius: 5px; }
.attention-copy { min-width: 0; }
.attention-title-row { display: flex; align-items: baseline; flex-wrap: wrap; gap: 7px; }
.attention-title-row strong { overflow-wrap: anywhere; font-size: 13px; line-height: 1.45; }
.attention-copy p { margin: 5px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.attention-action { flex: 0 0 auto; }
.summary-list { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 20px 0 0; padding: 0; }
.summary-item { min-width: 0; padding: 10px 11px; background: var(--ledger-paper); border-top: 2px solid var(--ledger-line); }
.summary-item--warning { border-top-color: var(--ledger-amber); }
.summary-item--danger { border-top-color: var(--ledger-coral); }
.summary-item--success { border-top-color: #357862; }
.summary-item dt { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.summary-item dd { margin: 5px 0 0; overflow-wrap: anywhere; font-size: 15px; font-weight: 700; line-height: 1.35; }
.details-link:focus-visible, .primary-action:focus-visible, .secondary-action:focus-visible { outline: 3px solid rgba(89, 100, 237, .42); outline-offset: 3px; }
@media (max-width: 720px) { .summary-list { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .today-focus-stage { padding: 16px; } .stage-heading { align-items: flex-start; } .details-link { padding-right: 0; text-align: right; } .focus-ticket { grid-template-columns: minmax(0, 1fr); } .ticket-stamp { align-items: center; flex-direction: row; padding: 10px 12px; border-right: 0; border-bottom: 1px dashed var(--ledger-line); } .agent-thread li { padding-right: 8px; } .attention-item { align-items: stretch; flex-direction: column; } .attention-action, .primary-action, .secondary-action { width: 100%; } }
@media (prefers-reduced-motion: reduce) { .today-focus-stage *, .today-focus-stage *::before, .today-focus-stage *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; } }
</style>
