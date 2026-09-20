<template>
  <section class="study-week-board" :aria-busy="loading">
    <header class="board-header">
      <div>
        <h2>{{ plan?.title || '近期复习行动板' }}</h2>
        <p class="board-subtitle">
           {{ delayedOnly ? '仅显示尚未完成的延期复习项。' : '从下一件要做的事开始，再按近期日程推进。' }}
        </p>
      </div>
      <dl v-if="plan" class="plan-facts" aria-label="计划信息">
        <div v-if="plan.exam_date"><dt>复习至</dt><dd>{{ formatDate(plan.exam_date) }}</dd></div>
        <div v-if="plan.daily_minutes"><dt>每日上限</dt><dd>{{ plan.daily_minutes }} 分钟</dd></div>
      </dl>
    </header>

    <div v-if="loading" class="board-loading" role="status" aria-live="polite">
      <span class="loading-rule" aria-hidden="true"></span>
      正在整理近期复习安排…
    </div>

    <template v-else>
      <section v-if="progressItems.length" class="progress-band" aria-label="计划完成进度">
        <div class="progress-copy"><span>已完成</span><strong>{{ completedCount }} / {{ progressItems.length }}</strong></div>
        <div class="progress-track" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100" :aria-label="`计划完成进度 ${progressPercent}%`">
          <span :style="{ width: `${progressPercent}%` }"></span>
        </div>
        <span class="progress-percent">{{ progressPercent }}%</span>
      </section>

       <div v-if="allCompleted && !delayedOnly && !focusedItemId" class="all-completed" role="status">
         计划中的 {{ progressItems.length }} 项复习均已完成，可在完整管理中回看或调整。
      </div>

      <div v-else-if="!displayItems.length" class="board-empty" role="status">
           {{ delayedOnly ? '没有待完成的延期复习项。' : '这份计划没有排入复习项。补充课程资料或调整任务后，请在完整管理中重新生成计划。' }}
      </div>

      <template v-else>
        <section v-if="nextAction" class="next-action" aria-labelledby="next-action-heading">
          <div class="section-heading">
            <p>下一步</p>
            <span>{{ dateKindLabel(nextAction) }}</span>
          </div>
          <article
            :ref="(element) => setItemRef(nextAction?.id, element)"
            class="next-card"
            :class="`is-${dateKind(nextAction)}`"
            :data-study-item-id="nextAction.id"
            :aria-current="nextAction.id === focusedItemId ? 'true' : undefined"
            :tabindex="nextAction.id === focusedItemId ? -1 : undefined"
          >
            <div class="next-copy">
              <h3 id="next-action-heading">{{ nextAction.title || '未命名复习项' }}</h3>
              <p class="item-meta">{{ formatDate(nextAction.date) }} <span v-if="nextAction.phase">· {{ nextAction.phase }}</span><span v-if="minutesLabel(nextAction)"> · {{ minutesLabel(nextAction) }}</span></p>
              <p v-if="nextAction.content" class="item-content">{{ nextAction.content }}</p>
            </div>
            <button
              type="button"
              class="complete-button"
              :disabled="saving"
              :aria-label="saving ? `正在保存“${nextAction.title || '未命名复习项'}”` : `标记“${nextAction.title || '未命名复习项'}”为已完成`"
              @click="emit('complete', nextAction)"
            >
              {{ saving ? '正在保存…' : '标为已完成' }}
            </button>
          </article>
        </section>

        <section v-if="scheduleItems.length" class="week-schedule" aria-labelledby="week-schedule-heading">
          <div class="section-heading schedule-heading">
            <p id="week-schedule-heading">{{ delayedOnly ? '延期项' : '近期日程' }}</p>
            <span>{{ scheduleItems.length }} 项</span>
          </div>
          <ol class="schedule-list">
            <li v-for="item in scheduleItems" :key="item.id" class="schedule-entry">
              <article
                :ref="(element) => setItemRef(item?.id, element)"
                class="schedule-card"
                :class="[`is-${dateKind(item)}`, { 'is-focused': item.id === focusedItemId, 'is-completed': item.status === 'completed' }]"
                :data-study-item-id="item.id"
                :aria-current="item.id === focusedItemId ? 'true' : undefined"
                :tabindex="item.id === focusedItemId ? -1 : undefined"
              >
                <div class="date-stamp"><span>{{ dayLabel(item.date) }}</span><strong>{{ shortDate(item.date) }}</strong></div>
                <div class="schedule-copy">
                  <div class="schedule-topline"><span>{{ dateKindLabel(item) }}</span><span v-if="item.phase">{{ item.phase }}</span></div>
                  <h3>{{ item.title || '未命名复习项' }}</h3>
                  <p v-if="item.content" class="item-content">{{ item.content }}</p>
                  <p class="item-meta"><span v-if="minutesLabel(item)">{{ minutesLabel(item) }}</span><span v-if="statusLabel(item.status)"> · {{ statusLabel(item.status) }}</span></p>
                </div>
                <button type="button" class="detail-button" :aria-label="`查看“${item.title || '未命名复习项'}”详情`" @click="emit('open-details', item)">查看详情</button>
              </article>
            </li>
          </ol>
        </section>

        <p v-if="hiddenCount" class="bounded-note">另有 {{ hiddenCount }} 项保留在完整管理中。</p>

      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  plan: { type: Object, default: null },
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  focusedItemId: { type: String, default: '' },
  delayedOnly: { type: Boolean, default: false },
})

