<template>
  <section class="academic-calendar-page" :aria-busy="loading">
    <div class="page-intro calendar-intro">
      <div>
        <h1>课表与考试</h1>
        <p>导入或填写固定的上课、考试时间，复习时段在计划里安排。</p>
      </div>
      <div class="page-actions">
        <el-button @click="openClassDialog()">添加上课时间</el-button>
        <el-button @click="openExamDialog()">添加考试</el-button>
        <el-button type="primary" class="integration-entry" @click="integrationDialogVisible = true">导入课表与考试</el-button>
      </div>
    </div>

    <nav class="schedule-switch" aria-label="日程与学习安排">
      <span aria-current="page">课表与考试 <small>固定时间</small></span>
      <router-link to="/study-plans">复习计划 <small>每天学什么</small></router-link>
    </nav>

    <div v-if="!courses.length && !loading && !error" class="course-gate" role="status">
      <div class="course-gate-mark" aria-hidden="true">课</div>
      <div>
        <strong>把课表放进来，就能查看一周安排</strong>
        <p>导入时自动建立课程；手动添加时，直接填写课程名称即可。</p>
      </div>
      <el-button type="primary" @click="integrationDialogVisible = true">导入课表与考试</el-button>
    </div>

    <div v-if="error" class="calendar-error" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="loadPage">重新读取</button>
    </div>

    <template v-if="courses.length">
      <section v-if="semesterCurrentWeek && selectedWeek === semesterCurrentWeek" class="today-ribbon" aria-labelledby="today-ribbon-title">
        <div class="today-stamp">
          <span>{{ todayLabel.month }}</span>
          <strong>{{ todayLabel.day }}</strong>
          <small>{{ todayLabel.weekday }}</small>
        </div>
        <div class="today-copy">
          <span class="section-eyebrow">今天的课程</span>
          <h2 id="today-ribbon-title">{{ todayHeadline }}</h2>
          <p>{{ todayDetail }}</p>
        </div>
        <div class="nearest-exam" :class="{ 'is-empty': !nearestExam }">
          <span>最近考试</span>
          <strong>{{ nearestExam ? nearestExam.course_name : '暂未录入' }}</strong>
          <small>{{ nearestExam ? `${countdownLabel(nearestExam.starts_at)} · ${formatDateTime(nearestExam.starts_at)}` : '添加后会在这里显示倒计时' }}</small>
        </div>
      </section>

      <div class="semester-week-bar" role="status">
        <template v-if="semesterCurrentWeek">
          <span>本学期第 <strong>{{ semesterCurrentWeek }}</strong> 周</span>
          <button v-if="selectedWeek !== semesterCurrentWeek" type="button" @click="jumpToCurrentWeek">跳到本周</button>
        </template>
        <label v-else class="semester-start-setter">
          <span>设置学期开学日（周一），自动定位本周：</span>
          <input
            v-model="semesterStartDraft"
            type="date"
            aria-label="学期开学日（周一）"
            :disabled="semesterStartSaving"
            @change="saveSemesterStart"
          >
        </label>
      </div>

      <section class="schedule-ledger" aria-labelledby="schedule-title">
        <header class="ledger-header">
          <div>
            <h2 id="schedule-title">第 {{ selectedWeek }} 周课表</h2>
            <p>按周查看单双周课程，点击课程即可编辑。</p>
          </div>
          <div class="week-switcher" aria-label="切换课表周次">
            <button type="button" :disabled="selectedWeek <= 1" aria-label="查看上一周" @click="changeWeek(-1)">←</button>
            <label>
              <span class="sr-only">课表周次</span>
              <el-input-number v-model="selectedWeek" :min="1" :max="30" :controls="false" aria-label="课表周次" />
            </label>
            <button type="button" :disabled="selectedWeek >= 30" aria-label="查看下一周" @click="changeWeek(1)">→</button>
          </div>
        </header>

        <div class="desktop-week-board">
          <section
            v-for="day in weekdays"
            :key="day.value"
            class="day-column"
            :class="{ 'is-today': day.value === todayWeekday && selectedWeek === semesterCurrentWeek }"
            :aria-labelledby="`weekday-${day.value}`"
          >
            <header>
              <strong :id="`weekday-${day.value}`">{{ day.label }}</strong>
              <small>{{ sessionsFor(day.value).length }} 节</small>
            </header>
            <div class="day-session-list">
              <button
                v-for="item in sessionsFor(day.value)"
                :key="item.id"
                type="button"
                class="class-ticket"
                :style="{ '--course-color': safeCourseColor(item.course_color) }"
                :aria-label="`编辑 ${item.course_name}，${formatTimeRange(item)}`"
                @click="openClassDialog(item)"
              >
                <span class="ticket-time">{{ formatTimeRange(item) }}</span>
                <strong>{{ item.course_name }}</strong>
                <span>{{ item.location || '地点待补充' }}</span>
                <small>{{ weekPatternLabel(item.week_pattern) }} · {{ item.start_week }}–{{ item.end_week }} 周</small>
              </button>
              <button v-if="!sessionsFor(day.value).length" type="button" class="empty-day" @click="openClassDialog(null, day.value)">
                <span aria-hidden="true">＋</span>
                添加课程
              </button>
            </div>
          </section>
        </div>

        <div class="mobile-week-board">
          <div class="mobile-day-tabs" role="tablist" aria-label="选择星期">
            <button
              v-for="day in weekdays"
              :id="`day-tab-${day.value}`"
              :key="day.value"
              type="button"
              role="tab"
              :aria-selected="activeWeekday === day.value"
              :aria-controls="`day-panel-${day.value}`"
              :class="{ 'is-active': activeWeekday === day.value, 'is-today': day.value === todayWeekday && selectedWeek === semesterCurrentWeek }"
              @click="activeWeekday = day.value"
            >
              <span>{{ day.short }}</span>
              <strong>{{ sessionsFor(day.value).length }}</strong>
            </button>
          </div>
          <div :id="`day-panel-${activeWeekday}`" class="mobile-day-panel" role="tabpanel" :aria-labelledby="`day-tab-${activeWeekday}`">
            <div class="mobile-day-heading">
              <div>
                <span>{{ activeDay?.label }}</span>
                <strong>{{ sessionsFor(activeWeekday).length ? `${sessionsFor(activeWeekday).length} 节课` : '当天无课' }}</strong>
              </div>
              <el-button @click="openClassDialog(null, activeWeekday)">添加</el-button>
            </div>
            <button
              v-for="item in sessionsFor(activeWeekday)"
              :key="item.id"
              type="button"
              class="mobile-class-row"
              :style="{ '--course-color': safeCourseColor(item.course_color) }"
              @click="openClassDialog(item)"
            >
              <span class="mobile-class-time">{{ formatTimeRange(item) }}</span>
              <span class="mobile-class-main">
                <strong>{{ item.course_name }}</strong>
                <small>{{ item.location || '地点待补充' }} · {{ weekPatternLabel(item.week_pattern) }}</small>
              </span>
              <span aria-hidden="true">›</span>
            </button>
            <div v-if="!sessionsFor(activeWeekday).length" class="mobile-empty-day">当天没有课程，可以添加上课时间。</div>
          </div>
        </div>
      </section>

      <section class="exam-ledger" aria-labelledby="exam-title">
        <header class="exam-header">
          <div>
            <h2 id="exam-title">考试安排</h2>
            <p>按日期排序，查看考场与座位。</p>
          </div>
          <label class="past-exam-toggle">
            <el-checkbox v-model="includePastExams">显示已结束考试</el-checkbox>
          </label>
        </header>

        <div v-if="exams.length" class="exam-list">
          <article v-for="exam in exams" :key="exam.id" class="exam-ticket" :class="{ 'is-past': isPastExam(exam) }">
            <div class="exam-date-block">
              <span>{{ examDateParts(exam.starts_at).month }}</span>
              <strong>{{ examDateParts(exam.starts_at).day }}</strong>
              <small>{{ examDateParts(exam.starts_at).weekday }}</small>
            </div>
            <div class="exam-main">
              <div class="exam-tags">
                <span>{{ examTypeLabel(exam.exam_type) }}</span>
                <span>{{ countdownLabel(exam.starts_at) }}</span>
              </div>
              <h3>{{ exam.course_name }}</h3>
              <p>{{ exam.title }}</p>
              <dl>
                <div><dt>时间</dt><dd>{{ formatExamRange(exam) }}</dd></div>
                <div><dt>地点</dt><dd>{{ exam.location || '待补充' }}</dd></div>
                <div><dt>座位</dt><dd>{{ exam.seat_number || '待补充' }}</dd></div>
              </dl>
            </div>
            <div class="exam-actions">
              <router-link v-if="!isPastExam(exam)" :to="{ path: '/study-plans', query: { action: 'create', course_id: exam.course_id, exam_date: chinaParts(new Date(exam.starts_at)).dateKey } }">安排复习</router-link>
              <button type="button" @click="openExamDialog(exam)">编辑</button>
              <button type="button" class="danger-action" @click="removeExam(exam)">删除</button>
            </div>
          </article>
        </div>
        <div v-else class="exam-empty">
          <strong>{{ includePastExams ? '还没有考试记录' : '近期没有考试安排' }}</strong>
          <p>添加考试后，这里会按日期显示倒计时、考场和座位。</p>
          <el-button type="primary" @click="openExamDialog()">添加第一场考试</el-button>
        </div>
      </section>
    </template>

    <AcademicEntryForms
      v-if="classDialogVisible || examDialogVisible"
      v-model:class-dialog-visible="classDialogVisible"
      v-model:exam-dialog-visible="examDialogVisible"
      :class-form="classForm" :exam-form="examForm"
      :editing-class="editingClass" :editing-exam="editingExam"
      :courses="courses" :weekdays="weekdays" :saving="saving" :deleting="deleting"
      :suggested-exam-title="suggestedExamTitle"
      @add-course="addCourse" @save-class="saveClassSession" @save-exam="saveExam" @remove-class="removeClassSession"
    />

    <AcademicIntegrationDialog
      v-if="integrationDialogVisible"
      :semester-start="semesterStartDate"
      v-model="integrationDialogVisible"
      @synced="handleIntegrationSynced"
    />
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElButton,
  ElCheckbox,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
} from 'element-plus'

