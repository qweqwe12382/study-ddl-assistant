<template>
  <section class="task-agenda" aria-labelledby="task-agenda-title" :aria-busy="viewState === 'loading' || viewState === 'pending'">
    <header class="task-agenda__heading">
      <h2 id="task-agenda-title">任务清单</h2>
      <span v-if="viewState === 'ready' && normalizedTasks.length" class="task-agenda__count" role="status">
        已显示 {{ visibleTasks.length }} 项
      </span>
    </header>

    <div
      v-if="viewState !== 'ready'"
      class="task-agenda__state"
      :class="`task-agenda__state--${viewState}`"
      :role="viewState === 'error' || viewState === 'invalid' ? 'alert' : 'status'"
      aria-live="polite"
      aria-atomic="true"
    >
      <strong>{{ stateTitle }}</strong>
      <p>{{ stateDetail }}</p>
    </div>

    <template v-else-if="visibleTasks.length">
      <div class="task-agenda__timeline">
        <span class="task-agenda__spine" aria-hidden="true"></span>
        <template v-for="row in timelineRows" :key="row.id">
          <p v-if="row.type === 'now'" class="task-agenda__now" aria-label="当前时间分隔线">
            <span>现在</span><time :datetime="nowIso">{{ nowLabel }}</time>
          </p>

          <section
            v-else
            class="task-agenda__group"
            :class="`task-agenda__group--${row.group.id}`"
            :aria-labelledby="`task-agenda-group-${row.group.id}`"
          >
            <header class="task-agenda__group-heading">
              <span class="task-agenda__group-node" aria-hidden="true"></span>
              <div>
                <h3 :id="`task-agenda-group-${row.group.id}`">{{ row.group.label }} <span>· {{ row.group.visibleCount }} 项</span></h3>
              </div>
            </header>

            <TransitionGroup tag="ol" name="task-list" class="task-agenda__list">
              <li v-for="task in row.group.tasks" :key="task.key" class="task-agenda__item">
                <article class="task-agenda__card" :class="`task-agenda__card--${task.groupId}`">
                  <button v-if="!task.terminal" type="button" class="task-agenda__check" :disabled="hasBusyTasks" :aria-busy="taskBusy(task)" :aria-label="`${taskBusy(task) ? '正在标记完成' : '标记完成'}：${task.name}`" :title="`完成：${task.name}`" @click="emit('complete-task', task.source)"><el-icon aria-hidden="true"><Check /></el-icon></button>
                  <span v-else class="task-agenda__check is-done" :aria-label="task.completed ? '已完成' : '已取消'"><el-icon v-if="task.completed" aria-hidden="true"><Check /></el-icon><span v-else aria-hidden="true">–</span></span>
                  <div class="task-agenda__card-topline">
                    <h4><button type="button" class="task-agenda__title-button" :disabled="hasBusyTasks" :aria-label="`编辑任务：${task.name}`" @click="emit('edit-task', task.source)">{{ task.name }}</button></h4>
                    <span v-if="!task.terminal && task.statusLabel !== '逾期'" class="task-agenda__status">{{ task.statusLabel }}</span>
                  </div>

                  <p class="task-agenda__schedule">
                    <span class="task-agenda__course" :aria-label="`课程：${task.courseName}`">{{ task.courseName }}</span>
                    <time v-if="task.dueIso" :datetime="task.dueIso">{{ task.dueLabel }}</time>
                    <span v-else>{{ task.dueLabel }}</span>
                    <span v-if="task.remainingLabel" aria-hidden="true"> · </span>
                    <span>{{ task.remainingLabel }}</span>
                    <template v-if="task.workloadLabel">
                      <span aria-hidden="true"> · </span>
                      <span>{{ task.workloadLabel }}</span>
                    </template>
                  </p>

                  <div
                    v-if="task.sourceContext.state !== 'missing'"
                    class="task-agenda__source"
                    :class="`task-agenda__source--${task.sourceContext.state}`"
                  >
                    <button
                      v-if="task.sourceContext.state === 'available'"
                      type="button"
                      class="task-agenda__source-action"
                      :disabled="materialBusy(task)"
                      :aria-label="`${materialBusy(task) ? '正在打开资料' : '打开资料'}：${task.sourceContext.label}`"
                      @click="emit('open-material', task.source)"
                    >
                      {{ materialBusy(task) ? '正在打开…' : `来源：${task.sourceContext.label}` }}
                    </button>
                    <span v-else class="task-agenda__source-copy">{{ task.sourceContext.title }}{{ task.sourceContext.label ? `：${task.sourceContext.label}` : '' }}</span>
                  </div>

                  <div class="task-agenda__actions" role="group" :aria-label="`任务操作：${task.name}`">
                    <router-link v-if="!task.completed && !task.canceled && focusTaskTarget(task.source)" class="task-agenda__action" :to="focusTaskTarget(task.source)" :aria-label="`开始专注 25 分钟：${task.name}`">专注 25 分钟</router-link>
                    <button
                      v-if="task.completed"
                      type="button"
                      class="task-agenda__action"
                      :disabled="hasBusyTasks"
                      :aria-label="`${task.completed ? '更新' : '补充'}完成反馈：${task.name}`"
                      @click="emit('feedback-task', task.source)"
                    >
                      {{ task.completed ? '更新反馈' : '补充反馈' }}
                    </button>
                  </div>
                </article>
              </li>
            </TransitionGroup>
          </section>
        </template>
      </div>

      <p v-if="invalidDateCount" class="task-agenda__notice" role="status">
        {{ invalidDateCount }} 项任务的截止时间无法确认，未纳入时间线；请在完整清单中检查。
      </p>

      <button
        type="button"
        class="task-agenda__show-all"
        :aria-label="hiddenTaskCount ? `进入完整任务管理，另有 ${hiddenTaskCount} 项` : '进入完整任务管理'"
        @click="emit('show-all')"
      >
        {{ hiddenTaskCount ? `查看完整任务管理（另有 ${hiddenTaskCount} 项）` : '进入完整任务管理' }}
      </button>
    </template>

    <div v-else class="task-agenda__empty" role="status" aria-live="polite">
      <strong>{{ emptyTitle }}</strong>
      <p>{{ emptyDetail }}</p>
      <div class="task-agenda__empty-actions">
        <button
          v-if="filtered"
          type="button"
          class="task-agenda__show-all task-agenda__show-all--primary"
          @click="emit('clear-filters')"
        >
          清除筛选
        </button>
        <button type="button" class="task-agenda__show-all" @click="emit('show-all')">
          {{ filtered ? '进入完整任务管理' : '查看全部任务' }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Check } from '@element-plus/icons-vue'
