<template>
  <section class="deadline-flow" aria-labelledby="deadline-flow-title">
    <header class="deadline-flow__heading">
      <div>
        <h2 id="deadline-flow-title">近期截止</h2>
        <p class="deadline-flow__lede">未来 7 天，按截止时间排序。</p>
      </div>
      <router-link class="deadline-flow__all" to="/tasks">全部任务</router-link>
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
            <p>{{ band.tasks.length }} 项</p>
          </div>

          <ul class="deadline-flow__task-list">
            <li v-for="task in band.tasks" :key="task.key">
              <article class="deadline-flow__task" :aria-label="taskAriaLabel(task)">
                <div class="deadline-flow__task-heading">
                  <button type="button" class="deadline-flow__task-name" :aria-label="`查看任务：${task.name}`" @click="emit('open-task', task.source)">{{ task.name }}</button>
                  <span class="deadline-flow__remaining">{{ task.remainingLabel }}</span>
                </div>
                <div class="deadline-flow__timing">
                  <span class="deadline-flow__course">{{ task.courseName }}</span>
                  <time :datetime="task.dueIso">{{ task.dueLabel }}</time>
                </div>
                <details class="deadline-flow__source" :class="`deadline-flow__source--${task.sourceContext.state}`">
                  <summary>任务详情与资料<span class="deadline-flow__source-state">{{ task.sourceContext.title }}</span></summary>
                  <div>
                    <span v-if="task.workloadLabel || task.priorityLabel || task.statusLabel" class="deadline-flow__meta">
                      <span v-if="task.workloadLabel" class="deadline-flow__metric deadline-flow__metric--workload">{{ task.workloadLabel }}</span>
                      <span v-if="task.priorityLabel" class="deadline-flow__metric">{{ task.priorityLabel }}</span>
                      <span v-if="task.statusLabel" class="deadline-flow__metric">状态：{{ task.statusLabel }}</span>
                    </span>
                    <strong v-if="task.sourceContext.label">{{ task.sourceContext.label }}</strong>
                    <p>{{ task.sourceContext.detail }}</p>
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
                </details>
              </article>
            </li>
          </ul>
        </section>
      </div>
    </template>

    <div v-else class="deadline-flow__state deadline-flow__state--empty" role="status" aria-live="polite">
      <el-icon class="deadline-flow__empty-icon" aria-hidden="true"><Calendar /></el-icon>
      <strong>近期没有要交的任务</strong>
      <p v-if="tasks.length">{{ emptyStateDetail }}</p>
      <router-link to="/tasks?action=quick-task" class="deadline-flow__empty-link">记下新的安排</router-link>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Calendar } from '@element-plus/icons-vue'
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
  loading: '正在同步最新安排…',
  error: '刷新页面后重试。',
  invalid: '部分日期需要核对，请打开全部任务检查。',
}[viewState.value] || '信息未确认前，不会显示为正常安排。'))

const emptyStateDetail = computed(() => {
  if (!props.tasks.length) return '当前没有未来 7 天内到期的任务。'
  return '未设置、已取消、已过期、截止时间无效或超过 7 天的任务不会出现在这里。'
})