import { academicCalendarApi, coursesApi, studyPreferencesApi } from '../api'
import { editBaseline, editRequestConfig } from '../utils/editPrecondition'
import { formatDateTime } from '../utils/format'
import { computeCurrentWeek } from '../utils/semesterWeek'

const AcademicEntryForms = defineAsyncComponent(() => import('../components/AcademicEntryForms.vue'))
const AcademicIntegrationDialog = defineAsyncComponent(() => import('../components/AcademicIntegrationDialog.vue'))
const route = useRoute()
const router = useRouter()

const weekdays = [
  { value: 1, short: '一', label: '星期一' },
  { value: 2, short: '二', label: '星期二' },
  { value: 3, short: '三', label: '星期三' },
  { value: 4, short: '四', label: '星期四' },
  { value: 5, short: '五', label: '星期五' },
  { value: 6, short: '六', label: '星期六' },
  { value: 7, short: '日', label: '星期日' },
]

const chinaTimeZone = 'Asia/Shanghai'
const weekdayKey = new Intl.DateTimeFormat('en-US', { timeZone: chinaTimeZone, weekday: 'short' }).format(new Date())
const todayWeekday = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 }[weekdayKey] || 1
const savedWeek = Number.parseInt(window.localStorage.getItem('study-academic-week') || '', 10)
const selectedWeek = ref(Number.isInteger(savedWeek) && savedWeek >= 1 && savedWeek <= 30 ? savedWeek : 1)
const activeWeekday = ref(todayWeekday)
const includePastExams = ref(false)
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const error = ref('')
const courses = ref([])
const classSessions = ref([])
const exams = ref([])
const classDialogVisible = ref(false)
const examDialogVisible = ref(false)
const integrationDialogVisible = ref(false)
const editingClass = ref(null)
const editingExam = ref(null)
let loadRequestId = 0