import { focusTaskTarget } from '../utils/dailyWorkflow'

const DAY = 24 * 60 * 60 * 1000
const MAX_DIRECT_ITEMS = 12

const GROUPS = [
  { id: 'overdue', code: 'PAST DUE', label: '已逾期' },
  { id: 'today', code: 'TODAY', label: '今天' },
  { id: 'tomorrow', code: 'TOMORROW', label: '明天' },
  { id: 'next-week', code: 'NEXT 7 DAYS', label: '未来 7 天' },
  { id: 'later', code: 'LATER', label: '稍后' },
  { id: 'undated', code: 'DATE TBD', label: '未定日期' },
  { id: 'completed', code: 'COMPLETED', label: '已完成' },
  { id: 'canceled', code: 'CANCELED', label: '已取消' },
]

const props = defineProps({
  state: { type: String, default: 'loading' },
  tasks: { type: Array, default: () => [] },
  filtered: { type: Boolean, default: false },
  busyTaskIds: { type: Array, default: () => [] },
  busyMaterialIds: { type: Array, default: () => [] },
  now: { type: [Date, String, Number], default: null },
  maxItems: { type: Number, default: 12 },
})

const emit = defineEmits(['complete-task', 'feedback-task', 'edit-task', 'open-material', 'show-all', 'clear-filters'])

