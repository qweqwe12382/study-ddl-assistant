<template>
  <section class="deadline-flow" aria-labelledby="deadline-flow-title">
    <header class="deadline-flow__heading">
      <div>
        <p class="deadline-flow__kicker">DEADLINE FLOW / NEXT 7 DAYS</p>
        <h2 id="deadline-flow-title">未来 7 天的截止任务</h2>
        <p class="deadline-flow__lede">按截止时间排序；可以查看任务，并检查关联资料是否可用。</p>
      </div>
      <span v-if="viewState === 'ready'" class="deadline-flow__count">当前任务 · {{ visibleTasks.length }} 项</span>
    </header>

    <div
      v-if="viewState !== 'ready'"
      class="deadline-flow__state"
      :class="`deadline-flow__state--${viewState}`"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <strong>{{ stateTitle }}</strong>
      <p>{{ stateDetail }}</p>
    </div>

    <template v-else-if="visibleTasks.length">
      <ol class="deadline-flow__ruler" aria-label="从现在到未来七天的截止时间范围">
        <li class="deadline-flow__ruler-marker"><span>现在</span></li>
        <li class="deadline-flow__ruler-marker"><span>24 小时</span></li>
        <li class="deadline-flow__ruler-marker"><span>3 天</span></li>
        <li class="deadline-flow__ruler-marker"><span>7 天</span></li>
      </ol>

      <div class="deadline-flow__bands" aria-label="按截止时间分组的任务">
        <section
          v-for="band in activeBands"
          :key="band.id"
          class="deadline-flow__band"
          :class="`deadline-flow__band--${band.id}`"
          :aria-labelledby="`deadline-flow-band-${band.id}`"
        >
          <div class="deadline-flow__band-heading">
            <h3 :id="`deadline-flow-band-${band.id}`">{{ band.label }}</h3>
            <p>{{ band.range }}</p>
          </div>

          <ul class="deadline-flow__task-list">
            <li v-for="task in band.tasks" :key="task.key">
              <article class="deadline-flow__task" :aria-label="taskAriaLabel(task)">
                <span class="deadline-flow__course">课程：{{ task.courseName }}</span>
                <strong class="deadline-flow__task-name">{{ task.name }}</strong>
                <span class="deadline-flow__timing">
                  <time :datetime="task.dueIso">{{ task.dueLabel }}</time>
                  <span>{{ task.remainingLabel }}</span>
                </span>
                <span v-if="task.workloadLabel || task.priorityLabel || task.statusLabel" class="deadline-flow__meta">
                  <span v-if="task.workloadLabel" class="deadline-flow__metric deadline-flow__metric--workload">{{ task.workloadLabel }}</span>
                  <span v-if="task.priorityLabel" class="deadline-flow__metric">{{ task.priorityLabel }}</span>
                  <span v-if="task.statusLabel" class="deadline-flow__metric">状态：{{ task.statusLabel }}</span>
                </span>
                <div class="deadline-flow__source" :class="`deadline-flow__source--${task.sourceContext.state}`">
                  <div>
                    <span class="deadline-flow__source-title">{{ task.sourceContext.title }}</span>
                    <strong v-if="task.sourceContext.label">{{ task.sourceContext.label }}</strong>
                    <p>{{ task.sourceContext.detail }}</p>
                  </div>
                </div>
                <div class="deadline-flow__actions" role="group" :aria-label="`任务操作：${task.name}`">
                  <button
                    type="button"
                    class="deadline-flow__action deadline-flow__action--primary"
                    :aria-label="`查看任务：${task.name}`"
                    @click="emit('open-task', task.source)"
                  >
                    查看任务
                  </button>
                  <button
                    v-if="task.sourceContext.state === 'available'"
                    type="button"
                    class="deadline-flow__action"
                    :disabled="materialBusy(task)"
                    :aria-busy="materialBusy(task)"
                    :aria-label="`${materialBusy(task) ? '正在打开资料' : '打开资料'}：${task.sourceContext.label}`"
                    @click="emit('open-material', task.source)"
                  >
                    {{ materialBusy(task) ? '正在打开…' : '打开资料' }}
                  </button>
                </div>
              </article>
            </li>
          </ul>
        </section>
      </div>
    </template>

    <div v-else class="deadline-flow__state deadline-flow__state--empty" role="status" aria-live="polite">
      <strong>未来 7 天没有待处理的截止任务。</strong>
      <p>{{ emptyStateDetail }}</p>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { dashboardMaterialSourceContext, navigationSourceCacheKey } from '../utils/materialSourceNavigation'

const DAY = 24 * 60 * 60 * 1000
const WINDOW = 7 * DAY

