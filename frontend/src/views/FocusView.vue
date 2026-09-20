<template>
  <div class="focus-page">
    <header class="focus-header">
      <div>
        <h1>专注计时</h1>
        <p class="focus-lead">一次一件事，留点时间给专注。</p>
      </div>
      <router-link class="focus-back" to="/tasks">返回截止任务</router-link>
    </header>

    <div v-if="errorMessage" class="focus-alert" role="alert">{{ errorMessage }}</div>
    <div v-if="notice" class="focus-notice" role="status">{{ notice }}</div>

    <section v-if="loading" class="focus-board is-loading" aria-live="polite">正在读取待办任务…</section>

    <section v-else-if="loadFailed" class="focus-board is-empty">
      <h3>待办任务尚未加载</h3>
      <p>连接恢复后可以重新读取任务。</p>
      <button class="focus-action primary" type="button" @click="loadTasks">重新加载任务</button>
    </section>

    <section v-else-if="pendingTasks.length === 0" class="focus-board is-empty">
      <h3>现在没有待办任务</h3>
      <p>记下要做的事，直接开始 25 分钟专注。</p>
      <QuickTaskAdd submit-label="添加并开始" @created="startCreatedTask" />
    </section>

    <section v-else class="focus-board" :class="{ 'is-running': phase === 'running', 'is-finished': phase === 'finished' }">
      <div class="focus-main">
        <label class="focus-field">
          <span>这次要专注什么？</span>
          <select v-model="selectedId" :disabled="sessionLocked" data-testid="focus-task-select" @change="errorMessage = ''">
            <option v-if="selectedId === null" :value="null" disabled>请选择要专注的任务</option>
            <option v-for="task in pendingTasks" :key="task.id" :value="task.id">
              {{ task.name }}
            </option>
          </select>
        </label>

        <div class="preset-row" role="group" aria-label="专注时长">
          <button
            v-for="preset in FOCUS_PRESET_MINUTES"
            :key="preset"
            type="button"
            class="preset-chip"
            :class="{ active: durationMinutes === preset }"
            :aria-pressed="durationMinutes === preset"
            :disabled="sessionLocked"
            @click="applyPreset(preset)"
          >
            {{ preset }} 分钟
          </button>
          <label class="custom-minutes" :class="{ active: isCustomDuration }">
            <input
              v-model="customMinutesDraft"
              type="number"
              min="15"
              max="240"
              step="5"
              inputmode="numeric"
              aria-label="自定义专注分钟（15 到 240）"
              :disabled="sessionLocked"
              @change="applyCustomMinutes"
            >
            分钟
          </label>
        </div>

        <p class="focus-clock" role="timer" aria-label="专注剩余时间">{{ clock }}</p>
        <div class="focus-track" aria-hidden="true">
          <span class="focus-fill" :style="{ transform: `scaleX(${progressPercent / 100})` }"></span>
        </div>
        <p class="focus-meta">{{ phaseLabel }} · 目标 {{ durationMinutes }} 分钟</p>

        <div class="control-row">
          <button v-if="phase === 'idle' || phase === 'paused'" class="focus-action primary" type="button" @click="startTimer">
            {{ phase === 'paused' ? '继续专注' : '开始专注' }}
          </button>
          <button v-if="phase === 'running'" class="focus-action" type="button" @click="pauseTimer">暂停</button>
          <button
            v-if="phase === 'running' || phase === 'paused'"
            class="focus-action"
            type="button"
            @click="stopTimer"
          >
            结束专注
          </button>
          <button v-if="phase === 'paused' || (phase === 'finished' && canRecord)" class="focus-action quiet" type="button" :disabled="recording" @click="resetTimer">
            放弃本次
          </button>
        </div>
      </div>

      <aside class="focus-record" aria-live="polite">
        <template v-if="phase !== 'finished'">
          <el-icon class="focus-record-icon" aria-hidden="true"><Timer /></el-icon>
          <h3>{{ phase === 'running' ? '这段时间，留给眼前的事' : '准备好就开始吧' }}</h3>
          <p>满 15 分钟后，可确认记录用时。</p>
          <details class="focus-record-help"><summary>计时与保存说明</summary><small>暂停不计时。记录或放弃前，任务和时长保持锁定；离开或刷新会丢失未保存计时。</small></details>
        </template>
        <template v-else-if="!canRecord">
          <h3>这次不足 15 分钟</h3>
          <p>系统最少记录 15 分钟。可以放弃本次，或继续专注到 15 分钟以上。</p>
          <div class="record-actions">
            <button class="focus-action primary" type="button" @click="startTimer">继续专注</button>
            <button class="focus-action quiet" type="button" @click="resetTimer">放弃本次</button>
          </div>
        </template>
        <template v-else>
          <h3>本次专注 {{ recordedLabel }}</h3>
          <p>把这段真实用时记入「{{ selectedTask?.name }}」。</p>
          <div class="record-actions">
            <button class="focus-action primary" type="button" :disabled="recording" @click="record(true)">
              {{ recording ? '正在记录' : '完成并记录' }}
            </button>
            <button class="focus-action" type="button" :disabled="recording" @click="record(false)">仅记录用时</button>
          </div>
        </template>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Timer } from '@element-plus/icons-vue'

