<template>
  <div class="focus-page">
    <header class="focus-header">
      <div>
        <h1>专注计时</h1>
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

    <section v-else-if="pendingTasks.length === 0 && !sessionLocked" class="focus-board is-empty">
      <h3>现在没有待办任务</h3>
      <p>记下要做的事，直接开始 25 分钟专注。</p>
      <QuickTaskAdd submit-label="添加并开始" @created="startCreatedTask" />
    </section>

    <section v-else class="focus-board" :class="{ 'is-running': phase === 'running', 'is-finished': phase === 'finished' }">
      <div class="focus-setup">
        <label class="focus-field">
          <span>这次要专注什么？</span>
          <select v-model="selectedId" :disabled="sessionLocked" data-testid="focus-task-select" @change="errorMessage = ''">
            <option v-if="selectedId === null" :value="null" disabled>请选择要专注的任务</option>
            <option v-if="activeSession && !selectedTask" :value="activeSession.taskId" disabled>{{ activeSession.taskName }}</option>
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
              placeholder="自定"
              aria-label="自定义专注分钟（15 到 240）"
              :disabled="sessionLocked"
              @change="applyCustomMinutes"
            >
            分钟
          </label>
        </div>

      </div>
      <div class="dial-panel">
        <div class="dial">
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <circle class="dial-track" cx="60" cy="60" r="54" />
            <circle class="dial-remaining" cx="60" cy="60" r="54" pathLength="100" stroke-dasharray="100" :stroke-dashoffset="progressPercent" transform="rotate(-90 60 60)" />
          </svg>
          <div class="dial-readout">
            <span class="dial-state">{{ phaseLabel }}</span>
            <p class="focus-clock" role="timer" aria-label="专注剩余时间">{{ clock }}</p>
            <span class="dial-target">目标 {{ durationMinutes }} 分钟</span>
          </div>
        </div>

        <div class="control-row">
          <button v-if="phase === 'idle' || phase === 'paused'" class="focus-action primary" type="button" :disabled="!selectedTask" @click="startTimer">
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
          <h3>记录专注用时</h3>
          <p>满 15 分钟后，可确认记录用时。</p>
           <details class="focus-record-help"><summary>计时与保存说明</summary><small>暂停期间停止计时。同一标签页内切换页面或刷新后可继续。</small></details>
        </template>
        <template v-else-if="!canRecord">
          <h3>这次不足 15 分钟</h3>
          <p>系统最少记录 15 分钟。可以放弃本次，或继续专注到 15 分钟以上。</p>
          <div class="record-actions">
            <button class="focus-action primary" type="button" :disabled="!selectedTask" @click="startTimer">继续专注</button>
            <button class="focus-action quiet" type="button" @click="resetTimer">放弃本次</button>
          </div>
        </template>
        <template v-else>
          <h3>本次专注 {{ recordedLabel }}</h3>
          <p>把本次用时记入「{{ activeSession?.taskName }}」。</p>
          <p v-if="!selectedTask && !pendingRecord">这项待办已发生变更，请核对任务或放弃本次计时。</p>
          <p>本次 {{ recordedLabel }} 会累加到已有记录；仅记录用时不会完成任务。</p>
          <p v-if="pendingRecord">上次保存结果尚未确认，请重试同一操作，避免重复记录。</p>
          <div class="record-actions">
            <button class="focus-action primary" type="button" :disabled="recording || (pendingRecord ? !pendingRecord.asComplete : !selectedTask)" @click="record(true)">
              {{ recording ? '正在记录' : '完成并记录' }}
            </button>
            <button class="focus-action" type="button" :disabled="recording || (pendingRecord ? pendingRecord.asComplete : !selectedTask)" @click="record(false)">仅记录用时</button>
          </div>
        </template>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Timer } from '@element-plus/icons-vue'

import http from '../api/http'
import { tasksApi } from '../api'
import { useFocusSession } from '../composables/useFocusSession'
import {
  FOCUS_PRESET_MINUTES,
  formatClock,
  isRecordable,
  normalizeCustomMinutes,
  recordLabel,
  sessionMinutes,
} from '../utils/focusTimer'
import { buildFocusSaveAttempt, sendFocusSaveAttempt } from '../utils/focusSave'
import QuickTaskAdd from '../components/QuickTaskAdd.vue'
import { orderedPendingTasks, resolveFocusTask } from '../utils/dailyWorkflow'

const route = useRoute()
const router = useRouter()
const {
  session: activeSession, recording, elapsed: elapsedSeconds,
  start: startSession, pause: pauseSession, reset: resetSession, rememberAttempt,
} = useFocusSession()
let incomingFocusPending = true
let taskRequestId = 0