const semesterStartDate = ref('')
const semesterStartDraft = ref('')
const semesterStartSaving = ref(false)
const semesterCurrentWeek = computed(() => computeCurrentWeek(semesterStartDate.value))

const classForm = reactive(emptyClassForm())
const examForm = reactive(emptyExamForm())
const suggestedExamTitle = computed(() => {
  const course = courses.value.find(item => item.id === examForm.course_id)
  return course ? `${course.name}${examTypeLabel(examForm.exam_type)}` : ''
})
function addCourse(course) {
  if (!courses.value.some(item => item.id === course.id)) courses.value.push(course)
}
const activeDay = computed(() => weekdays.find((day) => day.value === activeWeekday.value))
const nearestExam = computed(() => exams.value.find((exam) => !isPastExam(exam)) || null)
const todaySessions = computed(() => sessionsFor(todayWeekday).filter((item) => item.end_time.slice(0, 5) >= currentTime()))
const todayHeadline = computed(() => {
  const next = todaySessions.value[0]
  if (next) return `下一节：${next.course_name}`
  const total = sessionsFor(todayWeekday).length
  return total ? '今天的课程已经结束' : '今天没有固定课程'
})
const todayDetail = computed(() => {
  const next = todaySessions.value[0]
  if (next) return `${formatTimeRange(next)} · ${next.location || '地点待补充'}${next.teacher ? ` · ${next.teacher}` : ''}`
  return nearestExam.value ? `可以把空档留给 ${nearestExam.value.course_name} 的考试准备。` : '可以把空档留给复习、资料整理或休息。'
})
const todayLabel = computed(() => examDateParts(new Date().toISOString()))

function emptyClassForm(weekday = todayWeekday) {
  return {
    course_id: courses.value.length === 1 ? courses.value[0].id : null,
    weekday,
    start_time: '08:00',
    end_time: '09:40',
    location: '',
    start_week: 1,
    end_week: 18,
    week_pattern: 'all',
    note: '',
  }
}

function emptyExamForm() {
  return {
    course_id: courses.value.length === 1 ? courses.value[0].id : null,
    title: '',
    exam_type: 'final',
    starts_at: '',
    ends_at: '',
    location: '',
    seat_number: '',
    note: '',
  }
}

function assignForm(target, source) {
  Object.keys(target).forEach((key) => { target[key] = source[key] ?? (key === 'course_id' ? null : '') })
}

