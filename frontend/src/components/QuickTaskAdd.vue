<template>
  <form class="quick-add" aria-label="快速添加任务" @submit.prevent="submitQuickAdd">
    <label class="quick-add-label" for="quick-task-name">先记下来</label>
    <div class="quick-add-entry">
      <input id="quick-task-name" ref="nameInput" v-model="name" class="quick-add-name" name="quick_task_name" type="text" maxlength="200" placeholder="例如：完成高数第三章习题" :disabled="submitting" aria-describedby="quick-add-help quick-add-feedback" @keydown.enter="onEnter">
      <button class="quick-add-submit" type="submit" :disabled="submitting">{{ submitting ? '正在添加…' : '添加任务' }}</button>
    </div>
    <div class="quick-add-options-heading">
      <p id="quick-add-help">{{ dueSummary }}</p>
      <button type="button" class="quick-add-toggle" :aria-expanded="optionsOpen" aria-controls="quick-add-options" @click="optionsOpen = !optionsOpen">
        {{ optionsOpen ? '收起选项' : '设置日期和课程' }}<span class="option-chevron" :class="{ 'is-open': optionsOpen }" aria-hidden="true">⌄</span>
      </button>
    </div>
    <Transition name="reveal-panel">
      <div v-if="optionsOpen" id="quick-add-options" class="quick-add-options">
        <div class="quick-add-options-inner">
          <label class="quick-add-course-label">课程（可选）
            <select v-model="courseId" class="quick-add-course" :disabled="submitting">
              <option :value="null">暂不关联课程</option>
              <option v-for="course in courses" :key="course.id" :value="course.id">{{ course.name }}</option>
            </select>
          </label>
          <div class="quick-add-due" role="group" aria-label="快捷截止时间">
            <span class="quick-due-label">截止日期（可选）</span>
            <button v-for="chip in QUICK_DUE_CHIPS" :key="chip.key" type="button" class="quick-chip" :class="{ active: dueChip === chip.key }" :aria-pressed="dueChip === chip.key" :disabled="submitting" @click="dueChip = dueChip === chip.key ? '' : chip.key">{{ chip.label }}</button>
            <label class="quick-custom-date" :class="{ active: dueChip === 'custom' }">
              <input v-model="customDate" type="date" aria-label="自选截止日期" :disabled="submitting" @change="dueChip = customDate ? 'custom' : ''">
            </label>
            <button v-if="dueChip" type="button" class="quick-add-toggle" :disabled="submitting" @click="clearDate">清除日期</button>
          </div>
        </div>
      </div>
    </Transition>
    <div id="quick-add-feedback" aria-live="polite" aria-atomic="true">
      <Transition name="soft-swap" mode="out-in">
        <p v-if="feedback" :key="feedback" class="quick-add-feedback" :class="{ 'is-error': feedbackError }"><span aria-hidden="true">{{ feedbackError ? '!' : '✓' }}</span>{{ feedback }}</p>
      </Transition>
    </div>
  </form>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { tasksApi } from '../api'
import { QUICK_DUE_CHIPS, buildQuickAddPayload } from '../utils/quickTaskAdd'

defineProps({ courses: { type: Array, default: () => [] } })
const emit = defineEmits(['created'])
const name = ref('')
const nameInput = ref(null)
const courseId = ref(null)
const dueChip = ref('')
const customDate = ref('')
const submitting = ref(false)
const optionsOpen = ref(false)
const feedback = ref('')
const feedbackError = ref(false)
const dueSummary = computed(() => {
  if (!dueChip.value) return '只填任务名即可，其他信息稍后补充。'
  const label = dueChip.value === 'custom' ? customDate.value : QUICK_DUE_CHIPS.find(chip => chip.key === dueChip.value)?.label
  return `截止：${label || '请选择日期'} 23:59；精确时间可在添加后编辑。`
})
function clearDate() { dueChip.value = ''; customDate.value = '' }
function focusInput() { nameInput.value?.focus({ preventScroll: true }) }
function onEnter(event) {
  // Enter often confirms a Chinese IME candidate; it must not submit that draft.
  if (event.isComposing || event.keyCode === 229) { event.preventDefault(); return }
  event.preventDefault()
  void submitQuickAdd()
}
defineExpose({ focusInput })
async function submitQuickAdd() {
  if (submitting.value) return
  const built = buildQuickAddPayload({ name: name.value, courseId: courseId.value, dueChip: dueChip.value, customDate: customDate.value })
  feedbackError.value = false
  if (built.error) { feedbackError.value = true; feedback.value = built.error; focusInput(); return }
  submitting.value = true
  try {
    await tasksApi.create(built.payload)
    feedback.value = `已记下「${built.payload.name}」，可以在下方查看。`
    name.value = ''
    courseId.value = null
    clearDate()
    emit('created')
  } catch (error) {
    feedbackError.value = true
    feedback.value = error?.message || '添加失败，请重试。填写的内容已保留。'
  } finally {
    submitting.value = false
    await nextTick()
    focusInput()
  }
}
</script>

