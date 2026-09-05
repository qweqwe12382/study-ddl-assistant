<template>
  <form class="quick-add" role="search" aria-label="快速添加任务" @submit.prevent="submitQuickAdd">
    <span class="quick-add-label">快速添加</span>
    <input
      v-model="name"
      class="quick-add-name"
      name="quick_task_name"
      type="text"
      maxlength="200"
      placeholder="例如：高数第三章习题，明天交"
      :disabled="submitting"
      @keydown.enter.prevent="submitQuickAdd"
    >
    <select v-model="courseId" class="quick-add-course" aria-label="关联课程（可选）" :disabled="submitting">
      <option :value="null">不关联课程</option>
      <option v-for="course in courses" :key="course.id" :value="course.id">{{ course.name }}</option>
    </select>
    <div class="quick-add-due" role="group" aria-label="快捷截止时间">
      <button
        v-for="chip in QUICK_DUE_CHIPS"
        :key="chip.key"
        type="button"
        class="quick-chip"
        :class="{ active: dueChip === chip.key }"
        :disabled="submitting"
        @click="dueChip = dueChip === chip.key ? '' : chip.key"
      >
        {{ chip.label }}
      </button>
      <label class="quick-custom-date" :class="{ active: dueChip === 'custom' }">
        <input
          v-model="customDate"
          type="date"
          aria-label="自选截止日期"
          :disabled="submitting"
          @change="dueChip = 'custom'"
        >
      </label>
    </div>
    <button class="quick-add-submit" type="submit" :disabled="submitting">
      {{ submitting ? '正在添加' : '添加任务' }}
    </button>
  </form>
</template>

<script setup>
import { ref } from 'vue'

import { ElMessage } from 'element-plus'

import { tasksApi } from '../api'
import { QUICK_DUE_CHIPS, buildQuickAddPayload } from '../utils/quickTaskAdd'

defineProps({
  courses: { type: Array, default: () => [] },
})

const emit = defineEmits(['created'])

const name = ref('')
const courseId = ref(null)
const dueChip = ref('')
const customDate = ref('')
const submitting = ref(false)

async function submitQuickAdd() {
  if (submitting.value) return
  const built = buildQuickAddPayload({
    name: name.value,
    courseId: courseId.value,
    dueChip: dueChip.value,
    customDate: customDate.value,
  })
  if (built.error) {
    ElMessage.warning(built.error)
    return
  }
  submitting.value = true
  try {
    await tasksApi.create(built.payload)
    ElMessage.success(`已添加「${built.payload.name}」${built.payload.due_at ? '，可在下方议程中查看' : ''}`)
    name.value = ''
    courseId.value = null
    dueChip.value = ''
    customDate.value = ''
    emit('created')
  } catch (error) {
    ElMessage.error(error?.message || '添加失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.quick-add { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; margin: 0 0 16px; padding: 13px 15px; border: 1px solid var(--tasks-line, #d9e0ea); border-radius: 12px; background: var(--tasks-paper, #fffefb); box-shadow: 0 4px 12px rgba(30, 42, 68, .05); }
.quick-add-label { flex: 0 0 auto; color: #5a6882; font: 700 11px/1 Bahnschrift, "Microsoft YaHei", sans-serif; letter-spacing: .08em; }
.quick-add-name { flex: 1 1 220px; min-width: 0; min-height: 42px; padding: 0 12px; border: 1px solid #cbd4e0; border-radius: 9px; background: #fff; color: var(--ledger-ink); font-size: 14px; }
.quick-add-name:focus { outline: 2px solid rgba(89, 100, 237, .35); outline-offset: 1px; }
.quick-add-course { flex: 0 1 160px; min-height: 42px; padding: 0 9px; border: 1px solid #cbd4e0; border-radius: 9px; background: #fff; color: var(--ledger-ink); font-size: 13px; }
.quick-add-due { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.quick-chip { min-height: 38px; padding: 0 12px; border: 1px solid #cbd4e0; border-radius: 99px; background: #fff; color: #51617f; font-size: 12px; font-weight: 650; cursor: pointer; }
.quick-chip.active { color: #fff; border-color: var(--ledger-indigo); background: var(--ledger-indigo); }
.quick-custom-date { display: inline-flex; align-items: center; min-height: 38px; padding: 0 8px; border: 1px solid #cbd4e0; border-radius: 99px; background: #fff; }
.quick-custom-date.active { border-color: var(--ledger-indigo); }
.quick-custom-date input { border: 0; background: transparent; color: var(--ledger-ink); font-size: 12px; }
.quick-add-submit { flex: 0 0 auto; min-height: 42px; padding: 0 17px; color: #fff; border: 0; border-radius: 9px; background: var(--ledger-indigo); font-size: 13px; font-weight: 750; cursor: pointer; }
.quick-add-submit:hover:not(:disabled) { filter: brightness(1.06); }
.quick-add-submit:disabled { opacity: .6; cursor: default; }
@media (max-width: 640px) {
  .quick-add { align-items: stretch; flex-direction: column; }
  .quick-add-name, .quick-add-course, .quick-add-submit { width: 100%; flex-basis: auto; }
  .quick-add-submit { min-height: 44px; }
}
</style>
