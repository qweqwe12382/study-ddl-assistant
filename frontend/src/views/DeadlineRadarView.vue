<template>
  <div class="radar-page">
    <header class="radar-hero">
      <div class="radar-hero__copy">
        <h1>DDL 应变台</h1>
        <p class="radar-hero__lede">作业提前、延期或取消了？先看对本周的影响，核对后再更新任务。</p>
      </div>
      <router-link class="radar-back" to="/tasks">返回截止任务</router-link>
    </header>

    <section class="radar-input" aria-labelledby="radar-input-title">
      <div class="radar-input__heading">
        <div>
          <h2 id="radar-input-title">选择任务，粘贴变更通知</h2>
        </div>
        <span class="radar-safety">预览不会修改任务</span>
      </div>

      <form class="radar-form" @submit.prevent="previewChange">
        <label class="radar-field">
          <span>要核对的原任务</span>
          <el-select
            v-model="selectedTaskId"
            filterable
            :loading="tasksLoading"
            :disabled="tasksLoading || !actionableTasks.length || previewLoading || applyLoading"
            :placeholder="tasksLoading ? '正在读取任务…' : actionableTasks.length ? '选择一项已有任务' : '暂无可变更任务'"
            aria-label="选择要关联的已有任务"
          >
            <el-option
              v-for="task in actionableTasks"
              :key="task.navigation_key"
              :label="taskOptionLabel(task)"
              :value="task.id"
            />
          </el-select>
        </label>

        <label class="radar-field radar-field--notice">
          <span>通知原文</span>
          <el-input
            v-model="noticeText"
            :disabled="previewLoading || applyLoading"
            type="textarea"
            :rows="5"
            maxlength="4000"
            show-word-limit
            resize="vertical"
            placeholder="例如：课程群通知，数据结构实验报告提交时间提前至 9 月 18 日 20:00，请互相转告。"
            aria-label="粘贴包含提前、延期、改期或取消表达的通知原文"
          />
        </label>

        <div class="radar-form__footer">
          <p>通知需明确说明提前、延期、改期或取消。仅有日期不会改动任务。</p>
          <el-button native-type="submit" type="primary" :loading="previewLoading" :disabled="!canPreview">
            生成变更预演
          </el-button>
        </div>
      </form>

      <div v-if="!tasksLoading && !tasksError && !actionableTasks.length" class="radar-empty" role="status">
        <p>还没有可以变更的任务。先记下一项任务，再来核对新的通知。</p>
        <router-link to="/tasks?action=create-task">记一项任务</router-link>
      </div>

      <div v-if="tasksError || radarError" class="radar-error" role="alert">
        <strong>{{ tasksError ? '任务读取失败' : '暂时不能生成预演' }}</strong>
        <span>{{ tasksError || radarError }}</span>
        <el-button v-if="tasksError" link type="primary" @click="loadTasks">重新读取</el-button>
      </div>
    </section>

    <Transition name="radar-reveal">
      <section v-if="preview" ref="previewElement" class="radar-result" aria-labelledby="radar-result-title">
        <div class="radar-result__heading">
          <div>
            <span class="radar-step">预演</span>
            <h2 id="radar-result-title">这次变更，会影响哪些安排？</h2>
          </div>
          <span class="radar-direction" :class="`is-${preview.impact.direction}`">{{ directionLabel(preview.impact) }}</span>
        </div>

        <ol class="radar-track">
          <li class="radar-station radar-station--evidence">
            <span class="radar-station__number">01</span>
            <div class="radar-station__body">
              <span class="radar-station__label">通知证据</span>
              <strong>{{ preview.evidence.marker }}</strong>
              <blockquote>{{ preview.evidence.quote }}</blockquote>
              <p v-if="preview.evidence.warnings?.length" class="radar-warning">解析提示：{{ preview.evidence.warnings.join('、') }}</p>
            </div>
          </li>

          <li class="radar-station radar-station--shift">
            <span class="radar-station__number">02</span>
            <div class="radar-station__body">
              <span class="radar-station__label">截止变化</span>
              <strong class="radar-task-name">{{ preview.task.name }}</strong>
              <div class="deadline-shift">
                <div>
                  <span>原截止</span>
                  <time>{{ formatRadarDate(preview.task.current_due_at) }}</time>
                </div>
                <span class="deadline-shift__arrow" aria-hidden="true">→</span>
                <div :class="{ 'is-cancel': preview.intent === 'cancel' }">
                  <span>{{ preview.intent === 'cancel' ? '通知结果' : '新截止' }}</span>
                  <time>{{ preview.intent === 'cancel' ? '任务取消' : formatRadarDate(preview.task.proposed_due_at) }}</time>
                </div>
              </div>
            </div>
          </li>

          <li class="radar-station radar-station--pressure">
            <span class="radar-station__number">03</span>
            <div class="radar-station__body">
              <span class="radar-station__label">七日压力</span>
              <strong>{{ preview.impact.summary }}</strong>
              <div class="pressure-legend" aria-hidden="true">
                <span><i class="is-before"></i>变更前</span>
                <span><i class="is-after"></i>变更后</span>
                <span><i class="is-capacity"></i>当日容量</span>
              </div>
              <div class="pressure-days" aria-label="未来七日任务压力对比">
                <div
                  v-for="day in preview.pressure_days"
                  :key="day.local_date"
                  class="pressure-day"
                  :class="{ 'is-affected': day.affected, 'is-overloaded': day.after_overload_minutes > 0 }"
                  :aria-label="pressureAriaLabel(day)"
                >
                  <span class="pressure-day__date">{{ shortDate(day.local_date) }}</span>
                  <div class="pressure-day__plot">
                    <i class="pressure-day__capacity" :style="capacityStyle(day)" aria-hidden="true"></i>
                    <span class="pressure-bar pressure-bar--before" :style="barStyle(day, 'before_minutes')"></span>
                    <span class="pressure-bar pressure-bar--after" :style="barStyle(day, 'after_minutes')"></span>
                  </div>
                  <strong>{{ day.after_minutes }}<small> 分</small></strong>
                  <span v-if="day.after_overload_minutes" class="pressure-day__overload">超 {{ day.after_overload_minutes }}</span>
                  <span v-else-if="day.affected" class="pressure-day__changed">有变化</span>
                  <span v-else class="pressure-day__quiet">—</span>
                </div>
              </div>
            </div>
          </li>

          <li class="radar-station radar-station--confirm">
            <span class="radar-station__number">04</span>
            <div class="radar-station__body">
              <span class="radar-station__label">确认执行</span>
              <strong>核对后确认更新</strong>
              <p>{{ confirmationCopy }}</p>
              <el-checkbox v-model="confirmed" :disabled="Boolean(executionResult)">
                我已核对通知证据与目标任务
              </el-checkbox>
              <el-button
                type="danger"
                :loading="applyLoading"
                :disabled="!confirmed || Boolean(executionResult)"
                @click="applyChange"
              >
                {{ preview.action_label }}
              </el-button>
            </div>
          </li>
        </ol>

        <details class="radar-basis">
          <summary>这次预演怎么算的？</summary>
          <dl>
            <div v-for="(value, key) in preview.calculation_basis" :key="key">
              <dt>{{ basisLabel(key) }}</dt>
              <dd>{{ value }}</dd>
            </div>
          </dl>
        </details>
      </section>
    </Transition>

    <Transition name="radar-reveal">
      <section v-if="executionResult" ref="receiptElement" class="radar-receipt" tabindex="-1" aria-labelledby="radar-receipt-title">
        <span class="radar-receipt__check" aria-hidden="true">✓</span>
        <div>
          <span class="radar-step">已执行 · 回执 {{ executionResult.receipt.id }}</span>
          <h2 id="radar-receipt-title">通知变更已经落到任务上</h2>
          <p>{{ executionResult.message }}</p>
          <p class="radar-receipt__meta">任务版本已更新为 {{ executionResult.task.revision }}；产生 {{ executionResult.plan_delta_count }} 条待确认的复习计划调整。</p>
        </div>
        <router-link to="/tasks">查看最新任务</router-link>
      </section>
    </Transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElCheckbox, ElInput, ElMessage, ElOption, ElSelect } from 'element-plus'

