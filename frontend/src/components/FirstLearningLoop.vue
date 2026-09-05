<template>
  <section
    class="first-learning-loop"
    :class="{ 'is-compact': isCompact }"
    :aria-labelledby="isCompact ? undefined : 'first-learning-loop-title'"
    :aria-label="isCompact ? '上手进度' : undefined"
  >
    <button
      v-if="hidden"
      type="button"
      class="loop-restore"
      aria-label="显示上手进度"
      @click="restore"
    >
      显示上手进度
    </button>

    <template v-else>
      <header v-if="!isCompact" class="loop-header">
        <div>
          <p class="loop-kicker">上手进度</p>
          <h2 id="first-learning-loop-title">完成 4 步，开始安排学习</h2>
          <p class="loop-summary">记录课程、资料、任务和一次完成反馈，之后就能看到更贴合实际的安排。</p>
        </div>
        <button type="button" class="loop-hide" @click="hide">稍后再看</button>
      </header>
      <button v-else type="button" class="loop-hide loop-hide-compact" @click="hide">稍后再看</button>

      <div v-if="state !== 'ready'" class="loop-data-state" :class="`loop-data-state--${state}`" role="status" aria-live="polite">
        <strong>{{ stateTitle }}</strong>
        <span>{{ stateDetail }}</span>
        <button v-if="state === 'error' || state === 'invalid'" type="button" class="loop-retry" @click="$emit('retry')">重试</button>
      </div>

      <template v-else>
        <p v-if="!isCompact" class="loop-ready-state" role="status">进度已更新</p>
        <div v-if="isCompact" class="loop-compact-ticket" role="status" aria-live="polite">
          <template v-if="currentStep">
            <span class="loop-progress">{{ progressLabel }}</span>
            <strong>下一步：{{ currentStep.title }}</strong>
            <p>{{ currentStep.concise }}</p>
            <button type="button" class="loop-primary" @click="emitAction(currentStep.action)">{{ currentStep.actionLabel }}</button>
          </template>
          <template v-else>
            <strong>4 步已完成</strong>
            <p>第一条学习记录已经建立。</p>
            <button type="button" class="loop-primary" @click="emitAction('complete')">查看任务</button>
          </template>
        </div>

        <ol v-else class="loop-steps" aria-label="学习记录建立步骤">
          <li v-for="step in steps" :key="step.key" :class="['loop-step', { 'is-complete': step.complete, 'is-current': !step.complete && step.key === currentStep?.key }]">
            <span class="loop-step-number" aria-hidden="true">{{ step.order }}</span>
            <div class="loop-step-content">
              <div class="loop-step-title-row">
                <strong>{{ step.title }}</strong>
                <span>{{ step.complete ? '已完成' : '未完成' }}</span>
              </div>
              <p>{{ step.evidence }}</p>
              <button v-if="!step.complete" type="button" class="loop-secondary" @click="emitAction(step.action)">{{ step.actionLabel }}</button>
            </div>
          </li>
        </ol>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { strictNonNegativeInteger } from '../utils/firstLearningLoopPlacement'

const HIDDEN_STORAGE_KEY = 'study-ledger:first-learning-loop-hidden'

const props = defineProps({
  state: { type: String, default: 'loading' },
  concise: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  progress: { type: Object, default: () => ({}) },
  materialSourceAvailable: { type: Boolean, default: false },
})

const emit = defineEmits(['retry', 'navigate', 'open-material-source'])
const hidden = ref(false)
const isCompact = computed(() => props.compact || props.concise)

const counts = computed(() => ({
  courses: safeCount(props.progress.courses_count),
  materials: safeCount(props.progress.materials_count),
  tasks: safeCount(props.progress.active_task_count) !== null && safeCount(props.progress.completed_task_count) !== null
    ? safeCount(props.progress.active_task_count) + safeCount(props.progress.completed_task_count)
    : null,
  completed: safeCount(props.progress.completed_task_count),
}))