function sessionsFor(weekday) {
  return classSessions.value.filter((item) => item.weekday === weekday)
}

function safeCourseColor(value) {
  return /^#[0-9a-f]{6}$/i.test(String(value || '')) ? value : '#5964ed'
}

function weekPatternLabel(value) {
  return { all: '每周', odd: '单周', even: '双周' }[value] || '每周'
}

function examTypeLabel(value) {
  return { quiz: '随堂测验', midterm: '期中考试', final: '期末考试', other: '其他考试' }[value] || '考试'
}

function formatTimeRange(item) {
  return `${item.start_time.slice(0, 5)}–${item.end_time.slice(0, 5)}`
}

function formatExamRange(exam) {
  if (!exam.ends_at) return formatDateTime(exam.starts_at)
  const start = new Date(exam.starts_at)
  const end = new Date(exam.ends_at)
  const startParts = chinaParts(start)
  const endParts = chinaParts(end)
  const sameDay = startParts.dateKey === endParts.dateKey
  const endOptions = sameDay ? { hour: '2-digit', minute: '2-digit' } : {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }
  const endText = new Intl.DateTimeFormat('zh-CN', { timeZone: chinaTimeZone, ...endOptions }).format(end)
  return `${formatDateTime(exam.starts_at)} – ${endText}`
}

function examDateParts(value) {
  const date = new Date(value)
  return {
    month: new Intl.DateTimeFormat('zh-CN', { timeZone: chinaTimeZone, month: 'short' }).format(date),
    day: new Intl.DateTimeFormat('zh-CN', { timeZone: chinaTimeZone, day: '2-digit' }).format(date),
    weekday: new Intl.DateTimeFormat('zh-CN', { timeZone: chinaTimeZone, weekday: 'short' }).format(date),
  }
}

function countdownLabel(value) {
  const target = chinaParts(new Date(value))
  const today = chinaParts(new Date())
  const targetDay = Date.UTC(target.year, target.month - 1, target.day)
  const localToday = Date.UTC(today.year, today.month - 1, today.day)
  const days = Math.round((targetDay - localToday) / 86400000)
  if (days < 0) return '已结束'
  if (days === 0) return '今天'
  if (days === 1) return '明天'
  return `还有 ${days} 天`
}

function isPastExam(exam) {
  return new Date(exam.ends_at || exam.starts_at).getTime() < Date.now()
}

function currentTime() {
  const now = chinaParts(new Date())
  return `${String(now.hour).padStart(2, '0')}:${String(now.minute).padStart(2, '0')}`
}

function toLocalDatetime(value) {
  if (!value) return ''
  const date = chinaParts(new Date(value))
  const part = (number) => String(number).padStart(2, '0')
  return `${date.year}-${part(date.month)}-${part(date.day)}T${part(date.hour)}:${part(date.minute)}:00`
}

