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
                  <div class="task-agenda__card-topline">
                    <h4>{{ task.name }}</h4>
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
                    <button
                      v-if="!task.terminal"
                      type="button"
                      class="task-agenda__action task-agenda__action--primary"
                      :disabled="hasBusyTasks"
                      :aria-label="`${taskBusy(task) ? '正在标记完成' : '标记完成'}：${task.name}`"
                      @click="emit('complete-task', task.source)"
                    >
                      {{ taskBusy(task) ? '正在完成…' : '标记完成' }}
                    </button>
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
                    <button
                      type="button"
                      class="task-agenda__action task-agenda__action--quiet"
                      :disabled="hasBusyTasks"
                      :aria-label="`编辑任务：${task.name}`"
                      @click="emit('edit-task', task.source)"
                    >
                      编辑
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
  maxItems: { type: Number, default: MAX_DIRECT_ITEMS },
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
.task-agenda { min-width: 0; padding: 0; color: var(--ledger-ink); }
.task-agenda__heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-width: 0; }
.task-agenda__heading h2 { margin: 0; color: var(--ledger-ink); font-family: inherit; font-size: 18px; line-height: 1.4; }
.task-agenda__count { flex: 0 0 auto; color: var(--ledger-muted); font-size: 12px; line-height: 1.4; }
.task-agenda__state, .task-agenda__empty { display: grid; gap: 7px; margin-top: 18px; padding: 16px; background: var(--ledger-canvas); border: 1px solid var(--ledger-line); border-left: 3px solid var(--ledger-indigo); border-radius: 6px; }
.task-agenda__state strong, .task-agenda__empty strong { color: var(--ledger-ink); font-size: 14px; line-height: 1.5; }
.task-agenda__state p, .task-agenda__empty p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.task-agenda__state--pending, .task-agenda__state--loading { border-left-color: var(--ledger-amber); }
.task-agenda__state--error, .task-agenda__state--invalid { border-left-color: var(--ledger-coral); }
.task-agenda__timeline { position: relative; min-width: 0; margin-top: 18px; padding-left: 29px; }
.task-agenda__spine { position: absolute; top: 6px; bottom: 8px; left: 6px; width: 2px; background: repeating-linear-gradient(to bottom, var(--ledger-line) 0 8px, transparent 8px 13px); }
.task-agenda__now { position: relative; display: flex; align-items: center; gap: 8px; min-width: 0; margin: 0 0 16px -29px; color: var(--ledger-muted); font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif; font-size: 11px; font-weight: 700; letter-spacing: .07em; line-height: 1.45; }
.task-agenda__now::before { content: ''; flex: 0 0 auto; width: 14px; height: 14px; margin-right: 8px; background: var(--ledger-paper); border: 3px solid var(--ledger-indigo); border-radius: 50%; box-shadow: 0 0 0 3px #f1f7f3; }
.task-agenda__now::after { content: ''; flex: 1 1 auto; min-width: 0; border-top: 1px solid var(--ledger-line); }
.task-agenda__now span { color: var(--ledger-indigo); }
.task-agenda__now time { min-width: 0; overflow-wrap: anywhere; }
.task-agenda__group { position: relative; min-width: 0; margin-top: 20px; }
.task-agenda__group:first-of-type { margin-top: 0; }
.task-agenda__group-heading { position: relative; display: flex; align-items: flex-start; gap: 11px; min-width: 0; margin-left: -29px; }
.task-agenda__group-node { flex: 0 0 auto; width: 12px; height: 12px; margin: 5px 9px 0 1px; background: var(--ledger-paper); border: 2px solid var(--ledger-indigo); border-radius: 50%; }
.task-agenda__group--overdue .task-agenda__group-node { border-color: var(--ledger-coral); }
.task-agenda__group--today .task-agenda__group-node, .task-agenda__group--tomorrow .task-agenda__group-node { border-color: var(--ledger-amber); }
.task-agenda__group--completed .task-agenda__group-node { border-style: dashed; border-color: var(--ledger-muted); }
.task-agenda__group--canceled .task-agenda__group-node { border-style: dashed; border-color: #b3a56d; }
.task-agenda__group-heading > div { min-width: 0; }
.task-agenda__group-heading p { margin: 0; color: var(--ledger-indigo); font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif; font-size: 10px; font-weight: 750; letter-spacing: .1em; line-height: 1.45; }
.task-agenda__group--overdue .task-agenda__group-heading p { color: var(--ledger-coral); }
.task-agenda__group--today .task-agenda__group-heading p, .task-agenda__group--tomorrow .task-agenda__group-heading p { color: var(--ledger-amber-text); }
.task-agenda__group-heading h3 { margin: 3px 0 0; color: var(--ledger-ink); font-size: 15px; line-height: 1.45; overflow-wrap: anywhere; }
.task-agenda__group-heading h3 span { color: var(--ledger-muted); font-size: 12px; font-weight: 600; }
.task-agenda__list { display: grid; gap: 0; min-width: 0; margin: 8px 0 0; padding: 0; list-style: none; }
.task-agenda__card { display: grid; grid-template-columns: minmax(0, 1fr) auto; column-gap: 18px; min-width: 0; padding: 12px 0; background: var(--ledger-paper); border-bottom: 1px solid var(--ledger-line); }
.task-agenda__card--overdue { border-left-color: var(--ledger-coral); }
.task-agenda__card--today, .task-agenda__card--tomorrow { border-left-color: var(--ledger-amber); }
.task-agenda__card--completed, .task-agenda__card--canceled { background: transparent; }
.task-agenda__card-topline { display: flex; grid-column: 1; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; min-width: 0; }
.task-agenda__card-topline h4 { margin: 0; color: var(--ledger-ink); font-size: 15px; font-weight: 650; line-height: 1.45; overflow-wrap: anywhere; }
.task-agenda__status { color: var(--ledger-muted); font-size: 11px; line-height: 1.45; white-space: nowrap; }
.task-agenda__course { margin-right: 6px; color: var(--ledger-muted); font-size: 12px; line-height: 1.55; overflow-wrap: anywhere; }
.task-agenda__schedule { display: flex; grid-column: 1; flex-wrap: wrap; align-items: baseline; gap: 2px 6px; margin: 5px 0 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.65; overflow-wrap: anywhere; }
.task-agenda__schedule time { font-variant-numeric: tabular-nums; }
.task-agenda__source { display: flex; grid-column: 1; align-items: center; min-width: 0; margin-top: 3px; }
.task-agenda__source-copy { min-width: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.task-agenda__source--deleted .task-agenda__source-copy { color: var(--ledger-amber-text); }
.task-agenda__source-action { min-width: 44px; min-height: 36px; max-width: 100%; padding: 4px 0; color: var(--ledger-link); background: transparent; border: 0; border-radius: 4px; cursor: pointer; font: inherit; font-size: 12px; line-height: 1.5; text-align: left; overflow-wrap: anywhere; touch-action: manipulation; }
.task-agenda__source-action:hover { text-decoration: underline; text-underline-offset: 3px; }
.task-agenda__source-action:active { box-shadow: inset 0 0 0 999px rgba(30, 42, 68, .08); }
.task-agenda__source-action:focus-visible { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 42%, transparent); outline-offset: 3px; }
.task-agenda__source-action:disabled { cursor: wait; opacity: .58; }
.task-agenda__actions { display: flex; grid-column: 2; grid-row: 1 / span 3; align-self: center; flex-wrap: wrap; align-items: center; gap: 4px; margin: 0; }
.task-agenda__action, .task-agenda__show-all { display: inline-flex; align-items: center; justify-content: center; min-width: 0; min-height: 44px; padding: 8px 12px; color: #43516b; background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 8px; cursor: pointer; font: inherit; font-size: 12px; font-weight: 700; line-height: 1.4; text-align: center; touch-action: manipulation; transition: color .16s ease, background-color .16s ease, border-color .16s ease, box-shadow .16s ease; }
.task-agenda__action { flex: 0 0 auto; min-width: 44px; }
.task-agenda__action--primary { color: var(--ledger-paper); background: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.task-agenda__action--quiet { flex-grow: 0; color: var(--ledger-muted); border-color: transparent; }
.task-agenda__action:disabled { cursor: wait; opacity: .58; }
.task-agenda__action:hover, .task-agenda__show-all:hover { color: var(--ledger-indigo); background: #f1f7f3; border-color: var(--ledger-indigo); }
.task-agenda__action--primary:hover { color: var(--ledger-paper); background: var(--ledger-link); border-color: var(--ledger-link); }
.task-agenda__action:active, .task-agenda__show-all:active { box-shadow: inset 0 0 0 999px rgba(30, 42, 68, .06); }
.task-agenda__action:focus-visible, .task-agenda__show-all:focus-visible { position: relative; z-index: 1; outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 42%, transparent); outline-offset: 3px; }
.task-agenda__notice { margin: 16px 0 0; padding: 10px 12px; color: var(--ledger-amber-text); background: #fff8ec; border: 1px solid #ecd0a8; border-left: 3px solid var(--ledger-amber); border-radius: 5px; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.task-agenda__show-all { width: 100%; margin-top: 16px; color: var(--ledger-link); }
.task-agenda__empty-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 4px; }
.task-agenda__empty .task-agenda__show-all { margin-top: 0; }
.task-agenda__show-all--primary { color: var(--ledger-paper); background: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.task-agenda__show-all--primary:hover { color: var(--ledger-paper); background: var(--ledger-link); border-color: var(--ledger-link); }
@media (max-width: 420px) { .task-agenda__empty-actions { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 560px) { .task-agenda { padding: 0; } .task-agenda__heading { flex-wrap: wrap; gap: 10px; } .task-agenda__count { justify-self: start; } .task-agenda__timeline { padding-left: 25px; } .task-agenda__now, .task-agenda__group-heading { margin-left: -25px; } .task-agenda__spine { left: 5px; } .task-agenda__now::before { width: 12px; height: 12px; margin-right: 7px; } .task-agenda__group-node { width: 11px; height: 11px; margin-right: 8px; } .task-agenda__card { display: block; padding: 12px 0; } .task-agenda__source { align-items: stretch; flex-direction: column; } .task-agenda__source-action { width: 100%; min-height: 44px; } .task-agenda__actions { display: grid; grid-template-columns: minmax(0, 1fr) auto; margin-top: 10px; gap: 8px; } .task-agenda__action { width: 100%; } }
@media (prefers-reduced-motion: reduce) { .task-agenda *, .task-agenda *::before, .task-agenda *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; } }
</style>
