<template>
  <aside class="exam-glance" aria-labelledby="upcoming-exam-heading">
    <header><h2 id="upcoming-exam-heading">最近考试</h2><el-icon aria-hidden="true"><Calendar /></el-icon></header>
    <p v-if="loading" role="status">正在读取考试安排…</p>
    <div v-else-if="error" role="status"><p>考试安排暂时无法读取。</p><button type="button" @click="load">重新读取</button></div>
    <template v-else-if="exam">
      <div class="countdown"><template v-if="days"><strong>{{ days }}</strong> 天后开考</template><strong v-else>今天开考</strong></div>
      <h3>{{ exam.title }}</h3>
      <CourseLabel v-if="exam.course_name && !exam.title.includes(exam.course_name)" :name="exam.course_name" :color="exam.course_color" />
      <p><time :datetime="exam.starts_at">{{ formatDateTime(exam.starts_at) }}</time><span v-if="exam.location"> · {{ exam.location }}</span></p>
      <router-link :to="{path:'/study-plans', query:{action:'create', course_id:exam.course_id, exam_id:exam.id, exam_date:examDay}}">安排复习</router-link>
    </template>
    <template v-else><p>还没有待考日程。</p><router-link to="/schedule">打开课表与考试</router-link></template>
  </aside>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Calendar } from '@element-plus/icons-vue'
import CourseLabel from './CourseLabel.vue'
import { academicCalendarApi } from '../api'
import { formatDateTime } from '../utils/format'
import { localReferenceDateTime } from '../utils/pasteNotice'

const exams = ref([])
const now = ref(new Date())
const loading = ref(true)
const error = ref(false)
let clock
const exam = computed(() => exams.value.find(item => Date.parse(item.starts_at) >= now.value.getTime()))
const dayKey = date => localReferenceDateTime(date).slice(0, 10)
const examDay = computed(() => exam.value ? dayKey(new Date(exam.value.starts_at)) : '')
const days = computed(() => (Date.parse(examDay.value) - Date.parse(dayKey(now.value))) / 86400000)
async function load() {
  loading.value = true
  error.value = false
  try {
    const rows = await academicCalendarApi.listExams()
    if (!Array.isArray(rows)) throw new Error('考试安排格式无效')
    exams.value = rows
    now.value = new Date()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}
onMounted(() => {
  load()
  clock = setInterval(() => { now.value = new Date() }, 60000)
})
onUnmounted(() => clearInterval(clock))
</script>

<style scoped>
.exam-glance { min-width: 0; align-self: start; padding: 22px; border-radius: var(--ledger-radius); background: #eaf2ec; color: var(--ledger-ink); }
header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
header .el-icon { color: var(--ledger-primary); font-size: 20px; }
h2 { margin: 0; font-size: 16px; }
h3 { margin: 12px 0 0; font: 600 17px/1.5 var(--font-content); overflow-wrap: anywhere; }
p { margin: 8px 0 0; color: #475f54; font-size: 13px; overflow-wrap: anywhere; }
.countdown { display: flex; gap: 8px; align-items: baseline; margin-top: 16px; color: var(--ledger-primary); }
.countdown strong { font-size: clamp(32px, 4vw, 48px); line-height: 1.1; font-variant-numeric: tabular-nums; }
a, button { display: inline-flex; align-items: center; min-height: 40px; margin-top: 12px; font-size: 14px; font-weight: 600; color: var(--ledger-primary); text-underline-offset: 4px; text-decoration: underline; }
button { padding: 0; border: 0; background: transparent; cursor: pointer; }
</style>