function chinaParts(value) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: chinaTimeZone,
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(value).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]))
  const year = Number(parts.year)
  const month = Number(parts.month)
  const day = Number(parts.day)
  return {
    year,
    month,
    day,
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    dateKey: `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
  }
}

function normalizeOptional(value) {
  const trimmed = String(value || '').trim()
  return trimmed || null
}

async function loadPage() {
  const requestId = ++loadRequestId
  loading.value = true
  error.value = ''
  try {
    const [courseRows, overview] = await Promise.all([
      coursesApi.list(),
      academicCalendarApi.overview(selectedWeek.value, includePastExams.value),
    ])
    if (requestId !== loadRequestId) return
    courses.value = Array.isArray(courseRows) ? courseRows : []
    classSessions.value = Array.isArray(overview?.class_sessions) ? overview.class_sessions : []
    exams.value = Array.isArray(overview?.exams) ? overview.exams : []
  } catch (loadError) {
    if (requestId !== loadRequestId) return
    courses.value = []
    classSessions.value = []
    exams.value = []
    error.value = loadError.message
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

function changeWeek(delta) {
  selectedWeek.value = Math.min(30, Math.max(1, selectedWeek.value + delta))
}

function openClassDialog(item = null, weekday = activeWeekday.value) {
  editingClass.value = item ? { ...item } : null
  assignForm(classForm, item ? {
    ...item,
    start_time: item.start_time.slice(0, 5),
    end_time: item.end_time.slice(0, 5),
  } : emptyClassForm(weekday))
  classDialogVisible.value = true
}

function openExamDialog(item = null) {
  editingExam.value = item ? { ...item } : null
  assignForm(examForm, item ? {
    ...item,
    starts_at: toLocalDatetime(item.starts_at),
    ends_at: toLocalDatetime(item.ends_at),
  } : emptyExamForm())
  examDialogVisible.value = true
}

async function saveClassSession() {
  if (saving.value) return
  if (!classForm.course_id || !classForm.start_time || !classForm.end_time) {
    ElMessage.warning('请填写课程、星期和上下课时间')
    return
  }
  if (classForm.end_time <= classForm.start_time) {
    ElMessage.warning('下课时间必须晚于上课时间')
    return
  }
  if (classForm.end_week < classForm.start_week) {
    ElMessage.warning('结束周不能早于开始周')
    return
  }
  const payload = {
    ...classForm,
    location: normalizeOptional(classForm.location),
    note: normalizeOptional(classForm.note),
  }
  saving.value = true
  try {
    if (editingClass.value) {
      const config = editRequestConfig(editBaseline(editingClass.value))
      await academicCalendarApi.updateClassSession(editingClass.value.id, payload, config)
      ElMessage.success('课程时间已更新')
    } else {
      await academicCalendarApi.createClassSession(payload)
      ElMessage.success('课程已加入课表')
    }
    classDialogVisible.value = false
    await loadPage()
  } catch (saveError) {
    ElMessage.error(saveError.message)
  } finally {
    saving.value = false
  }
}

async function saveExam() {
  if (saving.value) return
  if (!examForm.course_id || !examForm.starts_at) {
    ElMessage.warning('请选择或新建课程，再填写开始时间')
    return
  }
  if (examForm.ends_at && examForm.ends_at <= examForm.starts_at) {
    ElMessage.warning('结束时间必须晚于开始时间')
    return
  }
  const payload = {
    ...examForm,
    title: examForm.title.trim() || suggestedExamTitle.value,
    ends_at: examForm.ends_at || null,
    location: normalizeOptional(examForm.location),
    seat_number: normalizeOptional(examForm.seat_number),
    note: normalizeOptional(examForm.note),
  }
  saving.value = true
  try {
    if (editingExam.value) {
      const config = editRequestConfig(editBaseline(editingExam.value))
      await academicCalendarApi.updateExam(editingExam.value.id, payload, config)
      ElMessage.success('考试安排已更新')
    } else {
      await academicCalendarApi.createExam(payload)
      ElMessage.success('考试已加入日程')
    }
    examDialogVisible.value = false
    await loadPage()
  } catch (saveError) {
    ElMessage.error(saveError.message)
  } finally {
    saving.value = false
  }
}

async function removeClassSession(item) {
  try {
    await ElMessageBox.confirm(`确定从课表删除“${item.course_name}”这节课吗？`, '删除课程时间', {
      confirmButtonText: '删除', cancelButtonText: '保留', type: 'warning',
    })
  } catch {
    return
  }
  deleting.value = true
  try {
    await academicCalendarApi.removeClassSession(item.id, editRequestConfig(editBaseline(item)))
    classDialogVisible.value = false
    ElMessage.success('课程时间已删除')
    await loadPage()
  } catch (removeError) {
    ElMessage.error(removeError.message)
  } finally {
    deleting.value = false
  }
}

async function removeExam(item) {
  try {
    await ElMessageBox.confirm(`确定删除“${item.title}”吗？`, '删除考试安排', {
      confirmButtonText: '删除', cancelButtonText: '保留', type: 'warning',
    })
  } catch {
    return
  }
  try {
    await academicCalendarApi.removeExam(item.id, editRequestConfig(editBaseline(item)))
    examDialogVisible.value = false
    ElMessage.success('考试安排已删除')
    await loadPage()
  } catch (removeError) {
    ElMessage.error(removeError.message)
  }
}

async function handleIntegrationSynced(syncInfo = {}) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(syncInfo.semester_start || '')) {
    try {
      if (semesterStartDate.value !== syncInfo.semester_start) {
        await studyPreferencesApi.update({ semester_start_date: syncInfo.semester_start })
        semesterStartDate.value = syncInfo.semester_start
        semesterStartDraft.value = syncInfo.semester_start
      }
    } catch {
      ElMessage.warning('课表已导入，但开学日未保存。请在课表上补充开学日以自动定位本周。')
    }
    const [year, month, day] = syncInfo.semester_start.split('-').map(Number)
    const semesterStart = Date.UTC(year, month - 1, day)
    const today = chinaParts(new Date())
    const chinaToday = Date.UTC(today.year, today.month - 1, today.day)
    const importedWeek = Math.min(30, Math.max(1, Math.floor((chinaToday - semesterStart) / 604800000) + 1))
    if (importedWeek !== selectedWeek.value) {
      selectedWeek.value = importedWeek
      return
    }
  }
  await loadPage()
}

watch(selectedWeek, (value) => {
  window.localStorage.setItem('study-academic-week', String(value))
  loadPage()
})
watch(includePastExams, loadPage)
watch(() => route.query.action, async action => {
  if (action !== 'import') return
  integrationDialogVisible.value = true
  const query = { ...route.query }
  delete query.action
  await router.replace({ path: route.path, query })
}, { immediate: true })

async function loadSemesterStart() {
  try {
    const preference = await studyPreferencesApi.get()
    semesterStartDate.value = preference?.semester_start_date || ''
  } catch {
    // 读取失败不影响周次手动选择，只是暂时不显示自动定位提示。
  }
}

async function saveSemesterStart() {
  const value = semesterStartDraft.value
  if (!value || semesterStartSaving.value) return
  semesterStartSaving.value = true
  try {
    await studyPreferencesApi.update({ semester_start_date: value })
    semesterStartDate.value = value
    const week = computeCurrentWeek(value)
    if (week && week !== selectedWeek.value) selectedWeek.value = week
  } catch (requestError) {
    error.value = requestError?.message || '开学日保存失败，请稍后重试'
  } finally {
    semesterStartSaving.value = false
  }
}

function jumpToCurrentWeek() {
  if (semesterCurrentWeek.value) selectedWeek.value = semesterCurrentWeek.value
}

onMounted(() => {
  loadPage()
  loadSemesterStart()
})
</script>

<style scoped>
.schedule-switch { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: -4px 0 22px; border-bottom: 1px solid var(--ledger-line); }
.schedule-switch > * { display: flex; align-items: center; gap: 8px; padding: 12px 2px; color: var(--ledger-muted); font-size: 14px; text-decoration: none; }
.schedule-switch > span { border-bottom: 2px solid var(--ledger-link); color: var(--ledger-link); font-weight: 600; }
.schedule-switch small { font-weight: 400; font-size: 12px; color: var(--ledger-muted); }
.academic-calendar-page { --calendar-blue: var(--ledger-link); --calendar-mint: #dceee3; --calendar-yellow: #ffc857; color: var(--ledger-ink); }
.calendar-kicker, .section-eyebrow, .ticket-time, .today-stamp, .exam-date-block, .week-switcher { font-family: inherit; font-variant-numeric: tabular-nums; }
.calendar-intro h1 { font-family: inherit; font-size: clamp(24px, 2.3vw, 30px); font-weight: 700; letter-spacing: 0; }
.calendar-kicker, .section-eyebrow { color: var(--ledger-muted); font-size: 12px; font-weight: 700; letter-spacing: 0; }
.course-gate, .calendar-error { display: flex; align-items: center; gap: 16px; margin-bottom: 18px; padding: 18px; background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 6px; }
.semester-week-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: -6px 0 16px; padding: 10px 14px; background: #f1f7f3; border: 1px solid #c8ddd1; border-radius: 6px; color: var(--ledger-muted); font-size: 12.5px; }
.semester-week-bar strong { color: var(--calendar-blue); }
.semester-week-bar button { min-height: 36px; padding: 0 12px; color: var(--calendar-blue); background: #fff; border: 1px solid #c8ddd1; border-radius: 4px; font-weight: 700; cursor: pointer; }
.semester-week-bar button:hover { border-color: var(--calendar-blue); }
.semester-start-setter { display: inline-flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.semester-start-setter input { min-height: 36px; padding: 0 9px; border: 1px solid #c8ddd1; border-radius: 4px; background: #fff; color: var(--ledger-ink); font-size: 12.5px; }
.course-gate-mark { display: grid; place-items: center; width: 44px; height: 44px; flex: 0 0 auto; color: #fff; background: var(--calendar-blue); border-radius: 4px; font-weight: 800; }
.course-gate > div:nth-child(2) { min-width: 0; flex: 1; }
.course-gate strong { font-size: 15px; }
.course-gate p { margin: 5px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.55; }
.course-gate a { display: inline-flex; align-items: center; min-height: 44px; padding: 0 12px; border: 1px solid var(--ledger-line); border-radius: 4px; font-size: 13px; font-weight: 700; }
.calendar-error { justify-content: space-between; color: #9f3c3c; border-color: #e2b8b8; background: #fff8f7; }
.calendar-error button { min-height: 40px; padding: 0 12px; color: #923737; background: #fff; border: 1px solid #d9a7a7; border-radius: 4px; cursor: pointer; }
.today-ribbon { display: grid; grid-template-columns: auto minmax(0, 1fr) minmax(220px, .42fr); align-items: stretch; margin-bottom: 18px; overflow: hidden; background: #f1f7f3; border: 1px solid var(--ledger-line); border-radius: 12px; }
.today-stamp { display: grid; align-content: center; min-width: 104px; padding: 16px 20px; color: var(--ledger-link); background: var(--calendar-mint); text-align: center; }
.today-stamp span, .today-stamp small { font-size: 12px; font-weight: 700; letter-spacing: 0; }
.today-stamp strong { margin: 3px 0; font-size: 22px; font-weight: 700; line-height: 1; }
.today-copy { min-width: 0; padding: 18px 22px; color: var(--ledger-ink); }
.today-copy .section-eyebrow { color: var(--ledger-muted); }
.today-copy h2 { margin: 6px 0 5px; font-family: inherit; font-size: 16px; font-weight: 700; }
.today-copy p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
.nearest-exam { display: grid; align-content: center; gap: 5px; padding: 17px 21px; background: #ffffff; border-left: 1px solid var(--ledger-line); }
.nearest-exam span { color: var(--ledger-muted); font-size: 11px; font-weight: 700; }
.nearest-exam strong { color: var(--ledger-ink); font-size: 14px; overflow-wrap: anywhere; }
.nearest-exam small { color: var(--ledger-muted); line-height: 1.45; }
.nearest-exam.is-empty { background: #f5f8f7; }
.schedule-ledger, .exam-ledger { margin-bottom: 18px; background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 12px; }
.ledger-header, .exam-header { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 20px 22px; border-bottom: 1px solid var(--ledger-line); }
.ledger-header h2, .exam-header h2 { margin: 5px 0 0; font-family: inherit; font-size: 16px; font-weight: 700; }
.ledger-header p, .exam-header p { margin: 5px 0 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; }
.week-switcher { display: grid; grid-template-columns: 44px 66px 44px; gap: 6px; }
.week-switcher :deep(.el-input-number) { width: 100%; min-width: 0; }
.week-switcher button { min-height: 44px; color: var(--ledger-ink); background: #fff; border: 1px solid var(--ledger-line); border-radius: 4px; cursor: pointer; }
.week-switcher button:disabled { color: #a4adba; background: #f5f8f7; cursor: not-allowed; }
.week-switcher :deep(.el-input__wrapper) { min-height: 44px; padding: 0 8px; }
.desktop-week-board { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); min-width: 0; }
.day-column { min-width: 0; border-right: 1px solid var(--ledger-line); }
.day-column:last-child { border-right: 0; }
.day-column > header { display: flex; align-items: center; justify-content: space-between; gap: 7px; min-height: 50px; padding: 12px 11px; background: #f5f8f7; border-bottom: 1px solid var(--ledger-line); }
.day-column > header strong { min-width: 0; font-size: 12px; }
.day-column > header small { color: var(--ledger-muted); font-size: 12px; }
.day-column.is-today > header { background: #f1f7f3; }
.day-column.is-today > header strong { color: var(--calendar-blue); }
.day-session-list { display: flex; flex-direction: column; gap: 8px; min-height: 238px; padding: 9px; }
.class-ticket { position: relative; width: 100%; min-height: 116px; padding: 11px 10px 10px 13px; overflow: hidden; color: var(--ledger-ink); background: #fff; border: 1px solid var(--ledger-line); border-radius: 5px; cursor: pointer; text-align: left; }
.class-ticket::before { position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--course-color); content: ""; }
.class-ticket:hover { border-color: var(--ledger-indigo); }
.class-ticket .ticket-time { display: block; color: var(--ledger-muted); font-size: 12px; font-weight: 700; }
.class-ticket strong { display: block; margin-top: 7px; font-size: 13px; line-height: 1.35; overflow-wrap: anywhere; }
.class-ticket > span:not(.ticket-time), .class-ticket small { display: block; margin-top: 6px; color: var(--ledger-muted); font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }
.empty-day { display: grid; place-items: center; gap: 4px; min-height: 82px; color: var(--ledger-muted); background: transparent; border: 1px dashed var(--ledger-line); border-radius: 5px; cursor: pointer; font-size: 11px; }
.empty-day span { font-size: 20px; line-height: 1; }
.empty-day:hover { color: var(--calendar-blue); border-color: #c8ddd1; background: #f1f7f3; }
.mobile-week-board { display: none; }
.exam-header { align-items: flex-end; }
.past-exam-toggle { display: inline-flex; align-items: center; min-height: 44px; }
.exam-list { padding: 0 22px 12px; }
.exam-ticket { display: grid; grid-template-columns: 82px minmax(0, 1fr) auto; gap: 18px; align-items: stretch; padding: 18px 0; border-bottom: 1px dashed var(--ledger-line); }
.exam-ticket:last-child { border-bottom: 0; }
.exam-ticket.is-past { opacity: .66; }
.exam-date-block { display: grid; align-content: center; padding: 10px; color: var(--ledger-ink); background: #fff4d8; border: 1px solid #efdba8; border-radius: 4px; text-align: center; }
.exam-date-block span, .exam-date-block small { font-size: 12px; font-weight: 700; letter-spacing: 0; }
.exam-date-block strong { margin: 3px 0; font-size: 20px; font-weight: 700; line-height: 1; }
.exam-main { min-width: 0; }
.exam-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.exam-tags span { padding: 3px 7px; color: var(--ledger-ink); background: #f5f8f7; border-radius: 3px; font-size: 12px; font-weight: 700; }
.exam-tags span:last-child { color: #85551e; background: #fff2d7; }
.exam-main h3 { margin: 8px 0 2px; font-family: inherit; font-size: 14px; font-weight: 700; overflow-wrap: anywhere; }
.exam-main > p { margin: 0; color: var(--ledger-muted); font-size: 12px; overflow-wrap: anywhere; }
.exam-main dl { display: flex; flex-wrap: wrap; gap: 8px 22px; margin: 12px 0 0; }
.exam-main dl div { min-width: 150px; }
.exam-main dt { color: var(--ledger-muted); font-size: 12px; }
.exam-main dd { margin: 3px 0 0; color: var(--ledger-ink); font-size: 12px; overflow-wrap: anywhere; }
.exam-actions { display: flex; align-items: center; gap: 6px; }
.exam-actions button { min-width: 52px; min-height: 44px; color: var(--ledger-ink); background: #fff; border: 1px solid var(--ledger-line); border-radius: 4px; cursor: pointer; }
.exam-actions button:hover { color: var(--calendar-blue); border-color: #c8ddd1; }
.exam-actions .danger-action:hover { color: #a13e3e; border-color: #d9aaaa; }
.exam-empty { display: grid; justify-items: center; padding: 40px 20px 44px; text-align: center; }
.exam-empty > span { color: var(--ledger-muted); font-family: inherit; font-size: 11px; letter-spacing: 0; }
.exam-empty strong { margin-top: 10px; font-size: 16px; }
.exam-empty p { margin: 7px 0 18px; color: var(--ledger-muted); font-size: 13px; }

@media (max-width: 1100px) {
  .desktop-week-board { display: none; }
  .mobile-week-board { display: block; }
  .mobile-day-tabs { display: grid; grid-template-columns: repeat(7, minmax(48px, 1fr)); overflow-x: auto; border-bottom: 1px solid var(--ledger-line); }
  .mobile-day-tabs button { min-width: 48px; min-height: 58px; padding: 7px 4px; color: var(--ledger-muted); background: #f5f8f7; border: 0; border-right: 1px solid var(--ledger-line); cursor: pointer; }
  .mobile-day-tabs button:last-child { border-right: 0; }
  .mobile-day-tabs span, .mobile-day-tabs strong { display: block; }
  .mobile-day-tabs span { font-size: 11px; }
  .mobile-day-tabs strong { margin-top: 3px; font-size: 14px; }
  .mobile-day-tabs button.is-active { color: #fff; background: var(--ledger-link); }
  .mobile-day-tabs button.is-today:not(.is-active) { color: var(--ledger-ink); box-shadow: inset 0 -3px var(--calendar-mint); }
  .mobile-day-panel { padding: 16px; }
  .mobile-day-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 12px; }
  .mobile-day-heading div { display: grid; gap: 3px; }
  .mobile-day-heading span { color: var(--ledger-muted); font-size: 11px; }
  .mobile-day-heading strong { font-size: 15px; }
  .mobile-class-row { display: grid; grid-template-columns: 74px minmax(0, 1fr) auto; align-items: center; gap: 13px; width: 100%; min-height: 72px; margin-top: 8px; padding: 10px 12px; color: var(--ledger-ink); background: #fff; border: 1px solid var(--ledger-line); border-left: 5px solid var(--course-color); border-radius: 5px; cursor: pointer; text-align: left; }
  .mobile-class-time { font-family: inherit; font-size: 11px; font-weight: 700; }
  .mobile-class-main { min-width: 0; display: grid; gap: 5px; }
  .mobile-class-main strong, .mobile-class-main small { overflow-wrap: anywhere; }
  .mobile-class-main small { color: var(--ledger-muted); line-height: 1.4; }
  .mobile-empty-day { padding: 24px 10px; color: var(--ledger-muted); background: #f5f8f7; border: 1px dashed var(--ledger-line); border-radius: 5px; text-align: center; font-size: 12px; }
}

@media (max-width: 760px) {
  .today-ribbon { grid-template-columns: 78px minmax(0, 1fr); }
  .today-stamp { min-width: 78px; padding: 14px 10px; }
  .today-copy { padding: 17px 15px; }
  .calendar-intro h1 { font-size: 25px; }
  .today-copy h2 { font-size: 15px; }
  .nearest-exam { grid-column: 1 / -1; min-height: 78px; border-top: 1px solid var(--ledger-line); border-left: 0; }
  .ledger-header, .exam-header { align-items: flex-start; flex-direction: column; padding: 18px 16px; }
  .week-switcher { width: 100%; grid-template-columns: 48px minmax(0, 1fr) 48px; }
  .past-exam-toggle { min-height: 32px; }
  .exam-list { padding: 0 16px 8px; }
  .exam-ticket { grid-template-columns: 68px minmax(0, 1fr); gap: 12px; }
  .exam-date-block { min-height: 78px; }
  .exam-main dl { display: grid; grid-template-columns: 1fr; gap: 7px; }
  .exam-main dl div { min-width: 0; }
  .exam-actions { grid-column: 1 / -1; justify-content: flex-end; }
}

@media (prefers-reduced-motion: reduce) {
  .class-ticket { transition: none; }
  .class-ticket:hover { transform: none; }
}
</style>