const emit = defineEmits(['complete', 'open-details'])
const itemElements = ref({})
const today = localDateKey(new Date())

const progressItems = computed(() => Array.isArray(props.plan?.items) ? props.plan.items : props.items)
const completedCount = computed(() => progressItems.value.filter((item) => item?.status === 'completed').length)
const progressPercent = computed(() => progressItems.value.length ? Math.round((completedCount.value / progressItems.value.length) * 100) : 0)
const allCompleted = computed(() => progressItems.value.length > 0 && completedCount.value === progressItems.value.length)

const boardItems = computed(() => (Array.isArray(props.items) ? props.items : []).filter((item) => item?.id))
const eligibleItems = computed(() => {
  const filtered = props.delayedOnly
    ? boardItems.value.filter((item) => item.status !== 'completed' && dateKind(item) === 'overdue')
    : boardItems.value
  return [...filtered].sort(compareItems)
})

const nextAction = computed(() => {
  const pending = eligibleItems.value.filter((item) => item.status !== 'completed')
  return [...pending].sort(compareNextActions)[0] || null
})

const displayItems = computed(() => {
  const requiredIds = [nextAction.value?.id, props.focusedItemId].filter(Boolean)
  const selected = nextAction.value ? [nextAction.value] : []
  const nearbyPending = eligibleItems.value.filter((item) => (
    item.id !== nextAction.value?.id
    && item.status !== 'completed'
    && dateKind(item) !== 'later'
  ))
  for (const item of nearbyPending) {
    if (selected.length >= 7) break
    selected.push(item)
  }
  const focusedItem = eligibleItems.value.find((item) => item.id === props.focusedItemId)
  if (focusedItem && !selected.some((item) => item.id === focusedItem.id)) {
    const replaceIndex = findLastReplaceableIndex(selected, requiredIds)
    if (replaceIndex >= 0) selected.splice(replaceIndex, 1, focusedItem)
    else if (selected.length < 7) selected.push(focusedItem)
  }
  return selected.sort(compareItems)
})

const scheduleItems = computed(() => displayItems.value.filter((item) => item.id !== nextAction.value?.id))
const hiddenCount = computed(() => Math.max(0, eligibleItems.value.length - displayItems.value.length))

function localDateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  return Number.isNaN(date.getTime()) ? null : date
}

function dateKind(item) {
  const key = item?.date
  if (!parseDate(key)) return 'later'
  if (key < today) return 'overdue'
  if (key === today) return 'today'
  const oneWeekFromToday = parseDate(today)
  oneWeekFromToday.setDate(oneWeekFromToday.getDate() + 6)
  return key <= localDateKey(oneWeekFromToday) ? 'upcoming' : 'later'
}

function findLastReplaceableIndex(items, requiredIds) {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (!requiredIds.includes(items[index].id)) return index
  }
  return -1
}