import http from '../api/http'
import { tasksApi } from '../api'
import { authSession } from '../auth/session'
import {
  FOCUS_PRESET_MINUTES,
  activeElapsedSeconds,
  formatClock,
  isRecordable,
  mergeActualMinutes,
  normalizeCustomMinutes,
  recordLabel,
  sessionMinutes,
} from '../utils/focusTimer'
import { editRequestConfig } from '../utils/editPrecondition'
import QuickTaskAdd from '../components/QuickTaskAdd.vue'
import { orderedPendingTasks, resolveFocusTask } from '../utils/dailyWorkflow'

const route = useRoute()
const router = useRouter()
let incomingFocusPending = true
let taskRequestId = 0

const loading = ref(true)
const loadFailed = ref(false)
const errorMessage = ref('')
const tasks = ref([])
const selectedId = ref(null)
const durationMinutes = ref(25)
const customMinutesDraft = ref('')
const phase = ref('idle')
const elapsedSeconds = ref(0)
const recording = ref(false)
const notice = ref('')

let ticker = null
let startedAtMs = 0
let accumulatedSeconds = 0

const sessionLocked = computed(() => phase.value !== 'idle' || recording.value)
const pendingTasks = computed(() => orderedPendingTasks(tasks.value))
const selectedTask = computed(() => pendingTasks.value.find((task) => task.id === selectedId.value) || null)
const clock = computed(() => formatClock(Math.max(0, durationMinutes.value * 60 - elapsedSeconds.value)))
const progressPercent = computed(() => {
  const total = Math.max(1, durationMinutes.value * 60)
  return Math.min(100, Math.round((elapsedSeconds.value / total) * 100))
})
const canRecord = computed(() => isRecordable(elapsedSeconds.value))
const recordedLabel = computed(() => recordLabel(sessionMinutes(elapsedSeconds.value)))
const isCustomDuration = computed(() => !FOCUS_PRESET_MINUTES.includes(durationMinutes.value))
const phaseLabel = computed(() => {
  if (phase.value === 'running') return `正在专注 ${recordedLabel.value}`
  if (phase.value === 'paused') return `已暂停于 ${recordedLabel.value}`
  if (phase.value === 'finished') return `本次共 ${recordedLabel.value}`
  return `准备开始 · 从 ${clock.value} 倒计时`
})

function stopTicker() {
  if (ticker) {
    clearInterval(ticker)
    ticker = null
  }
}