const requestedState = computed(() => (
  ['pending', 'loading', 'ready', 'error', 'invalid'].includes(props.state) ? props.state : 'invalid'
))

const referenceNow = computed(() => {
  if (props.now === null || props.now === undefined) return new Date()
  return parseDate(props.now)?.date || null
})

const viewState = computed(() => {
  if (requestedState.value !== 'ready') return requestedState.value
  if (!Array.isArray(props.tasks) || !referenceNow.value) return 'invalid'
  return 'ready'
})

const normalizedResult = computed(() => {
  if (viewState.value !== 'ready') return { tasks: [], invalidDateCount: 0 }

  const now = referenceNow.value
  const todayKey = localDayKey(now)
  let invalidDateCount = 0
  const tasks = props.tasks
    .map((source, sourceIndex) => {
      const normalized = normalizeTask(source, sourceIndex, now, todayKey)
      if (normalized === 'invalid-date') invalidDateCount += 1
      return normalized
    })
    .filter((task) => task && task !== 'invalid-date')

  return { tasks: sortTasks(tasks), invalidDateCount }
})

const normalizedTasks = computed(() => normalizedResult.value.tasks)
const invalidDateCount = computed(() => normalizedResult.value.invalidDateCount)
const visibleLimit = computed(() => {
  const requested = Number(props.maxItems)
  if (!Number.isFinite(requested)) return MAX_DIRECT_ITEMS
  return Math.max(1, Math.min(MAX_DIRECT_ITEMS, Math.floor(requested)))
})
const visibleTasks = computed(() => normalizedTasks.value.slice(0, visibleLimit.value))
const hiddenTaskCount = computed(() => Math.max(0, normalizedTasks.value.length - visibleTasks.value.length))

const visibleGroups = computed(() => GROUPS
  .map((group) => {
    const tasks = visibleTasks.value.filter((task) => task.groupId === group.id)
    return { ...group, visibleCount: tasks.length, tasks }
  })
  .filter((group) => group.tasks.length)
)
const timelineRows = computed(() => {
  const rows = []
  let nowInserted = false
  visibleGroups.value.forEach((group) => {
    if (!nowInserted && group.id !== 'overdue') {
      rows.push({ type: 'now', id: 'now' })
      nowInserted = true
    }
    rows.push({ type: 'group', id: `group-${group.id}`, group })
  })
  if (!nowInserted) rows.push({ type: 'now', id: 'now' })
  return rows
})
const busyTaskSet = computed(() => new Set(props.busyTaskIds.map((id) => String(id))))
const busyMaterialSet = computed(() => new Set(props.busyMaterialIds.map((id) => String(id))))
const hasBusyTasks = computed(() => busyTaskSet.value.size > 0)

const nowIso = computed(() => referenceNow.value?.toISOString() || undefined)
const nowLabel = computed(() => referenceNow.value ? formatDateTime(referenceNow.value) : '当前时间待确认')

const stateTitle = computed(() => ({
  pending: '任务安排正在准备',
  loading: '正在读取任务安排',
  error: '任务安排暂时无法读取',
  invalid: '任务安排信息不完整',
}[viewState.value] || '任务安排信息不完整'))

const stateDetail = computed(() => ({
  pending: '正在准备数据，暂不显示任务。',
  loading: '正在加载任务列表。',
  error: '请稍后重试，重新读取任务安排。',
  invalid: '任务列表或当前时间不完整，暂时无法归类。',
}[viewState.value] || '任务信息不完整，暂时无法展示。'))

