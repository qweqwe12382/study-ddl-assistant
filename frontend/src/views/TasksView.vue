<template>
  <div>
    <div class="page-intro">
      <div>
        <h1>DDL 任务</h1>
        <p>手动记录课程任务，先把重要日期放进一个清单。</p>
      </div>
      <div class="page-actions">
        <el-button @click="downloadFile(exportsApi.tasksCsvUrl())">导出 CSV</el-button>
        <el-button @click="downloadFile(exportsApi.tasksCalendarUrl())">导出待办日历</el-button>
        <el-button type="primary" @click="openCreate">新增任务</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon closable class="mb-18" @close="error = ''" />

    <el-card class="table-card" shadow="never" v-loading="loading">
      <div class="table-toolbar">
        <h2>
          任务清单
          <el-tag size="small" effect="plain">{{ filteredTasks.length }}<span v-if="hasActiveFilters"> / {{ tasks.length }}</span></el-tag>
        </h2>
        <div class="toolbar-actions">
          <el-select v-model="statusFilter" clearable placeholder="全部状态" style="width: 140px">
            <el-option label="未开始" value="not_started" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已逾期" value="overdue" />
          </el-select>
          <el-input v-model="keyword" placeholder="搜索任务" clearable style="width: 180px" />
          <el-button v-if="hasActiveFilters" link @click="resetFilters">清除筛选</el-button>
        </div>
      </div>
      <div class="table-wrap">
        <el-table :data="filteredTasks" :empty-text="tableEmptyText">
          <el-table-column label="任务名称" min-width="240">
            <template #default="{ row }">
              <div class="row-title">{{ row.name }}</div>
              <div class="row-meta">{{ row.task_type || '未分类' }} · 优先级 {{ row.priority }}</div>
            </template>
          </el-table-column>
          <el-table-column label="所属课程" width="150">
            <template #default="{ row }">{{ courseName(row.course_id) }}</template>
          </el-table-column>
          <el-table-column label="截止时间" width="170">
            <template #default="{ row }">
              <span :class="{ overdue: isOverdue(row) }">{{ formatDateTime(row.due_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }"><el-tag :type="displayStatusType(row)" size="small">{{ displayStatus(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="来源" min-width="150">
            <template #default="{ row }">
              <span :class="{ muted: !row.material_id && !row.source_material_name }">{{ materialName(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status !== 'completed'" link type="success" @click="completeTask(row)">完成</el-button>
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="removeTask(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑任务' : '新增任务'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="92px" class="dialog-form">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.name" placeholder="例如：完成实验一报告" />
        </el-form-item>
        <el-form-item label="所属课程">
          <el-select v-model="form.course_id" clearable placeholder="选择课程" style="width: 100%">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务类型">
          <el-input v-model="form.task_type" placeholder="作业 / 实验 / 考试 / 报告" />
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker
            v-model="form.due_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择截止时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-rate v-model="form.priority" :max="5" show-score text-color="#ff9900" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="未开始" value="not_started" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已逾期" value="overdue" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源资料">
          <el-select v-model="form.material_id" clearable placeholder="关联资料" style="width: 100%">
            <el-option v-for="material in materials" :key="material.id" :label="material.original_filename" :value="material.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="填写任务说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveTask">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  ElAlert,
  ElCard,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRate,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus'

import { coursesApi, exportsApi, materialsApi, tasksApi } from '../api'
import { downloadFile } from '../utils/download'
import { formatDateTime, isOverdue, statusLabel, statusType } from '../utils/format'

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const keyword = ref('')
const statusFilter = ref('')
const dialogVisible = ref(false)
const editingId = ref(null)
const courses = ref([])
const materials = ref([])
const tasks = ref([])
const form = reactive(emptyForm())
const hasActiveFilters = computed(() => Boolean(keyword.value.trim() || statusFilter.value))
const tableEmptyText = computed(() => hasActiveFilters.value ? '没有符合当前筛选条件的任务' : '还没有任务记录')

const filteredTasks = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  return tasks.value.filter((task) => {
    const matchStatus = !statusFilter.value || task.status === statusFilter.value
    const matchKeyword = !value || [task.name, task.description, task.task_type].filter(Boolean).join(' ').toLowerCase().includes(value)
    return matchStatus && matchKeyword
  })
})

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
}

function emptyForm() {
  return {
    name: '',
    course_id: null,
    material_id: null,
    task_type: '',
    description: '',
    due_at: '',
    priority: 3,
    status: 'not_started',
  }
}

function resetForm() {
  Object.assign(form, emptyForm())
  editingId.value = null
}

function courseName(courseId) {
  return courses.value.find((course) => course.id === courseId)?.name || '未归类课程'
}

function materialName(task) {
  return materials.value.find((material) => material.id === task.material_id)?.original_filename
    || (task.source_material_name ? `已删除：${task.source_material_name}` : '—')
}

function displayStatus(task) {
  if (isOverdue(task)) return '已逾期'
  return statusLabel(task.status)
}

function displayStatusType(task) {
  if (isOverdue(task)) return 'danger'
  return statusType(task.status)
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(task) {
  Object.assign(form, {
    name: task.name,
    course_id: task.course_id,
    material_id: task.material_id,
    task_type: task.task_type || '',
    description: task.description || '',
    due_at: task.due_at ? task.due_at.slice(0, 19) : '',
    priority: task.priority || 3,
    status: task.status,
  })
  editingId.value = task.id
  dialogVisible.value = true
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [courseData, materialData, taskData] = await Promise.all([
      coursesApi.list(),
      materialsApi.list(),
      tasksApi.list(),
    ])
    courses.value = courseData
    materials.value = materialData
    tasks.value = taskData
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function saveTask() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写任务名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      course_id: form.course_id,
      material_id: form.material_id,
      task_type: form.task_type.trim() || null,
      description: form.description.trim() || null,
      due_at: form.due_at || null,
      priority: form.priority,
      status: form.status,
    }
    if (editingId.value) {
      await tasksApi.update(editingId.value, payload)
      ElMessage.success('任务已更新')
    } else {
      await tasksApi.create(payload)
      ElMessage.success('任务已添加')
    }
    dialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function completeTask(task) {
  try {
    await tasksApi.complete(task.id)
    ElMessage.success('任务已完成')
    await loadData()
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function removeTask(task) {
  try {
    await ElMessageBox.confirm(`确定删除“${task.name}”吗？`, '删除任务', { type: 'warning' })
    await tasksApi.remove(task.id)
    ElMessage.success('任务已删除')
    await loadData()
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

onMounted(loadData)
</script>

<style scoped>
.mb-18 { margin-bottom: 18px; }
.overdue { color: #e45656; font-weight: 600; }
</style>