const steps = computed(() => [
  { key: 'course', order: '01', title: '新增课程', concise: '先添加一门课程。', evidence: `课程：${countLabel(counts.value.courses, '门')}`, complete: counts.value.courses !== null && counts.value.courses >= 1, action: 'course', actionLabel: '新增课程' },
  { key: 'material', order: '02', title: '上传资料', concise: '上传一份课程资料。', evidence: `资料：${countLabel(counts.value.materials, '份')}`, complete: counts.value.materials !== null && counts.value.materials >= 1, action: 'material', actionLabel: props.materialSourceAvailable ? '查看待处理资料' : '上传资料' },
  { key: 'task', order: '03', title: '新增任务', concise: '把要做的事记成任务。', evidence: `任务：${countLabel(counts.value.tasks, '条')}（进行中 ${countLabel(safeCount(props.progress.active_task_count), '条')}，已完成 ${countLabel(safeCount(props.progress.completed_task_count), '条')}）`, complete: counts.value.tasks !== null && counts.value.tasks >= 1, action: 'task', actionLabel: props.materialSourceAvailable ? '查看待确认资料' : '新增任务' },
  { key: 'complete', order: '04', title: '完成一项任务', concise: '完成一项任务，留下学习记录。', evidence: `已完成：${countLabel(counts.value.completed, '条')}`, complete: counts.value.completed !== null && counts.value.completed >= 1, action: 'complete', actionLabel: '查看任务' },
])

const completedSteps = computed(() => steps.value.filter((step) => step.complete).length)
const currentStep = computed(() => steps.value.find((step) => !step.complete) || null)
const progressCountsReady = computed(() => Object.values(counts.value).every((count) => count !== null))
const progressLabel = computed(() => progressCountsReady.value ? `上手进度 ${completedSteps.value}/4` : '进度数据待确认')
const stateTitle = computed(() => ({ loading: '正在读取上手进度', error: '上手进度加载失败', invalid: '上手进度暂不可用' }[props.state] || '上手进度暂不可用'))
const stateDetail = computed(() => ({ loading: '正在确认课程、资料、任务和完成记录。', error: '请重试后再查看进度。', invalid: '进度信息不完整，暂时无法显示。' }[props.state] || '进度信息暂时无法显示。'))

function safeCount(value) {
  return strictNonNegativeInteger(value)
}

function countLabel(value, unit) {
  return value === null ? '待确认' : `${value}${unit}`
}

function emitAction(action) {
  if ((action === 'material' || action === 'task') && props.materialSourceAvailable) {
    emit('open-material-source')
    return
  }
  emit('navigate', action)
}

function hide() {
  hidden.value = true
  try {
    if (typeof window !== 'undefined') window.localStorage.setItem(HIDDEN_STORAGE_KEY, 'true')
  } catch {
    // Preference persistence is optional; the current page still updates.
  }
}

function restore() {
  hidden.value = false
  try {
    if (typeof window !== 'undefined') window.localStorage.removeItem(HIDDEN_STORAGE_KEY)
  } catch {
    // Preference persistence is optional; the current page still updates.
  }
}

onMounted(() => {
  try {
    hidden.value = typeof window !== 'undefined' && window.localStorage.getItem(HIDDEN_STORAGE_KEY) === 'true'
  } catch {
    hidden.value = false
  }
})
</script>