function tick() {
  elapsedSeconds.value = activeElapsedSeconds(accumulatedSeconds, startedAtMs, performance.now(), durationMinutes.value * 60)
  if (elapsedSeconds.value >= durationMinutes.value * 60) {
    stopTicker()
    elapsedSeconds.value = durationMinutes.value * 60
    phase.value = 'finished'
  }
}

function startTimer() {
  if (recording.value || phase.value === 'running' || (phase.value === 'finished' && canRecord.value)) return
  if (!selectedTask.value) {
    errorMessage.value = '请先选择一个专注的任务'
    return
  }
  errorMessage.value = ''
  notice.value = ''
  stopTicker()
  accumulatedSeconds = elapsedSeconds.value
  startedAtMs = performance.now()
  phase.value = 'running'
  ticker = setInterval(tick, 1000)
}

function pauseTimer() {
  tick()
  stopTicker()
  if (phase.value !== 'finished') phase.value = 'paused'
}

function stopTimer() {
  if (phase.value === 'running') tick()
  stopTicker()
  phase.value = 'finished'
}

function resetTimer() {
  if (recording.value) return
  stopTicker()
  elapsedSeconds.value = 0
  phase.value = 'idle'
}

function applyPreset(minutes) {
  if (sessionLocked.value) return
  durationMinutes.value = minutes
  resetTimer()
}

function applyCustomMinutes() {
  if (sessionLocked.value) return
  const normalized = normalizeCustomMinutes(customMinutesDraft.value)
  if (normalized === null) {
    customMinutesDraft.value = ''
    errorMessage.value = '自定义时长需在 15 到 240 分钟之间'
    return
  }
  errorMessage.value = ''
  customMinutesDraft.value = String(normalized)
  applyPreset(normalized)
}

function taskBaseline(task) {
  return editRequestConfig({ id: task.id, navigation_key: task.navigation_key, revision: task.revision })
}

async function record(asComplete) {
  const task = selectedTask.value
  if (!task || recording.value || phase.value !== 'finished') return
  const minutes = sessionMinutes(elapsedSeconds.value)
  if (!isRecordable(elapsedSeconds.value)) return
  recording.value = true
  errorMessage.value = ''
  const actual = mergeActualMinutes(task.actual_minutes, minutes)
  const config = taskBaseline(task)
  try {
    if (asComplete) {
      await http.post(`/tasks/${task.id}/complete`, { actual_minutes: actual }, config)
    } else {
      await tasksApi.update(task.id, { actual_minutes: actual }, config)
    }
    notice.value = asComplete ? `已完成「${task.name}」，记录 ${recordLabel(minutes)}` : `已记录 ${recordLabel(minutes)}`
    // The write succeeded; consume the session before a refresh can fail.
    stopTicker()
    elapsedSeconds.value = 0
    phase.value = 'idle'
    await loadTasks()
  } catch (error) {
    errorMessage.value = error?.code === 'EDIT_CONFLICT'
      ? '任务刚被其他页面更新过，请返回任务页刷新后再试'
      : error?.message || '记录失败，请稍后重试'
  } finally {
    recording.value = false
  }
}

async function loadTasks() {
  const request = ++taskRequestId
  loading.value = true
  loadFailed.value = false
  errorMessage.value = ''
  try {
    const listed = await tasksApi.list()
    if (request !== taskRequestId) return
    tasks.value = listed
    if (incomingFocusPending) {
      incomingFocusPending = false
      const incoming = resolveFocusTask(listed, route.query)
      if (incoming.requested) {
        selectedId.value = incoming.task?.id ?? null
        if (!incoming.task) errorMessage.value = '原任务已完成、移除或变更，请重新选择要专注的任务。'
        if (incoming.start) {
          const query = { ...route.query }
          delete query.start
          await router.replace({ path: route.path, query })
          startTimer()
        }
        return
      }
    }
    if (!pendingTasks.value.some((task) => task.id === selectedId.value)) {
      selectedId.value = pendingTasks.value[0]?.id ?? null
    }
  } catch (error) {
    if (request !== taskRequestId) return
    loadFailed.value = true
    errorMessage.value = error?.message || '无法读取任务，请确认服务已启动'
  } finally {
    if (request === taskRequestId) loading.value = false
  }
}