const emptyTitle = computed(() => {
  if (props.filtered && !props.tasks.length) return '没有符合筛选条件的任务'
  return invalidDateCount.value ? '暂无可确认时间线的任务' : '当前没有可展示的任务'
})
const emptyDetail = computed(() => {
  if (props.filtered && !props.tasks.length) return '调整关键词、课程或状态，或清除筛选后查看全部。'
  if (invalidDateCount.value) return '部分任务截止时间无法确认，请在全部任务中检查。'
  if (!props.tasks.length) return '添加任务后，这里会按日期生成截止安排。'
  return '当前没有可直接排入时间线的任务。'
})

function normalizeTask(source, sourceIndex, now, todayKey) {
  if (!source || typeof source !== 'object') return null

  const completed = source.status === 'completed'
  const canceled = source.status === 'canceled'
  const dueInput = source.due_at
  const hasDueInput = dueInput !== null && dueInput !== undefined && String(dueInput).trim() !== ''
  const parsedDue = hasDueInput ? parseDate(dueInput) : null
  if (hasDueInput && !parsedDue) return 'invalid-date'

  const name = cleanText(source.name) || '未命名任务'
  const courseName = cleanText(source.course_name) || cleanText(source.course?.name) || '未归类课程'
  const dueDate = parsedDue?.date || null
  const dueDayKey = dueDate ? localDayKey(dueDate) : null
  const groupId = groupFor({ completed, canceled, dueDate, dueDayKey, hasTime: parsedDue?.hasTime, now, todayKey })
  const remainingLabel = remainingText({ groupId, dueDate, dueDayKey, hasTime: parsedDue?.hasTime, now, todayKey })
  const remainingMinutes = validMinutes(source.remaining_minutes)
  const estimatedMinutes = validMinutes(source.estimated_minutes)
  const actualMinutes = validMinutes(source.actual_minutes)

  return {
    source,
    sourceIndex,
    key: source.id ?? `${sourceIndex}-${name}-${dueDate?.getTime() ?? 'undated'}`,
    name,
    courseName,
    completed,
    canceled,
    terminal: completed || canceled,
    groupId,
    dueDate,
    dueTime: dueDate?.getTime() ?? null,
    dueIso: dueDate?.toISOString() || null,
    dueLabel: dueLabel(dueDate, parsedDue?.hasTime),
    remainingLabel,
    workloadLabel: canceled ? null : workloadText(remainingMinutes, estimatedMinutes, actualMinutes, completed),
    sourceContext: normalizeSourceContext(source.source_context),
    statusLabel: statusText(source.status, groupId),
    priority: validPriority(source.priority),
  }
}

function sortTasks(tasks) {
  const groupIndex = new Map(GROUPS.map((group, index) => [group.id, index]))
  return [...tasks].sort((first, second) => {
    const groupDifference = groupIndex.get(first.groupId) - groupIndex.get(second.groupId)
    if (groupDifference) return groupDifference

    if (first.groupId === 'overdue') return (second.dueTime ?? 0) - (first.dueTime ?? 0) || second.priority - first.priority || first.sourceIndex - second.sourceIndex
    if (first.groupId === 'completed') return (second.dueTime ?? 0) - (first.dueTime ?? 0) || first.sourceIndex - second.sourceIndex
    return (first.dueTime ?? Number.POSITIVE_INFINITY) - (second.dueTime ?? Number.POSITIVE_INFINITY)
      || second.priority - first.priority
      || first.sourceIndex - second.sourceIndex
  })
}

function groupFor({ completed, canceled, dueDate, dueDayKey, hasTime, now, todayKey }) {
  if (completed) return 'completed'
  if (canceled) return 'canceled'
  if (!dueDate) return 'undated'
  if ((hasTime && dueDate.getTime() < now.getTime()) || (!hasTime && dueDayKey < todayKey)) return 'overdue'

  const dayDifference = localDayDifference(dueDate, now)
  if (dayDifference <= 0) return 'today'
  if (dayDifference === 1) return 'tomorrow'
  if (dayDifference <= 7) return 'next-week'
  return 'later'
}