const BAND_DEFINITIONS = [
  { id: 'within-day', label: '24 小时内', range: '现在 → 24 小时' },
  { id: 'within-three-days', label: '1–3 天', range: '24 小时 → 3 天' },
  { id: 'within-week', label: '3–7 天', range: '3 天 → 7 天' },
]

const props = defineProps({
  state: { type: String, default: 'loading' },
  tasks: { type: Array, default: () => [] },
  busyMaterialKeys: { type: Array, default: () => [] },
  now: { type: [Date, String, Number], default: null },
})

const emit = defineEmits(['open-task', 'open-material'])

const requestedState = computed(() => (
  ['loading', 'ready', 'error'].includes(props.state) ? props.state : 'invalid'
))

const referenceNow = computed(() => {
  if (props.now === null || props.now === undefined) return new Date()
  return parseDate(props.now)
})

const viewState = computed(() => {
  if (requestedState.value !== 'ready') return requestedState.value
  if (!Array.isArray(props.tasks) || !referenceNow.value) return 'invalid'
  return 'ready'
})

const normalizedTasks = computed(() => {
  if (viewState.value !== 'ready') return []

  const nowTime = referenceNow.value.getTime()
  return props.tasks
    .map((task, index) => normalizeTask(task, index, nowTime))
    .filter(Boolean)
    .sort((first, second) => (
      first.dueTime - second.dueTime
      || second.priorityValue - first.priorityValue
      || first.sourceIndex - second.sourceIndex
    ))
})

const visibleTasks = computed(() => normalizedTasks.value.slice(0, 5))

const bands = computed(() => BAND_DEFINITIONS.map((band) => ({
  ...band,
  tasks: visibleTasks.value.filter((task) => task.bandId === band.id),
})))
const activeBands = computed(() => bands.value.filter((band) => band.tasks.length))
const busyMaterialSet = computed(() => new Set(props.busyMaterialKeys.map((key) => String(key))))

const stateTitle = computed(() => ({
  loading: '正在读取未来 7 天的截止任务',
  error: '暂时无法读取截止任务',
  invalid: '截止任务信息不完整',
}[viewState.value] || '截止任务信息不完整'))

const stateDetail = computed(() => ({
  loading: '加载期间不会用旧数据、默认任务或推测的截止时间替代。',
  error: '请刷新后再确认安排；当前不会把未知数据当成正常任务。',
  invalid: '任务列表或参考时间不完整，暂时无法按时间归类这些内容。',
}[viewState.value] || '信息未确认前，不会显示为正常安排。'))

const emptyStateDetail = computed(() => {
  if (!props.tasks.length) return '当前没有未来 7 天内到期的任务。'
  return '未设置、已过期、截止时间无效或超过 7 天的任务不会出现在这里。'
})

function normalizeTask(source, sourceIndex, nowTime) {
  if (!source || typeof source !== 'object') return null

  const name = cleanText(source.name)
  const dueAt = parseDate(source.due_at)
  if (!name || !dueAt || source.status === 'completed') return null

  const dueTime = dueAt.getTime()
  const distance = dueTime - nowTime
  if (distance <= 0 || distance > WINDOW) return null

  const remainingMinutes = validMinutes(source.remaining_minutes)
  const estimatedMinutes = validMinutes(source.estimated_minutes)
  const priority = validPriority(source.priority)
  const courseName = cleanText(source.course_name) || '课程待补充'
  const sourceContext = dashboardMaterialSourceContext(source)

  return {
    source,
    sourceIndex,
    key: source.id ?? `${dueTime}-${name}-${sourceIndex}`,
    name,
    courseName,
    dueTime,
    dueIso: dueAt.toISOString(),
    dueLabel: `截止 ${formatDueAt(dueAt)}`,
    remainingLabel: formatRemainingTime(distance),
    workloadLabel: formatWorkload(remainingMinutes, estimatedMinutes),
    priorityLabel: priority === null ? null : `优先级 ${priority}`,
    priorityValue: priority ?? 0,
    statusLabel: formatStatus(source.status),
    sourceContext,
    bandId: bandIdFor(distance),
  }
}

function materialBusy(task) {
  const context = task?.sourceContext
  const key = navigationSourceCacheKey({
    source_type: 'material',
    source_id: context?.materialId,
    navigation_key: context?.navigationKey,
  })
  return Boolean(key && busyMaterialSet.value.has(key))
}