import { deadlineRadarApi, tasksApi } from '../api'
import {
  actionableDeadlineTasks as filterActionableDeadlineTasks,
  buildDeadlineRadarKey,
  deadlineRadarPayload,
  pressureBarWidth,
} from '../utils/deadlineRadar'
import { formatDateTime } from '../utils/format'

const tasks = ref([])
const tasksLoading = ref(false)
const tasksError = ref('')
const selectedTaskId = ref('')
const noticeText = ref('')
const previewLoading = ref(false)
const applyLoading = ref(false)
const radarError = ref('')
const preview = ref(null)
const previewPayload = ref(null)
const confirmed = ref(false)
const executionKey = ref('')
const executionResult = ref(null)
const previewElement = ref(null)
const receiptElement = ref(null)

const actionableTasks = computed(() => filterActionableDeadlineTasks(tasks.value))
const selectedTask = computed(() => actionableTasks.value.find((task) => task.id === selectedTaskId.value) || null)
const canPreview = computed(() => Boolean(
  selectedTask.value
  && noticeText.value.trim().length >= 4
  && !previewLoading.value
  && !applyLoading.value,
))
const confirmationCopy = computed(() => {
  if (!preview.value) return ''
  if (preview.value.intent === 'cancel') return '确认后任务会标记为已取消，并退出进行中统计与七日负荷；原记录和执行回执仍会保留。'
  return `确认后仅更新“${preview.value.task.name}”的截止时间；关联复习计划如需变化，会另行生成待确认建议。`
})

