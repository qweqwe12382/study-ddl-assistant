<template>
  <section class="first-learning-loop" :class="{ 'is-collapsed': hidden || status?.completed }" aria-label="开始使用学伴管家">
    <Transition name="soft-swap" mode="out-in">
      <p v-if="state === 'ready' && status?.completed" key="complete" class="loop-finished"><span aria-hidden="true">✓</span> 已完成第一项任务，接下来按自己的节奏学习。</p>
      <button v-else-if="hidden" key="hidden" type="button" class="loop-restore" @click="setHidden(false)">查看上手提示</button>
      <div v-else-if="state !== 'ready' || !status" key="loading" class="loop-data-state" role="status">
        <span>{{ state === 'loading' ? '正在读取你的学习记录…' : '暂时无法读取上手进度。' }}</span>
        <button v-if="state !== 'loading'" type="button" class="loop-secondary" @click="$emit('retry')">重新读取</button>
      </div>
      <div v-else :key="status.started ? 'started' : 'new'" class="loop-content">
        <div class="loop-topline">
          <span class="loop-progress">{{ status.started ? '已经迈出第一步' : '第一次使用，从这里开始' }}</span>
          <button type="button" class="loop-hide" @click="setHidden(true)">稍后再看</button>
        </div>
        <h2>{{ status.started ? '开始做你的第一项任务' : '先记下一件要做的事' }}</h2>
        <p class="loop-summary">{{ status.started ? '做完后标记完成，就能留下第一条学习记录。用时和难度可以稍后补充。' : '写下作业或复习内容就能开始。课程、日期和预计用时，都可以稍后补充。' }}</p>
        <div class="loop-actions">
          <button type="button" class="loop-primary" @click="$emit('navigate', status.started ? 'complete' : 'task')">{{ status.started ? '去做第一项任务' : '记下第一项任务' }}</button>
          <button v-if="!status.started" type="button" class="loop-secondary" @click="startFromMaterial">{{ materialSourceAvailable ? '核对已有资料' : '从资料开始' }}</button>
        </div>
        <ol class="loop-steps" aria-label="开始学习的两个步骤">
          <li :class="{ 'is-complete': status.started }"><span aria-hidden="true">{{ status.started ? '✓' : '1' }}</span>记下一项任务</li>
          <li><span aria-hidden="true">2</span>做完后标记完成</li>
        </ol>
        <p v-if="!concise" class="loop-optional">想按课程整理？<button type="button" @click="$emit('navigate', 'course')">添加课程</button>，也可以以后再安排。</p>
      </div>
    </Transition>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { authSession } from '../auth/session'
import { firstLearningProgress } from '../utils/firstLearningLoopPlacement'

const props = defineProps({
  state: { type: String, default: 'loading' },
  concise: { type: Boolean, default: false },
  progress: { type: Object, default: () => ({}) },
  materialSourceAvailable: { type: Boolean, default: false },
})
const emit = defineEmits(['retry', 'navigate', 'open-material-source'])
const status = computed(() => firstLearningProgress(props.progress))
const hidden = ref(false)
// Keep one student's dismissed guide from hiding it for the next account.
const storageKey = computed(() => `study-ledger:get-started:${authSession.user?.id || 'guest'}`)
watch(storageKey, (key) => {
  try { hidden.value = window.localStorage.getItem(key) === 'hidden' }
  catch { hidden.value = false }
}, { immediate: true })

function setHidden(value) {
  hidden.value = value
  try {
    if (value) window.localStorage.setItem(storageKey.value, 'hidden')
    else window.localStorage.removeItem(storageKey.value)
  } catch { /* The guide still works when storage is unavailable. */ }
}
function startFromMaterial() {
  if (props.materialSourceAvailable) emit('open-material-source')
  else emit('navigate', 'material')
}
</script>

<style scoped>
.first-learning-loop { min-width: 0; margin-bottom: 24px; padding: 28px; border: 1px solid var(--ledger-line); border-top: 3px solid var(--ledger-indigo); border-radius: var(--ledger-radius); background: var(--ledger-paper); }
.first-learning-loop.is-collapsed { padding: 0; border: 0; background: transparent; }
.loop-topline { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.loop-progress { color: var(--ledger-link); font-size: 13px; font-weight: 600; }
.loop-hide, .loop-restore, .loop-optional button { min-height: 44px; padding: 8px 0; color: var(--ledger-muted); border: 0; background: transparent; cursor: pointer; font-size: 12px; }
.loop-hide:hover, .loop-restore:hover, .loop-optional button:hover { color: var(--ledger-link); text-decoration: underline; text-underline-offset: 4px; }
.loop-content h2 { margin: 12px 0 0; color: var(--ledger-ink); font-size: 25px; font-weight: 600; line-height: 1.5; }
.loop-summary { max-width: 62ch; margin: 12px 0 0; color: var(--ledger-muted); font-size: 14px; line-height: 1.8; }
.loop-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }
.loop-primary, .loop-secondary { min-height: 44px; padding: 10px 18px; border: 1px solid #d1e1d8; border-radius: 8px; color: var(--ledger-link); background: #fff; cursor: pointer; font-size: 13px; font-weight: 600; }
.loop-primary { color: #fff; background: var(--ledger-indigo); border-color: var(--ledger-indigo); }
.loop-primary:hover { background: var(--ledger-link); }
.loop-secondary:hover { background: #f3f8f5; border-color: var(--ledger-indigo); }
.loop-steps { display: flex; flex-wrap: wrap; gap: 14px 28px; margin: 26px 0 0; padding: 18px 0 0; border-top: 1px solid #d9e8df; list-style: none; }
.loop-steps li { display: flex; align-items: center; gap: 8px; color: var(--ledger-muted); font-size: 12px; }
.loop-steps li span { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: #eef4ef; color: var(--ledger-link); }
.loop-steps .is-complete span { color: #2d7155; background: #dceee4; }
.loop-optional { margin: 12px 0 0; color: var(--ledger-muted); font-size: 12px; }
.loop-optional button { color: var(--ledger-link); }
.loop-finished { margin: 0; padding: 12px 0; color: #526b61; font-size: 13px; line-height: 1.7; }
.loop-finished span { margin-right: 8px; color: #357862; }
.loop-data-state { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; color: var(--ledger-muted); font-size: 13px; }
.first-learning-loop button:focus-visible { outline: 3px solid rgba(50, 120, 100, .35); outline-offset: 3px; }
@media (max-width: 560px) { .first-learning-loop { padding: 18px; } .loop-content h2 { font-size: 21px; } .loop-actions { flex-direction: column; } .loop-steps { gap: 12px; } }
</style>