function normalizeTask(source, sourceIndex, nowTime) {
  if (!source || typeof source !== 'object') return null

  const name = cleanText(source.name)
  const dueAt = parseDate(source.due_at)
  if (!name || !dueAt || ['completed', 'canceled'].includes(source.status)) return null

  const dueTime = dueAt.getTime()
  const distance = dueTime - nowTime
  if (distance <= 0 || distance > WINDOW) return null

  const remainingMinutes = validMinutes(source.remaining_minutes)
  const estimatedMinutes = validMinutes(source.estimated_minutes)
  const priority = validPriority(source.priority)
  const courseName = cleanText(source.course_name) || '未归类课程'
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
    canceled: '已取消',
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
.deadline-flow__empty-icon { width: 42px; height: 42px; margin-bottom: 10px; color: var(--ledger-link); background: #eaf2ed; border-radius: 12px; font-size: 23px; }
.deadline-flow__empty-link { display: inline-flex; align-items: center; align-self: start; min-height: 44px; margin-top: 8px; color: var(--ledger-link); font-size: 13px; }
.deadline-flow__empty-link:hover { text-decoration: underline; text-underline-offset: 4px; }
.deadline-flow { min-width: 0; padding: 24px 26px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: var(--ledger-radius); }
.deadline-flow__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; min-width: 0; }
.deadline-flow__heading > div { min-width: 0; }
.deadline-flow__heading h2 { margin: 0; font-size: 16px; font-weight: 600; line-height: 1.5; }
.deadline-flow__lede { margin: 6px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.deadline-flow__all { display: inline-flex; align-items: center; flex: 0 0 auto; min-height: 44px; color: var(--ledger-link); font-size: 13px; }
.deadline-flow__all:hover { text-decoration: underline; text-underline-offset: 4px; }
.deadline-flow__state { display: grid; gap: 7px; margin-top: 22px; padding: 10px 0; }
.deadline-flow__state strong { font-size: 14px; font-weight: 500; line-height: 1.6; }
.deadline-flow__state p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.deadline-flow__state--error, .deadline-flow__state--invalid { padding-left: 12px; border-left: 2px solid var(--ledger-coral); }
.deadline-flow__state--invalid { border-left-color: var(--ledger-amber); }
.deadline-flow__bands { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; min-width: 0; margin-top: 22px; }
.deadline-flow__band { min-width: 0; }
.deadline-flow__band-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; padding-bottom: 9px; border-bottom: 1px solid var(--ledger-line); }
.deadline-flow__band-heading h3 { min-width: 0; margin: 0; color: var(--ledger-muted); font-size: 12px; font-weight: 500; line-height: 1.5; }
.deadline-flow__band--within-day .deadline-flow__band-heading h3 { color: #a24a42; }
.deadline-flow__band--within-three-days .deadline-flow__band-heading h3 { color: #805d22; }
.deadline-flow__band-heading p { margin: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; }
.deadline-flow__task-list { display: grid; min-width: 0; margin: 0; padding: 0; list-style: none; }
.deadline-flow__task-list li { min-width: 0; }
.deadline-flow__task-list li + li { border-top: 1px solid var(--ledger-line); }
.deadline-flow__task { min-width: 0; padding: 14px 0 2px; }
.deadline-flow__task-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; min-width: 0; }
.deadline-flow__task-name { min-width: 0; margin: -8px 0; padding: 8px 0; color: var(--ledger-ink); background: transparent; border: 0; font: inherit; font-size: 15px; font-weight: 600; line-height: 1.7; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
.deadline-flow__task-name:hover { color: var(--ledger-link); text-decoration: underline; text-underline-offset: 4px; }
.deadline-flow__remaining { flex: 0 0 auto; color: var(--ledger-muted); font-size: 12px; line-height: 1.7; }
.deadline-flow__band--within-day .deadline-flow__remaining { color: #a24a42; }
.deadline-flow__timing { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 4px; color: var(--ledger-muted); font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
.deadline-flow__source { min-width: 0; margin-top: 3px; }
.deadline-flow__source summary { min-height: 44px; padding: 12px 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.7; cursor: pointer; overflow-wrap: anywhere; }
.deadline-flow__source-state { margin-left: 12px; }
.deadline-flow__source--deleted .deadline-flow__source-state, .deadline-flow__source--identity_missing .deadline-flow__source-state, .deadline-flow__source--contradictory .deadline-flow__source-state { color: #805d22; }
.deadline-flow__source > div { display: grid; gap: 9px; min-width: 0; margin-bottom: 14px; padding: 14px; background: var(--ledger-canvas); border-radius: 6px; }
.deadline-flow__source strong { font-size: 13px; font-weight: 500; line-height: 1.6; overflow-wrap: anywhere; }
.deadline-flow__source p { margin: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
.deadline-flow__meta { display: flex; flex-wrap: wrap; gap: 5px 12px; min-width: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
.deadline-flow__action { justify-self: start; min-height: 44px; padding: 8px 12px; color: var(--ledger-link); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 8px; font: inherit; font-size: 13px; cursor: pointer; }
.deadline-flow__action:hover:not(:disabled) { border-color: var(--ledger-indigo); }
.deadline-flow__action:disabled { color: var(--ledger-muted); background: #eef1ef; border-color: #dfe5e0; cursor: wait; }
.deadline-flow__action:focus-visible, .deadline-flow__all:focus-visible, .deadline-flow__task-name:focus-visible, .deadline-flow__source summary:focus-visible { outline: 3px solid rgba(50, 120, 100, .35); outline-offset: 3px; }
@media (max-width: 560px) { .deadline-flow { padding: 18px; } .deadline-flow__task-heading { align-items: flex-start; flex-direction: column; gap: 4px; } .deadline-flow__source-state { margin-left: 8px; } .deadline-flow__action { width: 100%; } }
</style>