function compareItems(left, right) {
  const leftDate = parseDate(left.date) ? left.date : '9999-12-31'
  const rightDate = parseDate(right.date) ? right.date : '9999-12-31'
  return leftDate.localeCompare(rightDate) || String(left.id).localeCompare(String(right.id))
}

function compareNextActions(left, right) {
  const rank = { overdue: 0, today: 1, upcoming: 2, later: 2 }
  return rank[dateKind(left)] - rank[dateKind(right)] || compareItems(left, right)
}

function dateKindLabel(item) {
  if (item?.status === 'completed') return '已完成'
  return { overdue: '已延期', today: '今天', upcoming: '7 天内', later: '稍后' }[dateKind(item)]
}

function statusLabel(status) {
  return { not_started: '未开始', in_progress: '进行中', completed: '已完成' }[status] || ''
}

function formatDate(value) {
  const date = parseDate(value)
  return date ? `${date.getMonth() + 1} 月 ${date.getDate()} 日` : '日期待定'
}

function shortDate(value) {
  const date = parseDate(value)
  return date ? `${date.getMonth() + 1}/${date.getDate()}` : '待定'
}

function dayLabel(value) {
  const date = parseDate(value)
  return date ? `周${'日一二三四五六'[date.getDay()]}` : '日期'
}

function minutesLabel(item) {
  return Number.isFinite(Number(item?.minutes)) && Number(item.minutes) > 0 ? `${item.minutes} 分钟` : ''
}

function setItemRef(id, element) {
  if (!id) return
  if (element) itemElements.value[id] = element
  else delete itemElements.value[id]
}

async function focusItem(id) {
  await nextTick()
  const element = itemElements.value[id]
  if (!element) return false
  const reduceMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  element.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center', inline: 'nearest' })
  element.focus({ preventScroll: true })
  return true
}

defineExpose({ focusItem })
</script>