watch([selectedTaskId, noticeText], () => {
  preview.value = null
  previewPayload.value = null
  executionResult.value = null
  executionKey.value = ''
  confirmed.value = false
  radarError.value = ''
})

onMounted(loadTasks)

async function loadTasks() {
  tasksLoading.value = true
  tasksError.value = ''
  try {
    const result = await tasksApi.list()
    tasks.value = Array.isArray(result) ? result : []
    if (!actionableTasks.value.some((task) => task.id === selectedTaskId.value)) {
      selectedTaskId.value = ''
    }
  } catch (error) {
    tasksError.value = error?.message || '无法读取已有任务。'
  } finally {
    tasksLoading.value = false
  }
}

async function previewChange() {
  if (!canPreview.value) return
  const payload = deadlineRadarPayload(selectedTask.value, noticeText.value, new Date())
  if (!payload) {
    radarError.value = '请选择有效任务，并保留完整的通知原文。'
    return
  }
  previewLoading.value = true
  radarError.value = ''
  confirmed.value = false
  executionResult.value = null
  try {
    preview.value = await deadlineRadarApi.preview(payload)
    previewPayload.value = payload
    executionKey.value = buildDeadlineRadarKey(payload.task_id, randomToken())
    await nextTick()
    previewElement.value?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' })
  } catch (error) {
    preview.value = null
    previewPayload.value = null
    radarError.value = error?.message || '通知变更预演失败。'
  } finally {
    previewLoading.value = false
  }
}

async function applyChange() {
  if (applyLoading.value || !confirmed.value || !preview.value || !previewPayload.value || executionResult.value) return
  applyLoading.value = true
  radarError.value = ''
  try {
    const result = await deadlineRadarApi.apply({
      ...previewPayload.value,
      idempotency_key: executionKey.value,
    })
    executionResult.value = result
    tasks.value = tasks.value.map((task) => task.id === result.task.id ? result.task : task)
    confirmed.value = false
    ElMessage.success('通知变更已执行，并保留回执。')
    await nextTick()
    receiptElement.value?.focus({ preventScroll: true })
    receiptElement.value?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'nearest' })
  } catch (error) {
    if (error?.code === 'EDIT_CONFLICT') {
      radarError.value = '原任务已经在别处更新。本次没有执行，请重新读取任务并生成预演。'
      preview.value = null
      previewPayload.value = null
      executionKey.value = ''
      confirmed.value = false
      await loadTasks()
    } else {
      radarError.value = error?.message || '通知变更未保存，请重试。'
    }
  } finally {
    applyLoading.value = false
  }
}