const loading = ref(true)
const loadFailed = ref(false)
const errorMessage = ref('')
const tasks = ref([])
const selectedId = ref(null)
const chosenDuration = ref(activeSession.value?.duration || 25)
const durationMinutes = computed(() => activeSession.value?.duration || chosenDuration.value)
const customMinutesDraft = ref('')
const phase = computed(() => activeSession.value?.phase || 'idle')
const pendingRecord = computed(() => activeSession.value?.attempt)
const notice = ref('')

const sessionLocked = computed(() => phase.value !== 'idle' || recording.value)
const pendingTasks = computed(() => orderedPendingTasks(tasks.value))
const selectedTask = computed(() => {
  const current = activeSession.value
  return pendingTasks.value.find(task => current
    ? task.id === current.taskId && task.navigation_key === current.taskKey
    : task.id === selectedId.value) || null
})
const clock = computed(() => formatClock(Math.max(0, durationMinutes.value * 60 - elapsedSeconds.value)))
const progressPercent = computed(() => {
  const total = Math.max(1, durationMinutes.value * 60)
  return Math.min(100, (elapsedSeconds.value / total) * 100)
})
const canRecord = computed(() => isRecordable(elapsedSeconds.value))
const recordedLabel = computed(() => recordLabel(sessionMinutes(elapsedSeconds.value)))
const isCustomDuration = computed(() => !FOCUS_PRESET_MINUTES.includes(durationMinutes.value))
const phaseLabel = computed(() => ({ idle: '准备开始', running: '专注中', paused: '已暂停', finished: '本次已结束' })[phase.value])

function startTimer() {
  if (recording.value || phase.value === 'running' || (phase.value === 'finished' && canRecord.value)) return
  if (!selectedTask.value) {
    errorMessage.value = '请先选择一个专注的任务'
    return
  }
  errorMessage.value = ''
  notice.value = ''
  startSession(selectedTask.value, durationMinutes.value)
}

function pauseTimer() {
  pauseSession()
}

function stopTimer() {
  pauseSession('finished')
}

function resetTimer() {
  if (recording.value) return
  resetSession()
  if (!pendingTasks.value.some(task => task.id === selectedId.value)) {
    selectedId.value = pendingTasks.value[0]?.id ?? null
  }
}