async function startCreatedTask(task) {
  await loadTasks()
  if (loadFailed.value) return
  selectedId.value = pendingTasks.value.find(item => item.id === task?.id && item.navigation_key === task?.navigation_key)?.id ?? null
  startTimer()
}

function protectUnsavedSession(event) {
  if (!sessionLocked.value) return
  event.preventDefault()
  event.returnValue = ''
}

async function canLeaveFocus() {
  // Expired sessions and completed sign-outs must always reach the public pages.
  if (!authSession.user) {
    ElMessageBox.close()
    return true
  }
  if (recording.value) {
    notice.value = '正在保存专注记录，完成后再离开。'
    return false
  }
  if (!sessionLocked.value) return true
  try {
    await ElMessageBox.confirm('本次专注尚未记录，离开后计时会丢失。', '离开专注计时？', {
      confirmButtonText: '放弃并离开',
      cancelButtonText: '继续专注',
      type: 'warning',
      autofocus: false,
    })
    return true
  } catch {
    return false
  }
}

onBeforeRouteLeave(canLeaveFocus)
onBeforeRouteUpdate((to, from) => {
  if (to.query.task_id === from.query.task_id && to.query.navigation_key === from.query.navigation_key) return true
  return canLeaveFocus()
})
watch(() => [route.query.task_id, route.query.navigation_key], () => {
  resetTimer()
  incomingFocusPending = true
  loadTasks()
})

onMounted(() => {
  loadTasks()
  window.addEventListener('beforeunload', protectUnsavedSession)
})

onUnmounted(() => {
  stopTicker()
  window.removeEventListener('beforeunload', protectUnsavedSession)
})
</script>

