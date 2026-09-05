<template>
  <div class="focus-page">
    <header class="focus-header">
      <div>
        <p class="focus-kicker">FOCUS / 专注一段，再记录</p>
        <h2>专注计时</h2>
        <p class="focus-lead">选一个任务开始专注；结束后把真实用时记回任务，学习节奏建议会因此更准。</p>
      </div>
      <router-link class="focus-back" to="/tasks">返回截止任务</router-link>
    </header>

    <div v-if="errorMessage" class="focus-alert" role="alert">{{ errorMessage }}</div>

    <section v-if="loading" class="focus-board is-loading" aria-live="polite">正在读取待办任务…</section>

    <section v-else-if="pendingTasks.length === 0" class="focus-board is-empty">
      <h3>现在没有待办任务</h3>
      <p>先到截止任务页确认或创建任务，再回来开始专注。</p>
      <router-link class="focus-action primary" to="/tasks">去任务页</router-link>
    </section>

    <section v-else class="focus-board">
      <div class="focus-main">
        <label class="focus-field">
          <span>专注的任务</span>
          <select v-model="selectedId" :disabled="phase === 'running'" data-testid="focus-task-select">
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
            :disabled="phase === 'running'"
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
              :disabled="phase === 'running'"
              @change="applyCustomMinutes"
            >
            分钟
          </label>
        </div>

        <p class="focus-clock" role="timer" aria-label="专注剩余时间">{{ clock }}</p>
        <div class="focus-track" aria-hidden="true">
          <span class="focus-fill" :style="{ width: progressPercent + '%' }"></span>
        </div>
        <p class="focus-meta">已专注 {{ recordedLabel }} · 目标 {{ durationMinutes }} 分钟</p>

        <div class="control-row">
          <button v-if="phase !== 'running'" class="focus-action primary" type="button" :disabled="phase === 'finished'" @click="startTimer">
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
          <button v-if="phase === 'finished' || phase === 'paused'" class="focus-action quiet" type="button" @click="resetTimer">
            放弃本次
          </button>
        </div>
      </div>

      <aside class="focus-record" aria-live="polite">
        <template v-if="phase !== 'finished'">
          <h3>结束后会怎样</h3>
          <p>专注满 15 分钟才能记录用时；可以选择「完成并记录」或「仅记录用时」。记录会进入课程校准，让后续估时与节奏建议更贴近你的真实速度。</p>
          <small>计时只在当前页面进行，离开页面会停止。</small>
        </template>
        <template v-else-if="!canRecord">
          <h3>这次不足 15 分钟</h3>
          <p>系统最少记录 15 分钟。可以放弃本次，或继续专注到 15 分钟以上。</p>
          <button class="focus-action" type="button" @click="resetTimer">知道了，放弃本次</button>
        </template>
        <template v-else>
          <h3>本次专注 {{ recordedLabel }}</h3>
          <p>把真实用时记回「{{ selectedTask?.name }}」，来源标记为专注计时。</p>
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
import { computed, onMounted, onUnmounted, ref } from 'vue'

import http from '../api/http'
import { tasksApi } from '../api'
import {
  FOCUS_PRESET_MINUTES,
  formatClock,
  isRecordable,
  mergeActualMinutes,
  normalizeCustomMinutes,
  recordLabel,
  sessionMinutes,
} from '../utils/focusTimer'
import { editRequestConfig } from '../utils/editPrecondition'

const loading = ref(true)
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

const pendingTasks = computed(() => tasks.value.filter((task) => task.status !== 'completed'))
const selectedTask = computed(() => pendingTasks.value.find((task) => task.id === selectedId.value) || null)
const clock = computed(() => formatClock(Math.max(0, durationMinutes.value * 60 - elapsedSeconds.value)))
const progressPercent = computed(() => {
  const total = Math.max(1, durationMinutes.value * 60)
  return Math.min(100, Math.round((elapsedSeconds.value / total) * 100))
})
const canRecord = computed(() => isRecordable(elapsedSeconds.value))
const recordedLabel = computed(() => recordLabel(sessionMinutes(elapsedSeconds.value)))
const isCustomDuration = computed(() => !FOCUS_PRESET_MINUTES.includes(durationMinutes.value))

function stopTicker() {
  if (ticker) {
    clearInterval(ticker)
    ticker = null
  }
}

function tick() {
  elapsedSeconds.value += 1
  if (elapsedSeconds.value >= durationMinutes.value * 60) {
    stopTicker()
    elapsedSeconds.value = durationMinutes.value * 60
    phase.value = 'finished'
  }
}

function startTimer() {
  if (!selectedTask.value) {
    errorMessage.value = '请先选择一个专注的任务'
    return
  }
  errorMessage.value = ''
  notice.value = ''
  stopTicker()
  phase.value = 'running'
  ticker = setInterval(tick, 1000)
}

function pauseTimer() {
  stopTicker()
  phase.value = 'paused'
}

function stopTimer() {
  stopTicker()
  phase.value = 'finished'
}

function resetTimer() {
  stopTicker()
  elapsedSeconds.value = 0
  phase.value = 'idle'
}

function applyPreset(minutes) {
  if (phase.value === 'running') return
  durationMinutes.value = minutes
  resetTimer()
}