<style scoped>
.study-week-board { min-width: 0; padding: 0; color: var(--ledger-ink); }
.board-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; min-width: 0; padding-bottom: 16px; border-bottom: 1px solid var(--ledger-line); }
.board-kicker, .section-heading p { margin: 0; color: var(--ledger-indigo); font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif; font-size: 10px; font-weight: 700; letter-spacing: .12em; line-height: 1.4; text-transform: uppercase; }
.board-header h2 { margin: 6px 0 0; color: var(--ledger-ink); font-family: "Aptos Display", "Microsoft YaHei", sans-serif; font-size: 20px; line-height: 1.3; overflow-wrap: anywhere; }
.board-subtitle { max-width: 58ch; margin: 7px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.plan-facts { display: flex; flex: 0 1 auto; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin: 0; }
.plan-facts div { min-width: 76px; padding: 8px 10px; background: #f1f7f3; border-left: 2px solid #c8ddd1; }
.plan-facts dt { color: var(--ledger-muted); font-size: 11px; line-height: 1.3; }
.plan-facts dd { margin: 3px 0 0; color: var(--ledger-ink); font-family: Bahnschrift, "Microsoft YaHei", sans-serif; font-size: 12px; font-weight: 700; line-height: 1.4; white-space: nowrap; }
.progress-band { display: grid; grid-template-columns: auto minmax(80px, 1fr) auto; align-items: center; gap: 10px; margin: 16px 0 0; padding: 11px 12px; background: #f1f7f3; border: 1px solid #e4e8ef; }
.progress-copy { display: flex; align-items: baseline; gap: 6px; color: var(--ledger-muted); font-size: 12px; }
.progress-copy strong, .progress-percent { color: var(--ledger-indigo); font-family: Bahnschrift, "Microsoft YaHei", sans-serif; font-size: 13px; }
.progress-track { height: 6px; overflow: hidden; background: #dfe4ed; border-radius: 2px; }
.progress-track span { display: block; height: 100%; background: var(--ledger-indigo); transition: width .2s ease; }
.board-loading, .board-empty, .all-completed { padding: 30px 4px 10px; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; text-align: center; }
.bounded-note { margin: 12px 0 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; text-align: right; }
.loading-rule { display: block; width: 92px; height: 2px; margin: 0 auto 12px; background: var(--ledger-indigo); animation: loading-slide 1.2s ease-in-out infinite; transform-origin: left; }
.next-action, .week-schedule { margin-top: 20px; }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 9px; }
.section-heading > span { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; }
.next-card { position: relative; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 15px; align-items: stretch; min-width: 0; padding: 15px; background: #f1f7f3; border: 1px solid #c8ddd1; border-left: 3px solid var(--ledger-indigo); }
.next-card.is-overdue { background: #fff5f4; border-color: #ebc5c3; border-left-color: var(--ledger-coral); }
.next-copy, .schedule-copy { min-width: 0; }
.next-copy h3, .schedule-copy h3 { margin: 0; color: var(--ledger-ink); font-size: 15px; line-height: 1.45; overflow-wrap: anywhere; }
.item-meta { margin: 5px 0 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.item-content { margin: 7px 0 0; color: #43516b; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; white-space: pre-wrap; }
.complete-button, .detail-button { min-height: 44px; border-radius: 4px; font: inherit; font-size: 13px; font-weight: 700; cursor: pointer; }
.complete-button { align-self: center; padding: 9px 15px; color: #ffffff; background: var(--ledger-indigo); border: 1px solid var(--ledger-indigo); }
.next-card.is-overdue .complete-button { background: var(--ledger-coral); border-color: var(--ledger-coral); }
.complete-button:disabled { cursor: wait; opacity: .65; }
.schedule-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.schedule-card { display: grid; grid-template-columns: 58px minmax(0, 1fr) auto; gap: 13px; align-items: center; min-width: 0; padding: 12px; background: #ffffff; border: 0; border-bottom: 1px solid var(--ledger-line); border-left: 3px solid #aeb8c8; scroll-margin-block: 18px; }
.schedule-card.is-overdue { border-left-color: var(--ledger-coral); }
.schedule-card.is-today { border-left-color: var(--ledger-indigo); background: #f1f7f3; }
.schedule-card.is-upcoming { border-left-color: var(--ledger-link); }
.schedule-card.is-focused { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 32%, transparent); outline-offset: 2px; }
.schedule-card.is-completed { opacity: .72; }
.schedule-card.is-completed h3 { text-decoration: line-through; }
.date-stamp { align-self: stretch; display: flex; flex-direction: column; justify-content: center; padding-right: 10px; border-right: 1px solid #e1e6ee; }
.date-stamp span, .schedule-topline { color: var(--ledger-muted); font-size: 11px; line-height: 1.4; }
.date-stamp strong { margin-top: 2px; color: var(--ledger-ink); font-family: Bahnschrift, "Microsoft YaHei", sans-serif; font-size: 14px; }
.schedule-topline { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.schedule-topline span:first-child { color: var(--ledger-indigo); font-weight: 700; }
.is-overdue .schedule-topline span:first-child { color: var(--ledger-coral); }
.detail-button { min-width: 76px; padding: 8px 10px; color: var(--ledger-link); background: transparent; border: 1px solid #cbd3df; }
.complete-button:hover:not(:disabled), .detail-button:hover { filter: brightness(.96); }
.complete-button:focus-visible, .detail-button:focus-visible { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 42%, transparent); outline-offset: 3px; }
@keyframes loading-slide { 50% { transform: scaleX(.45); opacity: .55; } }
@media (max-width: 560px) { .study-week-board { padding: 0; } .board-header { flex-direction: column; } .plan-facts { justify-content: flex-start; } .next-card { grid-template-columns: minmax(0, 1fr); gap: 12px; } .complete-button { grid-column: 1; width: 100%; } .schedule-card { grid-template-columns: 52px minmax(0, 1fr); gap: 10px; } .detail-button { grid-column: 2; width: 100%; } .progress-band { grid-template-columns: auto minmax(0, 1fr); } .progress-percent { grid-column: 2; text-align: right; } }
@media (max-height: 480px) and (orientation: landscape) { .study-week-board { padding: 0; } .board-header { padding-bottom: 11px; } .next-action, .week-schedule { margin-top: 14px; } }
@media (prefers-reduced-motion: reduce) { .progress-track span, .loading-rule { transition: none; animation: none; } }
</style>