<style scoped>
.focus-record-icon { display: grid; place-items: center; width: 48px; height: 48px; margin: 0 0 22px; color: var(--ledger-primary); border-radius: 50%; background: #eaf2ed; font-size: 25px; }
.focus-record-help { margin-top: 16px; }
.focus-record-help summary { min-height: 44px; padding: 12px 0; color: var(--ledger-link); font-size: 12px; cursor: pointer; }
.focus-record-help small { margin-top: 0; }
.focus-page { max-width: 980px; margin: 0 auto; padding: 4px 0 32px; }
.focus-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; margin-bottom: 20px; }
.focus-kicker { margin: 0 0 6px; color: var(--ledger-indigo); font-size: 12px; font-weight: 750; }
.focus-header h1 { margin: 0; color: var(--ledger-ink); font-family: var(--font-display); font-size: clamp(26px, 2.5vw, 32px); font-weight: 750; letter-spacing: -.025em; }
.focus-lead { margin: 9px 0 0; max-width: 560px; color: var(--ledger-muted); font-size: 14px; line-height: 1.75; }
.focus-back { flex: 0 0 auto; min-height: 44px; display: inline-flex; align-items: center; padding: 0 15px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; font-size: 13px; font-weight: 700; }
.focus-back:hover { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.focus-alert { margin-bottom: 14px; padding: 11px 14px; border: 1px solid #e3b6b6; border-radius: 10px; background: #fdf1f1; color: #8c3b3b; font-size: 13px; }
.focus-notice { margin-bottom: 14px; padding: 11px 14px; border: 1px solid var(--ledger-line); border-radius: 10px; background: var(--ledger-paper); color: var(--ledger-ink); font-size: 14px; }
.focus-board { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(260px, .75fr); gap: 28px; padding: 24px; border: 1px solid var(--ledger-line); border-radius: 12px; background: var(--ledger-paper); transition: border-color .2s ease; }
.focus-board.is-running { border-color: var(--ledger-indigo); }
.focus-board.is-loading, .focus-board.is-empty { display: block; color: var(--ledger-muted); font-size: 14px; }
.focus-board.is-empty h3 { margin: 0 0 8px; color: var(--ledger-ink); }
.focus-board.is-empty p { margin: 0 0 18px; }
.focus-field { display: grid; gap: 7px; }
.focus-field span { color: var(--ledger-muted); font-size: 12px; font-weight: 700; }
.focus-field select { min-height: 44px; padding: 0 12px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; color: var(--ledger-ink); font-size: 14px; }
.preset-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.preset-chip { min-height: 44px; padding: 0 14px; border: 1px solid var(--ledger-line); border-radius: 7px; background: #fff; color: var(--ledger-muted); font-size: 13px; font-weight: 600; cursor: pointer; }
.preset-chip.active { color: #fff; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.preset-chip:disabled { opacity: .55; cursor: default; }
.custom-minutes { display: inline-flex; align-items: center; gap: 5px; min-height: 44px; padding: 0 11px; border: 1px solid var(--ledger-line); border-radius: 7px; color: var(--ledger-muted); font-size: 13px; font-weight: 600; }
.custom-minutes.active { color: #fff; border-style: solid; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.custom-minutes input { width: 58px; border: 0; background: transparent; color: inherit; font-size: 12.5px; font-weight: 700; text-align: center; }
.custom-minutes input:disabled { opacity: .55; }
.focus-clock { margin: 30px 0 14px; color: var(--ledger-ink); font-family: var(--font-ui); font-size: clamp(68px, 7vw, 92px); font-weight: 650; line-height: 1.05; font-variant-numeric: tabular-nums; letter-spacing: -.03em; }
.is-running .focus-clock { color: var(--ledger-indigo); animation: focus-state-settle .32s ease-out; }
.is-finished .focus-record { border-color: #c8ddd1; animation: focus-state-settle .32s ease-out; }
.focus-track { height: 5px; overflow: hidden; border-radius: 99px; background: #e5ede8; }
.focus-fill { display: block; width: 100%; height: 100%; border-radius: 99px; background: var(--ledger-indigo); transform-origin: left; transition: transform 1s linear; }
.focus-meta { margin: 10px 0 0; color: var(--ledger-muted); font-size: 12px; font-weight: 600; }
.control-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
.focus-action { min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 0 18px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; color: var(--ledger-ink); font-size: 13px; font-weight: 750; cursor: pointer; }
.focus-action:hover:not(:disabled) { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.focus-action.primary { color: #fff; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.focus-action.primary:hover:not(:disabled) { color: #fff; border-color: var(--ledger-indigo); filter: brightness(1.05); }
.focus-action:disabled { opacity: .55; cursor: default; }
.focus-action.quiet { border-style: dashed; }
.focus-record { align-self: stretch; padding: 8px 0 8px 24px; border-left: 1px solid var(--ledger-line); }
.focus-record h3 { margin: 0 0 9px; color: var(--ledger-ink); font-size: 15px; }
.focus-record p { margin: 0; color: var(--ledger-muted); font-size: 12.5px; line-height: 1.8; }
.focus-record small { display: block; margin-top: 14px; color: var(--ledger-muted); font-size: 12px; line-height: 1.75; }
.record-actions { display: grid; gap: 9px; margin-top: 15px; }
@keyframes focus-state-settle { from { opacity: .7; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 760px) {
  .focus-page { padding: 0 0 28px; }
  .focus-header { flex-direction: column; }
  .focus-board { grid-template-columns: 1fr; padding: 18px; }
  .focus-record { padding: 20px 0 0; border-left: 0; border-top: 1px solid var(--ledger-line); }
  .focus-clock { font-size: 52px; }
}
@media (prefers-reduced-motion: reduce) { .focus-board, .focus-fill { transition: none; } .is-running .focus-clock, .is-finished .focus-record { animation: none; } }
</style>