function parseDate(value) {
  if (value instanceof Date || typeof value === 'number') {
    const timestamp = new Date(value).getTime()
    return Number.isFinite(timestamp) ? { date: new Date(timestamp), hasTime: true } : null
  }
  if (typeof value !== 'string') return null

  const text = value.trim()
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[Tt\s](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?([zZ]|[+-]\d{2}:?\d{2})?)?$/.exec(text)
  if (!match) return null

  const [, yearText, monthText, dayText, hourText, minuteText, secondText, fractionText, timezoneText] = match
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const calendarDate = new Date(Date.UTC(year, month - 1, day))
  if (calendarDate.getUTCFullYear() !== year || calendarDate.getUTCMonth() !== month - 1 || calendarDate.getUTCDate() !== day) return null
  if (hourText === undefined) return { date: new Date(year, month - 1, day), hasTime: false }

  const hour = Number(hourText)
  const minute = Number(minuteText)
  const second = secondText === undefined ? 0 : Number(secondText)
  if (hour > 23 || minute > 59 || second > 59) return null
  const milliseconds = Number((fractionText || '').slice(0, 3).padEnd(3, '0'))

  if (!timezoneText) {
    const date = new Date(year, month - 1, day, hour, minute, second, milliseconds)
    if (
      date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day
      || date.getHours() !== hour || date.getMinutes() !== minute || date.getSeconds() !== second
    ) return null
    return { date, hasTime: true }
  }

  const normalizedTimezone = timezoneText.toUpperCase() === 'Z'
    ? 'Z'
    : `${timezoneText.slice(0, 3)}:${timezoneText.slice(-2)}`
  const fraction = fractionText ? `.${fractionText.slice(0, 3)}` : ''
  const timestamp = Date.parse(`${yearText}-${monthText}-${dayText}T${hourText}:${minuteText}:${String(second).padStart(2, '0')}${fraction}${normalizedTimezone}`)
  return Number.isFinite(timestamp) ? { date: new Date(timestamp), hasTime: true } : null
}

function localDayKey(date) {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
}

function localDayDifference(first, second) {
  return Math.round((localDayKey(first) - localDayKey(second)) / DAY)
}

function dueLabel(date, hasTime) {
  if (!date) return '未设置截止日期'
  const dateText = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' }).format(date)
  if (!hasTime) return `截止 ${dateText}`
  const timeText = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date)
  return `截止 ${dateText} ${timeText}`
}

function remainingText({ groupId, dueDate, hasTime, now }) {
  if (!dueDate || ['completed', 'canceled'].includes(groupId)) return null
  if (groupId === 'overdue') return hasTime ? `已逾期 ${durationText(now.getTime() - dueDate.getTime())}` : '截止日已过'
  if (!hasTime) {
    const days = Math.max(0, localDayDifference(dueDate, now))
    return days ? `距截止 ${days} 天` : '今天截止'
  }
  return `还剩 ${durationText(dueDate.getTime() - now.getTime())}`
}

function durationText(milliseconds) {
  const minutes = Math.max(0, Math.ceil(milliseconds / 60000))
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const remainingMinutes = minutes % 60
  if (days) return `${days} 天${hours ? ` ${hours} 小时` : ''}`
  if (hours) return `${hours} 小时${remainingMinutes ? ` ${remainingMinutes} 分钟` : ''}`
  return `${remainingMinutes} 分钟`
}

function workloadText(remainingMinutes, estimatedMinutes, actualMinutes, completed) {
  if (completed && actualMinutes !== null) return `实际 ${durationText(actualMinutes * 60000)}`
  if (completed && estimatedMinutes !== null) return `原预计 ${durationText(estimatedMinutes * 60000)}`
  if (completed) return null
  if (remainingMinutes !== null && estimatedMinutes !== null) return `还需 ${durationText(remainingMinutes * 60000)} / 预计 ${durationText(estimatedMinutes * 60000)}`
  if (remainingMinutes !== null) return `还需 ${durationText(remainingMinutes * 60000)}`
  if (estimatedMinutes !== null) return `预计 ${durationText(estimatedMinutes * 60000)}`
  return null
}

