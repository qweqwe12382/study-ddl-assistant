<template>
  <div>
    <div class="page-intro">
      <div>
        <h1>复习计划</h1>
        <p>根据课程资料、标签和未完成任务，生成一份可以随时调整的每日清单。</p>
      </div>
      <div class="page-actions">
        <el-button @click="download(exportsApi.tasksCsvUrl())">导出 DDL CSV</el-button>
        <el-button @click="download(exportsApi.materialsMarkdownUrl())">导出资料 Markdown</el-button>
        <el-button :disabled="!currentPlan" @click="download(exportsApi.studyPlanMarkdownUrl(currentPlan.id))">导出计划 Markdown</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon closable class="mb-18" @close="error = ''" />

    <el-card class="content-card plan-config" shadow="never" v-loading="loading">
      <div class="card-heading">
        <h2>生成新的复习计划</h2>
        <el-tag type="info" effect="plain">不会覆盖已有计划</el-tag>
      </div>
      <el-form :model="planForm" label-width="116px" class="plan-form">
        <el-form-item label="课程" required>
          <el-select v-model="planForm.course_id" placeholder="选择课程" style="width: 260px" @change="onCourseChange">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="考试日期" required>
          <el-date-picker v-model="planForm.exam_date" type="date" value-format="YYYY-MM-DD" placeholder="选择考试日期" />
        </el-form-item>
        <el-form-item label="每日学习时间" required>
          <el-input-number v-model="planForm.daily_minutes" :min="15" :max="1440" />
          <span class="form-suffix">分钟</span>
        </el-form-item>
        <el-form-item label="计划名称">
          <el-input v-model="planForm.title" placeholder="不填写则使用课程名生成" style="width: 260px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="generating" :disabled="!courses.length" @click="generatePlan">生成计划</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card plan-card" shadow="never" v-loading="plansLoading">
      <div class="table-toolbar">
        <div>
          <h2>计划明细 <el-tag v-if="currentPlan" size="small" effect="plain">{{ currentPlan.items.length }} 天</el-tag></h2>
          <div v-if="currentPlan" class="plan-meta">
            {{ currentPlan.title }} · 考试日期 {{ currentPlan.exam_date }} · 每日 {{ currentPlan.daily_minutes }} 分钟 ·
            已完成 {{ completedItemCount }}/{{ currentPlan.items.length }} 天
          </div>
        </div>
        <div class="toolbar-actions">
          <el-select v-if="plans.length" v-model="selectedPlanId" placeholder="选择已有计划" style="width: 240px" @change="selectPlan">
            <el-option v-for="plan in plans" :key="plan.id" :label="`${plan.title} · ${plan.exam_date}`" :value="plan.id" />
          </el-select>
          <el-button v-if="currentPlan" plain type="warning" @click="archivePlan">归档</el-button>
          <el-button v-if="currentPlan" type="primary" :loading="saving" @click="savePlan">保存修改</el-button>
        </div>
      </div>

      <div v-if="currentPlan" class="plan-summary">
        <div class="summary-item"><span>计划总时长</span><strong>{{ totalMinutes }} 分钟</strong></div>
        <div class="summary-item"><span>已完成时长</span><strong>{{ completedMinutes }} 分钟</strong></div>
        <div class="summary-progress">
          <div class="summary-progress-label"><span>完成进度</span><strong>{{ progressPercent }}%</strong></div>
          <el-progress :percentage="progressPercent" :show-text="false" :stroke-width="8" />
        </div>
      </div>

      <div v-if="currentPlan?.warnings?.length" class="plan-warnings">
        <el-alert v-for="warning in currentPlan.warnings" :key="warning" :title="warning" type="warning" show-icon :closable="false" />
      </div>

      <div v-if="currentPlan" class="table-wrap plan-table-wrap">
        <el-table :data="currentPlan.items" row-key="id" empty-text="当前计划没有明细">
          <el-table-column label="日期" width="145">
            <template #default="{ row }">
              <el-date-picker v-model="row.date" type="date" value-format="YYYY-MM-DD" size="small" :disabled-date="disabledAfterExam" />
            </template>
          </el-table-column>
          <el-table-column label="阶段 / 主题" min-width="260">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.phase }}</el-tag>
              <el-input v-model="row.title" size="small" class="item-title-input" />
            </template>
          </el-table-column>
          <el-table-column label="复习内容" min-width="370">
            <template #default="{ row }"><el-input v-model="row.content" type="textarea" :rows="2" size="small" /></template>
          </el-table-column>
          <el-table-column label="时长" width="125">
            <template #default="{ row }">
              <el-input-number v-model="row.minutes" :min="1" :max="1440" size="small" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="125">
            <template #default="{ row }">
              <el-select v-model="row.status" size="small">
                <el-option label="未开始" value="not_started" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="已完成" value="completed" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="来源" min-width="150">
            <template #default="{ row }"><span class="row-meta">{{ sourceLabel(row) }}</span></template>
          </el-table-column>
        </el-table>
      </div>
      <div v-else class="empty-state plan-empty">请选择课程并生成一份复习计划。</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { coursesApi, exportsApi, studyPlansApi } from '../api'

const loading = ref(false)
const plansLoading = ref(false)
const generating = ref(false)
const saving = ref(false)
const error = ref('')
const courses = ref([])
const plans = ref([])
const currentPlan = ref(null)
const selectedPlanId = ref(null)

const planForm = reactive({
  course_id: null,
  exam_date: defaultExamDate(),
  daily_minutes: 60,
  title: '',
})