function randomToken() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function reducedMotion() {
  return globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

function taskOptionLabel(task) {
  return `${task.name} · ${formatRadarDate(task.due_at)}`
}

function formatRadarDate(value) {
  return value ? formatDateTime(value) : '尚未设置'
}

function shortDate(value) {
  const parsed = new Date(`${value}T00:00:00+08:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: 'numeric',
    day: 'numeric',
    weekday: 'short',
  }).format(parsed)
}

function directionLabel(impact) {
  if (impact.direction === 'removed') return '任务取消'
  if (impact.direction === 'new_deadline') return '补上新截止'
  if (!impact.day_shift) return impact.direction === 'earlier' ? '同日提前' : '同日延后'
  return `${impact.direction === 'earlier' ? '提前' : '延后'} ${Math.abs(impact.day_shift)} 天`
}

function barStyle(day, field) {
  return { width: `${pressureBarWidth(day, field)}%` }
}

function capacityStyle(day) {
  return { left: `calc(${pressureBarWidth(day, 'effective_capacity_minutes')}% - 1px)` }
}

function pressureAriaLabel(day) {
  const affected = day.affected ? '这一天受到变更影响' : '这一天负荷不变'
  const overload = day.after_overload_minutes ? `，变更后超载 ${day.after_overload_minutes} 分钟` : ''
  return `${day.local_date}，变更前 ${day.before_minutes} 分钟，变更后 ${day.after_minutes} 分钟，当日容量 ${day.effective_capacity_minutes} 分钟，${affected}${overload}`
}

function basisLabel(key) {
  return {
    timezone: '时区',
    window: '观察窗口',
    task_binding: '任务绑定',
    workload_formula: '工作量口径',
    capacity_formula: '容量口径',
    execution_boundary: '执行边界',
  }[key] || key
}
</script>

<style scoped>
.radar-page {
  --radar-ink: var(--ledger-ink);
  --radar-blue: var(--ledger-indigo);
  --radar-red: #b64d42;
  --radar-green: #327864;
  --radar-amber: #b7791f;
  --radar-paper: var(--ledger-paper);
  min-width: 0;
  color: var(--radar-ink);
}

.radar-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.radar-hero__copy { max-width: 760px; min-width: 0; }
.radar-hero__signal { margin: 0 0 8px; color: var(--radar-red); font-size: 13px; font-weight: 750; letter-spacing: 0; }
.radar-hero h1 { margin: 0; font-size: 28px; font-weight: 650; line-height: 1.4; }
.radar-hero__lede { max-width: 730px; margin: 9px 0 0; color: var(--ledger-muted); font-size: 14px; line-height: 1.75; }
.radar-back { align-self: start; justify-self: end; min-height: 44px; padding: 11px 15px; color: var(--ledger-ink); border-bottom: 1px solid #c5d7ce; font-size: 14px; font-weight: 650; }
.radar-back:hover { color: var(--radar-blue); border-color: var(--radar-blue); }

.radar-input { padding: 22px 24px; background: var(--radar-paper); border: 1px solid var(--ledger-line); border-radius: 12px; box-shadow: none; }
.radar-input__heading, .radar-result__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.radar-step { display: block; margin-bottom: 5px; color: var(--ledger-muted); font-family: inherit; font-size: 11px; font-weight: 800; letter-spacing: 0; }
.radar-input h2, .radar-result h2, .radar-receipt h2 { margin: 0; color: var(--radar-ink); font-size: 18px; font-weight: 600; line-height: 1.5; }
.radar-safety { flex: 0 0 auto; padding: 5px 9px; color: var(--radar-green); border: 1px solid #a9cdbf; background: #f0f8f4; border-radius: 3px; font-size: 12px; font-weight: 700; }
.radar-form { display: grid; grid-template-columns: minmax(220px, .8fr) minmax(360px, 2fr); gap: 16px 18px; margin-top: 19px; }
.radar-field { display: grid; align-content: start; gap: 7px; min-width: 0; color: var(--ledger-ink); font-size: 13px; font-weight: 700; }
.radar-field :deep(.el-select), .radar-field :deep(.el-textarea) { width: 100%; }
.radar-field :deep(.el-select__wrapper) { min-height: 46px; }
.radar-field :deep(.el-textarea__inner) { min-height: 126px !important; padding: 13px 14px; color: var(--radar-ink); line-height: 1.7; }
.radar-field :deep(.el-select__wrapper:focus-within), .radar-field :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 2px rgba(50, 120, 100, .28); }
.radar-form__footer { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; gap: 18px; padding-top: 14px; border-top: 1px dashed var(--ledger-line); }
.radar-form__footer p { margin: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; }
.radar-form__footer :deep(.el-button) { min-height: 44px; min-width: 148px; }
.radar-empty { margin-top: 18px; padding: 14px; color: var(--ledger-muted); background: var(--ledger-canvas); border-radius: 8px; font-size: 13px; line-height: 1.7; }
.radar-empty p { margin: 0; }
.radar-empty a { display: inline-flex; align-items: center; min-height: 44px; font-weight: 600; }
.radar-error { display: flex; align-items: center; gap: 10px; margin-top: 15px; padding: 12px 14px; color: #862f29; background: #fff3f1; border-left: 3px solid var(--radar-red); font-size: 13px; line-height: 1.55; }
.radar-error span { min-width: 0; overflow-wrap: anywhere; }

.radar-result { margin-top: 22px; padding: 24px; background: #f5f8f7; border: 1px solid var(--ledger-line); border-radius: 6px; scroll-margin-top: 18px; }
.radar-direction { flex: 0 0 auto; padding: 6px 10px; color: var(--radar-red); border: 1px solid #deb0aa; background: #fff8f5; border-radius: 3px; font-family: inherit; font-size: 13px; font-weight: 800; }
.radar-direction.is-later, .radar-direction.is-new_deadline { color: var(--radar-blue); border-color: #c8ddd1; background: #f1f7f3; }
.radar-direction.is-removed { color: var(--ledger-muted); border-color: #cbd1da; background: #f9fafb; }
.radar-track { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0; margin: 22px 0 0; padding: 0; list-style: none; }
.radar-station { position: relative; min-width: 0; padding: 28px 16px 18px; background: var(--radar-paper); border-top: 3px solid var(--radar-blue); border-right: 1px solid var(--ledger-line); border-bottom: 1px solid var(--ledger-line); }
.radar-station:first-child { border-left: 1px solid var(--ledger-line); }
.radar-station::before { content: ""; position: absolute; z-index: 1; top: -7px; left: 16px; width: 11px; height: 11px; background: var(--radar-paper); border: 2px solid var(--radar-blue); border-radius: 50%; }
.radar-station--confirm { border-top-color: var(--radar-red); }
.radar-station--confirm::before { border-color: var(--radar-red); }
.radar-station__number { position: absolute; top: 5px; right: 12px; color: #c5d7ce; font-family: inherit; font-size: 19px; font-weight: 800; }
.radar-station__body { display: grid; align-content: start; gap: 9px; min-width: 0; }
.radar-station__label { color: var(--ledger-muted); font-size: 11px; font-weight: 800; letter-spacing: 0; }
.radar-station__body > strong { min-width: 0; color: var(--radar-ink); font-size: 14px; line-height: 1.55; overflow-wrap: anywhere; }
.radar-station blockquote { max-height: 128px; margin: 0; padding: 9px 0 9px 11px; overflow: auto; color: var(--ledger-muted); border-left: 2px solid #c5d7ce; font-size: 12px; line-height: 1.65; overflow-wrap: anywhere; }
.radar-warning { margin: 0; color: var(--radar-amber); font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.radar-task-name { min-height: 43px; }
.deadline-shift { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 6px; }
.deadline-shift > div { display: grid; gap: 4px; min-width: 0; padding: 8px; background: #f5f8f7; border-bottom: 2px solid #c5d7ce; }
.deadline-shift > div:last-child { background: #fff1ed; border-color: var(--radar-red); }
.deadline-shift > div:last-child.is-cancel { background: #f5f8f7; border-color: #c5d7ce; }
.deadline-shift span { color: var(--ledger-muted); font-size: 10px; }
.deadline-shift time { color: var(--radar-ink); font-family: inherit; font-size: 12px; font-weight: 750; line-height: 1.35; }
.deadline-shift__arrow { color: var(--radar-red) !important; font-size: 17px !important; font-weight: 800; }

.pressure-legend { display: flex; flex-wrap: wrap; gap: 9px; color: var(--ledger-muted); font-size: 10px; }
.pressure-legend span { display: inline-flex; align-items: center; gap: 4px; }
.pressure-legend i { display: inline-block; width: 13px; height: 3px; background: #a7afbd; }
.pressure-legend .is-after { background: var(--radar-red); }
.pressure-legend .is-capacity { height: 9px; width: 1px; background: var(--radar-amber); }
.pressure-days { display: grid; grid-template-columns: repeat(7, minmax(46px, 1fr)); gap: 5px; min-width: 0; }
.pressure-day { min-width: 0; padding: 7px 5px 6px; background: #f5f8f7; border-bottom: 2px solid transparent; }
.pressure-day.is-affected { background: #fff8f2; border-color: var(--radar-amber); }
.pressure-day.is-overloaded { background: #fff0ed; border-color: var(--radar-red); }
.pressure-day__date { display: block; min-height: 29px; color: #657083; font-size: 11px; line-height: 1.35; }
.pressure-day__plot { position: relative; height: 24px; margin: 4px 0 5px; overflow: hidden; background: #edf0f4; }
.pressure-day__capacity { position: absolute; z-index: 3; top: 0; width: 1px; height: 100%; background: var(--radar-amber); }
.pressure-bar { position: absolute; left: 0; height: 6px; min-width: 0; transition: width .42s ease; }
.pressure-bar--before { top: 5px; background: #a7afbd; }
.pressure-bar--after { bottom: 5px; background: var(--radar-red); }
.pressure-day > strong { display: block; color: var(--radar-ink); font-family: inherit; font-size: 12px; font-variant-numeric: tabular-nums; }
.pressure-day > strong small { font-size: 8px; font-weight: 600; }
.pressure-day__overload, .pressure-day__changed, .pressure-day__quiet { display: block; margin-top: 2px; color: var(--radar-red); font-size: 9px; font-weight: 750; }
.pressure-day__changed { color: var(--radar-amber); }
.pressure-day__quiet { color: #a5adba; }
.radar-station--confirm p { margin: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.radar-station--confirm :deep(.el-checkbox) { height: auto; align-items: flex-start; white-space: normal; }
.radar-station--confirm :deep(.el-checkbox__label) { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; white-space: normal; }
.radar-station--confirm :deep(.el-button) { width: 100%; min-height: 44px; margin-top: 2px; white-space: normal; }
.radar-basis { margin-top: 14px; color: var(--ledger-muted); font-size: 12px; }
.radar-basis summary { width: max-content; max-width: 100%; min-height: 38px; padding: 10px 2px; cursor: pointer; font-weight: 700; }
.radar-basis dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 5px 0 0; }
.radar-basis dl > div { min-width: 0; padding: 10px; background: var(--radar-paper); border-left: 2px solid #c5d7ce; }
.radar-basis dt { color: var(--ledger-muted); font-size: 10px; font-weight: 800; }
.radar-basis dd { margin: 5px 0 0; color: var(--ledger-ink); line-height: 1.55; overflow-wrap: anywhere; }

.radar-receipt { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 18px; margin-top: 20px; padding: 20px 22px; color: #245c49; background: #eff8f3; border: 1px solid #b9d9cc; border-left: 4px solid var(--radar-green); border-radius: 5px; outline: none; scroll-margin-top: 18px; }
.radar-receipt:focus-visible { box-shadow: 0 0 0 3px rgba(47, 122, 95, .24); }
.radar-receipt__check { display: grid; place-items: center; width: 38px; height: 38px; color: white; background: var(--radar-green); border-radius: 50%; font-size: 22px; font-weight: 800; }
.radar-receipt h2 { color: #234f40; }
.radar-receipt p { margin: 6px 0 0; line-height: 1.6; }
.radar-receipt__meta { color: #557468; font-size: 12px; }
.radar-receipt > a { min-height: 44px; padding: 12px 2px; color: var(--radar-green); border-bottom: 1px solid #81ad9a; font-size: 13px; font-weight: 750; }
.radar-reveal-enter-active { transition: opacity .3s ease, transform .3s ease; }
.radar-reveal-enter-from { opacity: 0; transform: translateY(10px); }

@media (max-width: 1180px) {
  .radar-back { grid-column: 1 / -1; justify-self: start; }
  .radar-track { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--ledger-line); }
  .radar-station--pressure, .radar-station--confirm { grid-column: 1 / -1; }
  .radar-station { border: 0; border-top: 3px solid var(--radar-blue); }
  .radar-station--confirm { border-top-color: var(--radar-red); }
}

@media (max-width: 760px) {
  .radar-hero { flex-direction: column; gap: 12px; }
  .radar-hero h1 { font-size: 25px; }
  .radar-back { grid-column: auto; }
  .radar-input, .radar-result { padding: 18px 14px; }
  .radar-input__heading, .radar-result__heading { align-items: flex-start; flex-direction: column; gap: 10px; }
  .radar-form { grid-template-columns: minmax(0, 1fr); }
  .radar-form__footer { grid-column: auto; align-items: stretch; flex-direction: column; }
  .radar-track { grid-template-columns: minmax(0, 1fr); }
  .radar-station { padding: 27px 14px 17px; }
  .pressure-days { grid-template-columns: repeat(7, minmax(0, 1fr)); padding-bottom: 8px; overflow-x: auto; }
  .radar-basis dl { grid-template-columns: minmax(0, 1fr); }
  .radar-receipt { grid-template-columns: auto minmax(0, 1fr); align-items: start; padding: 17px 14px; }
  .radar-receipt > a { grid-column: 2; justify-self: start; }
}

@media (max-width: 390px) {
  .deadline-shift { grid-template-columns: minmax(0, 1fr); }
  .deadline-shift__arrow { transform: rotate(90deg); justify-self: center; }
  .radar-receipt__check { width: 32px; height: 32px; font-size: 18px; }
}

@media (prefers-reduced-motion: reduce) {
  .pressure-bar, .radar-reveal-enter-active { transition: none; }
  .radar-reveal-enter-from { transform: none; }
}
</style>