function applyCustomMinutes() {
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
  if (!task || recording.value) return
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
    await loadTasks()
    resetTimer()
  } catch (error) {
    errorMessage.value = error?.code === 'EDIT_CONFLICT'
      ? '任务刚被其他页面更新过，请返回任务页刷新后再试'
      : error?.message || '记录失败，请稍后重试'
  } finally {
    recording.value = false
  }
}

async function loadTasks() {
  loading.value = true
  errorMessage.value = ''
  try {
    tasks.value = await tasksApi.list()
    if (!pendingTasks.value.some((task) => task.id === selectedId.value)) {
      selectedId.value = pendingTasks.value[0]?.id ?? null
    }
  } catch (error) {
    errorMessage.value = error?.message || '无法读取任务，请确认服务已启动'
  } finally {
    loading.value = false
  }
}

onMounted(loadTasks)

onUnmounted(stopTicker)
</script>

<style scoped>
.focus-page { max-width: 980px; margin: 0 auto; padding: 26px 20px 60px; }
.focus-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; margin-bottom: 20px; }
.focus-kicker { margin: 0 0 6px; color: var(--ledger-indigo); font: 700 11px/1.4 Bahnschrift, "Microsoft YaHei", sans-serif; letter-spacing: .1em; }
.focus-header h2 { margin: 0; color: var(--ledger-ink); font-family: "Aptos Display", "Microsoft YaHei", sans-serif; font-size: 30px; }
.focus-lead { margin: 9px 0 0; max-width: 520px; color: var(--ledger-muted); font-size: 13px; line-height: 1.8; }
.focus-back { flex: 0 0 auto; min-height: 44px; display: inline-flex; align-items: center; padding: 0 15px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; font-size: 13px; font-weight: 700; }
.focus-back:hover { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.focus-alert { margin-bottom: 14px; padding: 11px 14px; border: 1px solid #e3b6b6; border-radius: 10px; background: #fdf1f1; color: #8c3b3b; font-size: 13px; }
.focus-board { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(260px, .75fr); gap: 16px; padding: 24px; border: 1px solid var(--ledger-line); border-radius: 16px; background: var(--ledger-paper); box-shadow: var(--ledger-shadow); }
.focus-board.is-loading, .focus-board.is-empty { display: block; color: var(--ledger-muted); font-size: 14px; }
.focus-board.is-empty h3 { margin: 0 0 8px; color: var(--ledger-ink); }
.focus-board.is-empty p { margin: 0 0 18px; }
.focus-field { display: grid; gap: 7px; }
.focus-field span { color: #51617f; font-size: 12px; font-weight: 700; }
.focus-field select { min-height: 44px; padding: 0 12px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; color: var(--ledger-ink); font-size: 14px; }
.preset-row { display: flex; gap: 8px; margin-top: 14px; }
.preset-chip { min-height: 38px; padding: 0 14px; border: 1px solid var(--ledger-line); border-radius: 99px; background: #fff; color: #51617f; font-size: 12px; font-weight: 700; cursor: pointer; }
.preset-chip.active { color: #fff; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.preset-chip:disabled { opacity: .55; cursor: default; }
.custom-minutes { display: inline-flex; align-items: center; gap: 5px; min-height: 38px; padding: 0 11px; border: 1px dashed #cbd4e0; border-radius: 99px; color: #51617f; font-size: 12px; font-weight: 650; }
.custom-minutes.active { color: #fff; border-style: solid; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.custom-minutes input { width: 58px; border: 0; background: transparent; color: inherit; font-size: 12.5px; font-weight: 700; text-align: center; }
.custom-minutes input:disabled { opacity: .55; }
.focus-clock { margin: 26px 0 10px; color: var(--ledger-ink); font: 700 64px/1.05 Bahnschrift, "Segoe UI", sans-serif; font-variant-numeric: tabular-nums; letter-spacing: .02em; }
.focus-track { height: 8px; overflow: hidden; border-radius: 99px; background: #e7ebf3; }
.focus-fill { display: block; height: 100%; border-radius: 99px; background: var(--ledger-indigo); transition: width 1s linear; }
.focus-meta { margin: 10px 0 0; color: var(--ledger-muted); font-size: 12px; }
.control-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
.focus-action { min-height: 44px; display: inline-flex; align-items: center; justify-content: center; padding: 0 18px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; color: #3b4a66; font-size: 13px; font-weight: 750; cursor: pointer; }
.focus-action:hover:not(:disabled) { color: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.focus-action.primary { color: #fff; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.focus-action.primary:hover:not(:disabled) { color: #fff; border-color: var(--ledger-indigo); filter: brightness(1.05); }
.focus-action:disabled { opacity: .55; cursor: default; }
.focus-action.quiet { border-style: dashed; }
.focus-record { align-self: start; padding: 18px; border: 1px solid #d8def0; border-radius: 13px; background: #f4f6ff; }
.focus-record h3 { margin: 0 0 9px; color: var(--ledger-ink); font-size: 15px; }
.focus-record p { margin: 0; color: #55627e; font-size: 12.5px; line-height: 1.8; }
.focus-record small { display: block; margin-top: 11px; color: #8593ad; font-size: 11px; }
.record-actions { display: grid; gap: 9px; margin-top: 15px; }
@media (max-width: 760px) {
  .focus-page { padding: 18px 14px 46px; }
  .focus-header { flex-direction: column; }
  .focus-board { grid-template-columns: 1fr; padding: 18px; }
  .focus-clock { font-size: 52px; }
}
@media (prefers-reduced-motion: reduce) { .focus-fill { transition: none; } }
</style>
