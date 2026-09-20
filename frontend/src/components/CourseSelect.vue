<template>
  <div class="course-select">
    <div v-if="!adding" class="course-select-row">
      <el-select :model-value="modelValue" :disabled="disabled" :clearable="clearable" filterable :placeholder="placeholder" aria-label="选择课程" @update:model-value="$emit('update:modelValue', $event || null)">
        <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
      </el-select>
      <button type="button" :disabled="disabled" @click="startAdding">新建课程</button>
    </div>
    <div v-else class="course-create-row">
      <el-input ref="nameInput" v-model="name" maxlength="120" placeholder="输入课程名称" aria-label="新课程名称" :disabled="disabled || saving" @keydown="handleNameKey" />
      <el-button :loading="saving" :disabled="disabled || !name.trim()" @click="createCourse">添加并选择</el-button>
      <button type="button" :disabled="disabled || saving" @click="cancelAdding">取消</button>
    </div>
    <p v-if="error" class="course-create-error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { ElButton, ElInput, ElOption, ElSelect } from 'element-plus'
import { coursesApi } from '../api'

const props = defineProps({
  modelValue: { type: Number, default: null },
  courses: { type: Array, default: () => [] },
  clearable: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: '选择课程' },
})
const emit = defineEmits(['update:modelValue', 'created'])
const adding = ref(false)
const saving = ref(false)
const name = ref('')
const error = ref('')
const nameInput = ref(null)

async function startAdding() {
  if (props.disabled) return
  adding.value = true
  error.value = ''
  await nextTick()
  nameInput.value?.focus()
}
function cancelAdding() {
  if (props.disabled || saving.value) return
  adding.value = false
  error.value = ''
}
function handleNameKey(event) {
  if (!['Enter', 'Escape'].includes(event.key)) return
  event.stopPropagation()
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  if (event.key === 'Enter') createCourse()
  else cancelAdding()
}
async function createCourse() {
  if (props.disabled || saving.value || !name.value.trim()) return
  saving.value = true
  error.value = ''
  try {
    const existing = props.courses.find(course => course.name.trim() === name.value.trim())
    const course = existing || await coursesApi.create({ name: name.value.trim(), color: '#327864' })
    if (!existing) emit('created', course)
    emit('update:modelValue', course.id)
    adding.value = false
    name.value = ''
  } catch (err) {
    error.value = err.message || '课程未添加，请重试。已填写内容仍保留。'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.course-select { width: 100%; min-width: 0; }
.course-select-row, .course-create-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.el-select, .el-input { flex: 1; min-width: 140px; }
button { padding: 6px 4px; min-height: 36px; border: 0; background: transparent; color: var(--ledger-link); font: inherit; font-size: 13px; cursor: pointer; }
button:focus-visible { outline: 2px solid var(--ledger-link); outline-offset: 2px; border-radius: 4px; }
button:disabled { cursor: default; opacity: .6; }
.course-create-error { margin: 6px 0 0; color: #a12f25; font-size: 13px; line-height: 1.6; }
@media (max-width: 600px) { button { min-height: 44px; } .course-create-row .el-input { flex-basis: 100%; } }
</style>