function taskBusy(task) {
  return busyTaskSet.value.has(String(task.source?.id))
}

function materialBusy(task) {
  return task.sourceContext.materialId !== null
    && busyMaterialSet.value.has(String(task.sourceContext.materialId))
}

function validMinutes(value) {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) && numeric >= 0 ? Math.round(numeric) : null
}

function validPriority(value) {
  const numeric = Number(value)
  return Number.isInteger(numeric) && numeric >= 1 && numeric <= 5 ? numeric : 0
}

function cleanText(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function normalizeSourceContext(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { state: 'missing', materialId: null, label: null, title: '尚未关联资料' }
  }

  const materialId = Number(value.material_id)
  const validMaterialId = Number.isInteger(materialId) && materialId > 0 ? materialId : null
  const label = cleanText(value.label)
  if (value.state === 'available' && validMaterialId !== null && label) {
    return { state: 'available', materialId: validMaterialId, label, title: '来源资料' }
  }
  if (value.state === 'deleted' && label) {
    return { state: 'deleted', materialId: null, label, title: '来源资料（已删除）' }
  }
  return { state: 'missing', materialId: null, label: null, title: '尚未关联资料' }
}

function statusText(status, groupId) {
  if (groupId === 'completed') return '已完成'
  if (groupId === 'canceled') return '已取消'
  return {
    in_progress: '进行中',
    overdue: '逾期',
    not_started: '未开始',
  }[status] || '待开始'
}

function formatDateTime(date) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(date)
}
</script>

<style scoped>