<style scoped>
.quick-add { min-width: 0; margin-bottom: 18px; padding: 16px 18px; border: 1px solid var(--ledger-line); border-radius: var(--ledger-radius); background: var(--ledger-paper); }
.quick-add-label { display: block; margin-bottom: 9px; color: var(--ledger-ink); font-size: 14px; font-weight: 650; }
.quick-add-entry { display: flex; align-items: stretch; gap: 10px; }
.quick-add-name { width: 100%; min-width: 0; min-height: 46px; padding: 10px 13px; border: 1px solid #cbd4e0; border-radius: 8px; color: var(--ledger-ink); background: #fff; font-size: 14px; }
.quick-add-submit { flex-shrink: 0; min-height: 46px; padding: 10px 20px; border: 0; border-radius: 8px; background: var(--ledger-indigo); color: #fff; cursor: pointer; font-size: 13px; font-weight: 600; }
.quick-add-submit:hover:not(:disabled) { background: var(--ledger-link); }
.quick-add-submit:disabled { opacity: .6; cursor: wait; }
.quick-add-options-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0 14px; margin-top: 5px; }
.quick-add-options-heading p { margin: 6px 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; }
.quick-add-toggle { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; padding: 7px 0; color: var(--ledger-link); border: 0; background: transparent; font-size: 12px; cursor: pointer; }
.option-chevron { display: inline-block; transition: transform .18s ease; }
.option-chevron.is-open { transform: rotate(180deg); }
.quick-add-options { display: grid; grid-template-rows: 1fr; }
.quick-add-options-inner { min-height: 0; overflow: hidden; }
.quick-add-course-label { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding-top: 12px; border-top: 1px solid var(--ledger-line); color: var(--ledger-muted); font-size: 12px; }
.quick-add-course { min-width: 0; max-width: 100%; min-height: 44px; padding: 8px 10px; border: 1px solid #cbd4e0; border-radius: 8px; color: var(--ledger-ink); background: #fff; }
.quick-add-due { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding-top: 12px; }
.quick-due-label { flex-basis: 100%; color: var(--ledger-muted); font-size: 12px; }
.quick-chip { min-height: 44px; padding: 9px 14px; border: 1px solid #cbd4e0; border-radius: 8px; color: #51617f; background: #fff; font-size: 12px; cursor: pointer; }
.quick-chip.active { color: var(--ledger-link); background: #f1f7f3; border-color: var(--ledger-indigo); box-shadow: inset 0 0 0 1px var(--ledger-indigo); }
.quick-custom-date { display: flex; min-width: 0; min-height: 44px; padding: 8px; border: 1px solid #cbd4e0; border-radius: 8px; }
.quick-custom-date.active { border-color: var(--ledger-indigo); }
.quick-custom-date input { min-width: 0; max-width: 100%; border: 0; background: transparent; color: var(--ledger-ink); }
.quick-add-feedback { display: flex; align-items: baseline; gap: 8px; margin: 10px 0 0; color: #2e7156; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.quick-add-feedback.is-error { color: #b14242; }
@media (max-width: 560px) { .quick-add { padding: 14px; } .quick-add-entry { gap: 8px; } .quick-add-submit { padding: 10px 12px; } .quick-add-name, .quick-add-course { font-size: 16px; } }
</style>