const progressPercent = computed(() => {
  if (!currentPlan.value?.items?.length) return 0
  return Math.round((completedItemCount.value / currentPlan.value.items.length) * 100)
})
const completedItemCount = computed(() => currentPlan.value?.items?.filter((item) => item.status === 'completed').length || 0)
const totalMinutes = computed(() => currentPlan.value?.items?.reduce((total, item) => total + (item.minutes || 0), 0) || 0)
const completedMinutes = computed(() => currentPlan.value?.items?.reduce((total, item) => total + (item.status === 'completed' ? item.minutes || 0 : 0), 0) || 0)

function defaultExamDate() {
  const value = new Date()
  value.setDate(value.getDate() + 14)
  return value.toISOString().slice(0, 10)
}

function syncFormFromPlan(plan) {
  if (!plan) return
  planForm.course_id = plan.course_id
  planForm.exam_date = plan.exam_date || defaultExamDate()
  planForm.daily_minutes = plan.daily_minutes || 60
  planForm.title = plan.title || ''
}

async function loadPlans(courseId = planForm.course_id) {
  if (!courseId) {
    plans.value = []
    currentPlan.value = null
    selectedPlanId.value = null
    return
  }
  plansLoading.value = true
  try {
    plans.value = await studyPlansApi.list(courseId)
    const selected = plans.value.find((plan) => plan.id === selectedPlanId.value) || plans.value[0] || null
    currentPlan.value = selected
    selectedPlanId.value = selected?.id || null
    syncFormFromPlan(selected)
  } catch (err) {
    error.value = err.message
  } finally {
    plansLoading.value = false
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    courses.value = await coursesApi.list()
    if (!planForm.course_id && courses.value.length) planForm.course_id = courses.value[0].id
    await loadPlans()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function onCourseChange() {
  selectedPlanId.value = null
  currentPlan.value = null
  loadPlans(planForm.course_id)
}

function selectPlan(planId) {
  currentPlan.value = plans.value.find((plan) => plan.id === planId) || null
  syncFormFromPlan(currentPlan.value)
}

async function generatePlan() {
  if (!planForm.course_id || !planForm.exam_date) {
    ElMessage.warning('请选择课程并填写考试日期')
    return
  }
  generating.value = true
  try {
    const generated = await studyPlansApi.generate({
      course_id: planForm.course_id,
      exam_date: planForm.exam_date,
      daily_minutes: planForm.daily_minutes,
      title: planForm.title.trim() || null,
    })
    plans.value = [generated, ...plans.value]
    currentPlan.value = generated
    selectedPlanId.value = generated.id
    syncFormFromPlan(generated)
    ElMessage.success('复习计划已生成，可以继续编辑明细')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    generating.value = false
  }
}

function disabledAfterExam(value) {
  if (!currentPlan.value?.exam_date) return false
  const exam = new Date(`${currentPlan.value.exam_date}T23:59:59`)
  return value.getTime() > exam.getTime()
}

function sourceLabel(item) {
  const labels = []
  if (item.source_material_ids?.length) labels.push(`资料 #${item.source_material_ids.join(', #')}`)
  if (item.source_task_ids?.length) labels.push(`任务 #${item.source_task_ids.join(', #')}`)
  return labels.join('、') || '课程范围'
}

async function savePlan() {
  if (!currentPlan.value) return
  saving.value = true
  try {
    const saved = await studyPlansApi.update(currentPlan.value.id, {
      title: planForm.title.trim() || null,
      exam_date: planForm.exam_date,
      daily_minutes: planForm.daily_minutes,
      items: currentPlan.value.items,
    })
    currentPlan.value = saved
    const index = plans.value.findIndex((plan) => plan.id === saved.id)
    if (index >= 0) plans.value[index] = saved
    syncFormFromPlan(saved)
    ElMessage.success('计划修改已保存')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function archivePlan() {
  if (!currentPlan.value) return
  try {
    await ElMessageBox.confirm(`确定归档“${currentPlan.value.title}”吗？归档后不会出现在当前计划列表中。`, '归档计划', { type: 'warning' })
    await studyPlansApi.archive(currentPlan.value.id)
    ElMessage.success('计划已归档')
    selectedPlanId.value = null
    await loadPlans(planForm.course_id)
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

function download(url) {
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noreferrer'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

onMounted(loadData)
</script>

<style scoped>
.mb-18 { margin-bottom: 18px; }
.plan-config { margin-bottom: 22px; }
.plan-form { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 18px; }
.plan-form :deep(.el-form-item) { margin-bottom: 8px; }
.form-suffix { margin-left: 8px; color: #8993a4; font-size: 12px; }
.plan-meta { margin-top: 7px; color: #9aa3b2; font-size: 12px; }
.plan-summary { display: grid; grid-template-columns: 180px 180px minmax(260px, 1fr); gap: 22px; align-items: center; padding: 16px 22px; border-bottom: 1px solid #eef1f5; background: #fbfcfe; }
.summary-item { display: flex; flex-direction: column; gap: 6px; color: #8b96a6; font-size: 12px; }
.summary-item strong { color: #344054; font-size: 16px; }
.summary-progress-label { display: flex; justify-content: space-between; margin-bottom: 7px; color: #8b96a6; font-size: 12px; }
.summary-progress-label strong { color: #5964ed; }
.plan-warnings { display: grid; gap: 8px; padding: 16px 22px 0; }
.plan-table-wrap { padding-top: 10px; }
.plan-table-wrap :deep(.el-table td.el-table__cell) { vertical-align: top; }
.item-title-input { margin-top: 8px; }
.plan-empty { padding: 70px 0; }

@media (max-width: 1200px) {
  .plan-summary { grid-template-columns: 150px 150px minmax(220px, 1fr); }
}
</style>