function parseDate(value) {
  if (value instanceof Date || typeof value === 'number') {
    const timestamp = new Date(value).getTime()
    return Number.isFinite(timestamp) ? new Date(timestamp) : null
  }

  if (typeof value !== 'string') return null
  const text = value.trim()
  const parts = /^(\d{4})-(\d{2})-(\d{2})(?:[Tt\s](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:[zZ]|[+-]\d{2}:?\d{2})?)?$/.exec(text)
  if (!parts) return null

  const year = Number(parts[1])
  const month = Number(parts[2])
  const day = Number(parts[3])
  const hour = parts[4] === undefined ? null : Number(parts[4])
  const minute = parts[5] === undefined ? null : Number(parts[5])
  const second = parts[6] === undefined ? null : Number(parts[6])
  const calendarDate = new Date(Date.UTC(year, month - 1, day))
  if (
    calendarDate.getUTCFullYear() !== year
    || calendarDate.getUTCMonth() !== month - 1
    || calendarDate.getUTCDate() !== day
    || (hour !== null && (hour > 23 || minute > 59 || (second !== null && second > 59)))
  ) return null

  const timestamp = new Date(text).getTime()
  return Number.isFinite(timestamp) ? new Date(timestamp) : null
}

function cleanText(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function validMinutes(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? Math.round(value) : null
}

function validPriority(value) {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= 5 ? value : null
}

function bandIdFor(distance) {
  if (distance <= DAY) return 'within-day'
  if (distance <= 3 * DAY) return 'within-three-days'
  return 'within-week'
}

function formatDueAt(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(value)
}

function formatRemainingTime(distance) {
  const minutes = Math.max(1, Math.ceil(distance / (60 * 1000)))
  const days = Math.floor(minutes / (24 * 60))
  const hours = Math.floor((minutes % (24 * 60)) / 60)

  if (days) return `还剩 ${days} 天${hours ? ` ${hours} 小时` : ''}`
  if (hours) return `还剩 ${hours} 小时${minutes % 60 ? ` ${minutes % 60} 分钟` : ''}`
  return `还剩 ${minutes} 分钟`
}

function formatWorkload(remainingMinutes, estimatedMinutes) {
  if (remainingMinutes !== null && estimatedMinutes !== null) {
    if (remainingMinutes === estimatedMinutes) return `工作量：${remainingMinutes} 分钟`
    return `工作量：还需 ${remainingMinutes} 分钟（预计 ${estimatedMinutes} 分钟）`
  }
  if (remainingMinutes !== null) return `工作量：还需 ${remainingMinutes} 分钟`
  if (estimatedMinutes !== null) return `工作量：预计 ${estimatedMinutes} 分钟`
  return null
}

function formatStatus(value) {
  const status = cleanText(value)
  if (!status) return null
  return {
    not_started: '未开始',
    in_progress: '进行中',
    completed: '已完成',
    overdue: '已逾期',
  }[status] || null
}

function taskAriaLabel(task) {
  return [
    `课程：${task.courseName}`,
    task.name,
    task.dueLabel,
    task.remainingLabel,
    task.workloadLabel,
    task.priorityLabel,
    task.statusLabel ? `状态：${task.statusLabel}` : null,
    task.sourceContext?.title,
    task.sourceContext?.label,
  ].filter(Boolean).join('，')
}
</script>

<style scoped>
.deadline-flow { min-width: 0; padding: 20px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 8px; box-shadow: var(--ledger-shadow); }
.deadline-flow__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; min-width: 0; }
.deadline-flow__heading > div { min-width: 0; }
.deadline-flow__kicker { margin: 0; color: var(--ledger-indigo); font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif; font-size: 10px; font-weight: 750; letter-spacing: .12em; line-height: 1.45; }
.deadline-flow__heading h2 { margin: 6px 0 0; color: var(--ledger-ink); font-size: 19px; line-height: 1.35; }
.deadline-flow__lede { margin: 6px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.deadline-flow__count { flex: 0 0 auto; min-height: 28px; padding: 5px 8px; color: #43516b; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 999px; font-size: 12px; font-weight: 650; line-height: 1.4; text-align: center; }
.deadline-flow__state { display: grid; gap: 7px; margin-top: 18px; padding: 16px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 6px; }
.deadline-flow__state strong { color: var(--ledger-ink); font-size: 14px; line-height: 1.5; }
.deadline-flow__state p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.deadline-flow__state--error { border-left: 3px solid var(--ledger-coral); }
.deadline-flow__state--invalid { border-left: 3px solid var(--ledger-amber); }
.deadline-flow__state--empty { border-left: 3px solid var(--ledger-indigo); }
.deadline-flow__ruler { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); min-width: 0; margin: 20px 0 12px; padding: 0; border-top: 1px solid var(--ledger-line); list-style: none; }
.deadline-flow__ruler-marker { position: relative; min-width: 0; padding-top: 10px; color: var(--ledger-muted); font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif; font-size: 11px; font-weight: 700; letter-spacing: .02em; line-height: 1.35; overflow-wrap: anywhere; }
.deadline-flow__ruler-marker::before { content: ''; position: absolute; top: -4px; left: 0; width: 7px; height: 7px; background: var(--ledger-paper); border: 2px solid var(--ledger-indigo); border-radius: 50%; }
.deadline-flow__ruler-marker:last-child { text-align: right; }
.deadline-flow__ruler-marker:last-child::before { right: 0; left: auto; }
.deadline-flow__bands { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; min-width: 0; }
.deadline-flow__band { min-width: 0; padding: 12px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-left: 3px solid var(--ledger-indigo); border-radius: 6px; }
.deadline-flow__band--within-day { border-left-color: var(--ledger-coral); }
.deadline-flow__band--within-three-days { border-left-color: var(--ledger-amber); }
.deadline-flow__band-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; }
.deadline-flow__band-heading h3 { min-width: 0; margin: 0; color: var(--ledger-ink); font-size: 14px; line-height: 1.45; overflow-wrap: anywhere; }
.deadline-flow__band-heading p { flex: 0 1 auto; margin: 0; color: var(--ledger-muted); font-size: 11px; line-height: 1.45; text-align: right; overflow-wrap: anywhere; }
.deadline-flow__task-list { display: grid; gap: 8px; min-width: 0; margin: 11px 0 0; padding: 0; list-style: none; }
.deadline-flow__task-list li { min-width: 0; }
.deadline-flow__task { display: grid; gap: 7px; min-width: 0; padding: 12px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 5px; }
.deadline-flow__course { color: #59667d; font-size: 12px; font-weight: 650; line-height: 1.45; overflow-wrap: anywhere; }
.deadline-flow__task-name { color: var(--ledger-ink); font-size: 14px; line-height: 1.5; overflow-wrap: anywhere; word-break: break-word; }
.deadline-flow__timing { display: grid; gap: 2px; color: #43516b; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.deadline-flow__timing > span { color: var(--ledger-muted); font-weight: 650; }
.deadline-flow__meta { display: flex; flex-wrap: wrap; gap: 5px; min-width: 0; margin-top: 2px; }
.deadline-flow__metric { min-width: 0; padding: 3px 6px; color: #536177; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-radius: 3px; font-size: 11px; font-weight: 650; line-height: 1.45; overflow-wrap: anywhere; }
.deadline-flow__metric--workload { color: #43516b; }
.deadline-flow__source { min-width: 0; padding: 8px 10px; background: var(--ledger-canvas); border-left: 3px solid var(--ledger-indigo); }
.deadline-flow__source--deleted { border-left-color: var(--ledger-amber); }
.deadline-flow__source--missing, .deadline-flow__source--contradictory { border-left-color: var(--ledger-line); }
.deadline-flow__source > div { display: grid; gap: 2px; min-width: 0; }
.deadline-flow__source-title { color: #59667d; font-size: 11px; font-weight: 700; line-height: 1.45; }
.deadline-flow__source strong { color: #43516b; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; word-break: break-word; }
.deadline-flow__source p { margin: 0; color: var(--ledger-muted); font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.deadline-flow__actions { display: flex; flex-wrap: wrap; gap: 8px; }
.deadline-flow__action { min-height: 44px; padding: 0 12px; color: #43516b; background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 4px; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; touch-action: manipulation; }
.deadline-flow__action--primary { color: var(--ledger-paper); background: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.deadline-flow__action:hover:not(:disabled) { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.deadline-flow__action--primary:hover:not(:disabled) { color: var(--ledger-paper); background: #4853cf; border-color: #4853cf; }
.deadline-flow__action:focus-visible { outline: 3px solid rgba(89, 100, 237, .42); outline-offset: 3px; }
.deadline-flow__action:disabled { color: var(--ledger-muted); background: #eef1f5; border-color: #dfe4eb; cursor: wait; }

@media (max-width: 560px) {
  .deadline-flow { padding: 16px; }
  .deadline-flow__heading { align-items: stretch; flex-direction: column; gap: 10px; }
  .deadline-flow__count { align-self: flex-start; }
  .deadline-flow__ruler-marker { font-size: 10px; }
  .deadline-flow__bands { grid-template-columns: minmax(0, 1fr); }
  .deadline-flow__band-heading { align-items: flex-start; flex-direction: column; gap: 2px; }
  .deadline-flow__band-heading p { text-align: left; }
  .deadline-flow__actions { display: grid; grid-template-columns: minmax(0, 1fr); }
  .deadline-flow__action { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .deadline-flow *, .deadline-flow *::before, .deadline-flow *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }
}
</style>