<style scoped>
.first-learning-loop { margin: 0 0 22px; padding: 18px 20px; color: #22304b; background: linear-gradient(115deg, #f4f7ff 0%, #fbfcff 65%, #f0f7ff 100%); border: 1px solid #d9e4f2; border-left: 4px solid #4f6fe8; border-radius: 14px; box-shadow: 0 10px 24px rgba(42, 75, 132, .06); }
.first-learning-loop.is-compact { margin-bottom: 14px; padding: 10px 12px; border-left-width: 3px; border-radius: 10px; }
.loop-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.loop-header > div { min-width: 0; }
.loop-kicker { margin: 0; color: #4f6fe8; font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.loop-header h2 { margin: 5px 0 0; font-size: 18px; line-height: 1.35; }
.loop-summary { max-width: 680px; margin: 7px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }
.loop-hide, .loop-restore, .loop-retry, .loop-primary, .loop-secondary { min-height: 44px; border-radius: 8px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.loop-hide { flex: 0 0 auto; padding: 0 10px; color: #52627c; background: transparent; border: 0; }
.loop-hide-compact { display: block; margin: -5px -4px 1px auto; padding: 0 8px; }
.loop-hide:hover { color: #314bc2; background: #eaf0ff; }
.loop-data-state { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; margin-top: 16px; padding: 13px; background: #fff; border: 1px solid #dce4f0; border-radius: 10px; font-size: 12px; line-height: 1.55; }
.first-learning-loop.is-compact .loop-data-state { margin-top: 4px; padding: 10px; }
.loop-data-state span { color: #667085; }
.loop-data-state--error, .loop-data-state--invalid { border-color: #f0cfcd; background: #fff9f9; }
.loop-data-state--error strong, .loop-data-state--invalid strong { color: #a84444; }
.loop-ready-state { margin: 14px 0 0; color: #55708c; font-size: 12px; line-height: 1.5; }
.loop-retry, .loop-secondary { padding: 0 13px; color: #3852c4; background: #fff; border: 1px solid #b9c8f3; }
.loop-progress { color: #52627c; font-size: 12px; font-weight: 700; line-height: 1.5; }
.loop-compact-ticket { display: grid; justify-items: start; gap: 5px; margin-top: 4px; padding: 10px 12px; background: #fff; border: 1px solid #dce4f0; border-radius: 8px; }
.loop-compact-ticket strong { font-size: 14px; line-height: 1.4; }
.loop-compact-ticket p { margin: 0; color: #667085; font-size: 13px; line-height: 1.6; }
.loop-compact-ticket .loop-primary { margin-top: 2px; }
.loop-current p, .loop-step p { margin: 0; color: #667085; font-size: 12px; line-height: 1.6; }
.loop-primary { margin-top: 3px; padding: 0 15px; color: #fff; background: #4f6fe8; border: 1px solid #4f6fe8; }
.loop-primary:hover { background: #3d5bd0; }
.loop-steps { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 16px 0 0; padding: 0; list-style: none; }
.loop-step { display: flex; min-width: 0; gap: 9px; padding: 12px; background: #fff; border: 1px solid #dce4f0; border-radius: 10px; }
.loop-step.is-current { border-color: #91a8f4; box-shadow: inset 0 2px 0 #4f6fe8; }
.loop-step.is-complete { background: #f8fcff; border-color: #cfe4dc; }
.loop-step-number { flex: 0 0 auto; color: #7890b8; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; font-weight: 800; }
.loop-step-content { display: grid; min-width: 0; gap: 6px; }
.loop-step-title-row { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.loop-step-title-row strong { min-width: 0; font-size: 13px; overflow-wrap: anywhere; }
.loop-step-title-row span { flex: 0 0 auto; color: #477e65; font-size: 12px; font-weight: 700; line-height: 1.5; }
.loop-step:not(.is-complete) .loop-step-title-row span { color: #9a6d27; }
.loop-restore { width: 100%; color: #3852c4; background: #f6f8ff; border: 1px dashed #aebdeb; }
.loop-hide:focus-visible, .loop-restore:focus-visible, .loop-retry:focus-visible, .loop-primary:focus-visible, .loop-secondary:focus-visible { outline: 3px solid rgba(79, 111, 232, .35); outline-offset: 2px; }
@media (max-width: 850px) { .loop-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .first-learning-loop { padding: 16px; } .first-learning-loop.is-compact { padding: 10px 12px; } .loop-header { display: block; } .loop-hide { margin-top: 5px; padding-left: 0; } .loop-hide-compact { margin-top: -2px; padding-left: 8px; } .loop-compact-ticket { padding: 10px 11px; } .loop-steps { grid-template-columns: 1fr; } .loop-primary, .loop-secondary, .loop-retry { width: 100%; } }
</style>