.task-agenda { min-width: 0; color: var(--ledger-ink); }
.task-agenda__heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.task-agenda__heading h2 { margin: 0; font-size: 16px; font-weight: 600; }
.task-agenda__count { color: var(--ledger-muted); font-size: 12px; }
.task-agenda__state, .task-agenda__empty { display: grid; gap: 8px; padding: 28px 20px; margin-top: 16px; background: var(--ledger-canvas); border-radius: 10px; }
.task-agenda__state strong, .task-agenda__empty strong { font-size: 14px; }
.task-agenda__state p, .task-agenda__empty p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.7; }
.task-agenda__state--error, .task-agenda__state--invalid { border: 1px solid #e4c3bd; }
.task-agenda__timeline { margin-top: 24px; }
.task-agenda__spine, .task-agenda__group-node { display: none; }
.task-agenda__now { display: flex; align-items: center; gap: 8px; color: var(--ledger-muted); font-size: 12px; margin: 22px 0; }
.task-agenda__now::after { content: ''; flex: 1; height: 1px; background: var(--ledger-line); }
.task-agenda__now time { font-variant-numeric: tabular-nums; }
.task-agenda__group { margin-top: 24px; }
.task-agenda__group:first-of-type { margin-top: 0; }
.task-agenda__group-heading h3 { display: flex; align-items: baseline; gap: 8px; margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.task-agenda__group-heading h3 span { color: var(--ledger-muted); font-size: 12px; font-weight: 400; }
.task-agenda__group--overdue h3 { color: #a3423e; }
.task-agenda__list { position: relative; margin: 0; padding: 0; list-style: none; }
.task-agenda__card { display: grid; grid-template-columns: 44px minmax(0, 1fr) auto; gap: 0 10px; align-items: center; min-width: 0; padding: 12px 8px 14px 0; border-bottom: 1px solid var(--ledger-line); }
.task-agenda__card:focus-within { background: #f5f9f6; border-radius: 8px; }
.task-agenda__check { display: grid; place-items: center; position: relative; grid-column: 1; grid-row: 1 / span 3; width: 44px; height: 44px; padding: 0; border: 0; border-radius: 8px; background: transparent; color: var(--ledger-link); cursor: pointer; }
.task-agenda__check::before { content: ''; position: absolute; width: 20px; height: 20px; border: 1.5px solid #8ba998; border-radius: 50%; transition: background-color .14s ease, border-color .14s ease; }
.task-agenda__check .el-icon { position: relative; font-size: 15px; opacity: 0; }
.task-agenda__check:hover:not(:disabled)::before, .task-agenda__check:focus-visible::before { background: #e1eee6; border-color: var(--ledger-primary); }
.task-agenda__check:hover .el-icon, .task-agenda__check:focus-visible .el-icon, .task-agenda__check.is-done .el-icon { opacity: 1; }
.task-agenda__check.is-done { cursor: default; }
.task-agenda__check.is-done::before { background: #eaf2ed; border-color: #d6e4db; }
.task-agenda__check:disabled { cursor: wait; opacity: .6; }
.task-agenda__check[aria-busy="true"]::before { border-style: dashed; animation: task-saving .8s linear infinite; }
@keyframes task-saving { to { transform: rotate(360deg); } }
.task-agenda__card-topline { display: flex; grid-column: 2; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; min-width: 0; }
.task-agenda__card-topline h4 { margin: 0; min-width: 0; }
.task-agenda__title-button { display: block; padding: 5px 0; min-height: 32px; border: 0; color: var(--ledger-ink); background: transparent; font-size: 14px; font-weight: 600; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
.task-agenda__title-button:hover { color: var(--ledger-link); text-decoration: underline; text-underline-offset: 4px; }
.task-agenda__card--completed .task-agenda__title-button { color: var(--ledger-muted); text-decoration: line-through; text-decoration-color: #9eb0a5; }
.task-agenda__status { font-size: 11px; color: var(--ledger-muted); }
.task-agenda__schedule { display: flex; grid-column: 2; flex-wrap: wrap; gap: 2px 6px; margin: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
.task-agenda__schedule time { font-variant-numeric: tabular-nums; }
.task-agenda__course { margin-right: 4px; }
.task-agenda__source { grid-column: 2; min-width: 0; color: var(--ledger-muted); font-size: 12px; }
.task-agenda__source--deleted { color: var(--ledger-amber-text); }
.task-agenda__source-action { min-height: 32px; max-width: 100%; padding: 5px 0; border: 0; color: var(--ledger-link); background: transparent; font-size: 12px; overflow-wrap: anywhere; cursor: pointer; text-align: left; }
.task-agenda__source-action:hover { text-decoration: underline; }
.task-agenda__actions { display: flex; grid-column: 3; grid-row: 1 / span 3; gap: 6px; }
.task-agenda__action, .task-agenda__show-all { min-height: 44px; padding: 8px 12px; color: var(--ledger-link); background: transparent; border: 0; border-radius: 8px; font-size: 12px; cursor: pointer; }
.task-agenda__action:hover, .task-agenda__show-all:hover { background: #edf4ef; }
.task-agenda__action:disabled, .task-agenda__title-button:disabled, .task-agenda__source-action:disabled { cursor: wait; opacity: .6; }
.task-agenda__show-all { width: 100%; margin-top: 16px; border: 1px solid var(--ledger-line); }
.task-agenda__notice { padding: 12px; color: var(--ledger-amber-text); background: #fff8ed; border-radius: 8px; font-size: 12px; line-height: 1.7; }
.task-agenda__empty-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.task-agenda__empty-actions .task-agenda__show-all { width: auto; }
@media (max-width: 560px) { .task-agenda__card { grid-template-columns: 36px minmax(0, 1fr); padding-right: 0; column-gap: 8px; } .task-agenda__check { width: 36px; } .task-agenda__title-button { min-height: 44px; } .task-agenda__source-action { min-height: 44px; } .task-agenda__actions { grid-column: 2; grid-row: auto; } .task-agenda__action { padding-left: 0; } }

</style>