function applyPreset(minutes) {
  if (sessionLocked.value) return
  chosenDuration.value = minutes
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

async function record(asComplete) {
  const task = selectedTask.value
  if ((!task && !pendingRecord.value) || recording.value || phase.value !== 'finished') return
  const minutes = sessionMinutes(elapsedSeconds.value)
  if (!isRecordable(elapsedSeconds.value)) return
  if (pendingRecord.value && pendingRecord.value.asComplete !== asComplete) return
  recording.value = true
  errorMessage.value = ''
  let attempt = pendingRecord.value
  try {
    if (!attempt) {
      const key = globalThis.crypto?.randomUUID?.() || `focus-${Date.now()}-${Math.random().toString(36).slice(2)}`
      attempt = buildFocusSaveAttempt(task, minutes, asComplete, key)
      rememberAttempt(attempt)
    }
    await sendFocusSaveAttempt(attempt, {
      recordFocus: tasksApi.recordFocusSession,
      completeFocus: (id, payload, config) => http.post(`/tasks/${id}/complete`, payload, config),
    })
    if (pendingRecord.value !== attempt) return
    notice.value = asComplete ? `已完成「${attempt.taskName}」，记录 ${recordLabel(minutes)}` : `已记录 ${recordLabel(minutes)}`
    // The write succeeded; consume the session before a refresh can fail.
    resetSession()
    await loadTasks()
  } catch (error) {
    errorMessage.value = error?.code === 'EDIT_CONFLICT'
      ? '任务刚被其他页面更新过，请返回任务页刷新后再试'
      : error?.message || '记录失败，请稍后重试'
  } finally {
    if (!pendingRecord.value || pendingRecord.value === attempt) recording.value = false
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
    if (activeSession.value) {
      incomingFocusPending = false
      selectedId.value = activeSession.value.taskId
      if (route.query.start) {
        notice.value = '已有一次专注计时。记录或放弃后，可以开始新的待办。'
        const query = { ...route.query }
        delete query.start
        await router.replace({ path: route.path, query })
      }
      return
    }
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

watch(() => [route.query.task_id, route.query.navigation_key], () => {
  incomingFocusPending = true
  loadTasks()
})

onMounted(loadTasks)
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
.focus-board { display: grid; grid-template-columns: minmax(0, 1.18fr) minmax(260px, 1fr); grid-template-areas: 'dial setup' 'dial record'; grid-template-rows: auto 1fr; gap: 24px; padding: 20px; border: 1px solid var(--ledger-line); border-radius: var(--ledger-radius); box-shadow: var(--ledger-shadow); background: var(--ledger-paper); }
.focus-setup { grid-area: setup; min-width: 0; padding-top: 12px; }
.dial-panel { grid-area: dial; display: grid; justify-items: center; align-content: center; min-width: 0; gap: 16px; padding: clamp(18px, 3vw, 32px); background: #193f34; color: #fff; border-radius: 12px; }
.dial { display: grid; place-items: center; width: min(100%, 280px); aspect-ratio: 1; }
.dial > * { grid-area: 1 / 1; }
.dial svg { width: 100%; fill: none; stroke-width: 2.4; }
.dial-track { stroke: #47675a; }
.dial-remaining { stroke: #c7dcc4; stroke-linecap: round; transition: stroke-dashoffset .3s linear; }
.is-running .dial-remaining { stroke: #dcecc3; }
.dial-readout { display: grid; justify-items: center; gap: 6px; }
.dial-state, .dial-target { color: #d6e4db; font-size: 13px; }
.focus-board.is-loading, .focus-board.is-empty { display: block; color: var(--ledger-muted); font-size: 14px; }
.focus-board.is-empty h3 { margin: 0 0 8px; color: var(--ledger-ink); }
.focus-board.is-empty p { margin: 0 0 18px; }
.focus-field { display: grid; gap: 7px; }
.focus-field span { color: var(--ledger-muted); font-size: 12px; font-weight: 700; }
.focus-field select { min-height: 44px; padding: 0 12px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; color: var(--ledger-ink); font-size: 14px; }
.preset-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.preset-chip { min-height: 44px; padding: 0 14px; border: 1px solid var(--ledger-line); border-radius: 7px; background: #fff; color: var(--ledger-muted); font-size: 13px; font-weight: 600; cursor: pointer; }
.preset-chip.active { color: #fff; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.preset-chip:disabled { cursor: default; }
.preset-chip:disabled:not(.active) { color: var(--ledger-muted); background: var(--ledger-canvas); }
.custom-minutes { display: inline-flex; align-items: center; gap: 5px; min-height: 44px; padding: 0 11px; border: 1px solid var(--ledger-line); border-radius: 7px; color: var(--ledger-muted); font-size: 13px; font-weight: 600; }
.custom-minutes.active { color: #fff; border-style: solid; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.custom-minutes input { width: 58px; border: 0; background: transparent; color: inherit; font-size: 12.5px; font-weight: 700; text-align: center; }
.custom-minutes input:disabled { opacity: .55; }
.focus-clock { margin: 0; font: 600 clamp(46px, 5vw, 64px)/1.15 var(--font-ui); font-variant-numeric: tabular-nums; }
.is-finished .focus-record { border-color: #c8ddd1; animation: focus-state-settle .32s ease-out; }
.control-row { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
.dial-panel .focus-action { color: #fff; background: transparent; border-color: #8ea99c; }
.dial-panel .focus-action.primary, .dial-panel .focus-action:hover:not(:disabled) { color: #193f34; background: #e7f1e4; border-color: #e7f1e4; }
.focus-action { min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 0 18px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; color: var(--ledger-ink); font-size: 13px; font-weight: 750; cursor: pointer; }
.focus-action:hover:not(:disabled) { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.focus-action.primary { color: #fff; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.focus-action.primary:hover:not(:disabled) { color: #fff; border-color: var(--ledger-indigo); filter: brightness(1.05); }
.focus-action:disabled { opacity: .55; cursor: default; }
.focus-action.quiet { border-style: dashed; }
.focus-record { grid-area: record; padding-top: 20px; border-top: 1px solid var(--ledger-line); }
.focus-record h3 { margin: 0 0 9px; color: var(--ledger-ink); font-size: 15px; }
.focus-record p { margin: 0; color: var(--ledger-muted); font-size: 12.5px; line-height: 1.8; }
.focus-record small { display: block; margin-top: 14px; color: var(--ledger-muted); font-size: 12px; line-height: 1.75; }
.record-actions { display: grid; gap: 9px; margin-top: 15px; }
@keyframes focus-state-settle { from { opacity: .7; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 760px) {
  .focus-page { padding: 0 0 28px; }
  .focus-header { align-items: center; }
  .focus-board { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto; grid-template-areas: 'setup' 'dial' 'record'; gap: 16px; padding: 14px; }
  .focus-setup { padding: 0; }
  .dial { width: min(100%, 214px); }
  .focus-record { padding: 20px 0 0; border-left: 0; border-top: 1px solid var(--ledger-line); }
  .focus-clock { font-size: 52px; }
}
@media (prefers-reduced-motion: reduce) { .dial-remaining { transition: none; } .is-finished .focus-record { animation: none; } }
</style>
