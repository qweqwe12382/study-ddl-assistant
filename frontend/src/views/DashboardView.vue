<template>
  <div v-loading="loading">
    <div class="page-intro">
      <div>
        <h1>今天也为目标推进一点点</h1>
        <p>把分散的课程资料和截止时间，整理成清晰的下一步。</p>
      </div>
      <div class="page-actions">
        <el-button @click="$router.push('/materials')">管理资料</el-button>
        <el-button type="primary" @click="$router.push('/tasks')">新建任务</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon closable @close="error = ''" />
    <el-alert v-if="dashboard.next_action" :title="dashboard.next_action" type="info" show-icon class="dashboard-action" />

    <div class="stats-grid">
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon purple"><el-icon><List /></el-icon></div>
        <div class="stat-label">未完成任务</div>
        <div class="stat-value">{{ dashboard.active_task_count }}</div>
        <div class="stat-note">保持节奏，逐个完成</div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon orange"><el-icon><Clock /></el-icon></div>
        <div class="stat-label">7 天内到期</div>
        <div class="stat-value">{{ dashboard.due_soon_count }}</div>
        <div class="stat-note">优先查看临近 DDL</div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon red"><el-icon><WarningFilled /></el-icon></div>
        <div class="stat-label">已逾期任务</div>
        <div class="stat-value">{{ dashboard.overdue_count }}</div>
        <div class="stat-note">及时调整你的安排</div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon green"><el-icon><Collection /></el-icon></div>
        <div class="stat-label">资料总数</div>
        <div class="stat-value">{{ dashboard.materials_count }}</div>
        <div class="stat-note">来自 {{ dashboard.courses_count }} 门课程</div>
      </el-card>
    </div>

    <div class="content-grid">
      <el-card class="content-card" shadow="never">
        <div class="card-heading">
          <h2>近期任务</h2>
          <router-link to="/tasks">查看全部</router-link>
        </div>
        <div v-if="upcomingTasks.length">
          <div v-for="task in upcomingTasks" :key="task.id" class="task-row clickable-row" role="link" tabindex="0" @click="goToTasks" @keydown.enter="goToTasks" @keydown.space.prevent="goToTasks">
            <div class="row-main">
              <div class="row-title">{{ task.name }}</div>
              <div class="row-meta">{{ task.course_name || '未归类课程' }} · {{ dueLabel(task) }}</div>
            </div>
            <el-tag :type="statusType(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag>
          </div>
        </div>
        <div v-else class="empty-state">未来 7 天没有待处理任务。</div>
        <div v-if="overdueTasks.length" class="dashboard-subsection">
          <div class="subsection-title">逾期提醒</div>
          <div v-for="task in overdueTasks" :key="task.id" class="task-row clickable-row" role="link" tabindex="0" @click="goToTasks" @keydown.enter="goToTasks" @keydown.space.prevent="goToTasks">
            <div class="row-main">
              <div class="row-title">{{ task.name }}</div>
              <div class="row-meta">{{ task.course_name || '未归类课程' }} · 已逾期 {{ formatDateTime(task.due_at) }}</div>
            </div>
            <el-tag type="danger" size="small">优先处理</el-tag>
          </div>
        </div>
      </el-card>

      <el-card class="content-card" shadow="never">
        <div class="card-heading">
          <h2>最近资料</h2>
          <router-link to="/materials">进入资料库</router-link>
        </div>
        <div v-if="recentMaterials.length">
          <div v-for="material in recentMaterials" :key="material.id" class="material-row clickable-row" role="link" tabindex="0" @click="goToMaterial(material)" @keydown.enter="goToMaterial(material)" @keydown.space.prevent="goToMaterial(material)">
            <div class="row-main">
              <div class="row-title">{{ material.original_filename }}</div>
              <div class="row-meta">{{ material.course_name || '未归类课程' }} · {{ materialType(material) }}</div>
            </div>
            <el-tag size="small" effect="plain">{{ material.processing_status }}</el-tag>
          </div>
        </div>
        <div v-else class="empty-state">还没有资料记录。</div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElAlert, ElCard, ElMessage } from 'element-plus'
import { Clock, Collection, List, WarningFilled } from '@element-plus/icons-vue'

import { dashboardApi } from '../api'
import { formatDateTime, isOverdue, statusLabel, statusType } from '../utils/format'

const loading = ref(true)
const router = useRouter()
const error = ref('')
const dashboard = ref({
  active_task_count: 0,
  due_soon_count: 0,
  overdue_count: 0,
  materials_count: 0,
  courses_count: 0,
  next_action: '',
  upcoming_tasks: [],
  overdue_tasks: [],
  recent_materials: [],
})
const upcomingTasks = ref([])
const overdueTasks = ref([])
const recentMaterials = ref([])

function goToTasks() {
  router.push('/tasks')
}

function goToMaterial(material) {
  router.push({ path: '/materials', query: { q: material.original_filename } })
}

function dueLabel(task) {
  if (isOverdue(task)) return '已逾期 · ' + formatDateTime(task.due_at)
  return task.due_at ? '截止 ' + formatDateTime(task.due_at) : '未设置截止时间'
}

function materialType(material) {
  return material.material_type || material.file_type || '未分类'
}

async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    dashboard.value = await dashboardApi.get()
    upcomingTasks.value = dashboard.value.upcoming_tasks
    overdueTasks.value = dashboard.value.overdue_tasks
    recentMaterials.value = dashboard.value.recent_materials
  } catch (err) {
    error.value = err.message
    ElMessage.error(err.message)
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard-action { margin: 0 0 22px; }
.dashboard-subsection { margin-top: 18px; padding-top: 18px; border-top: 1px solid #f0f2f6; }
.subsection-title { margin-bottom: 4px; color: #e45656; font-size: 12px; font-weight: 700; }
.clickable-row { cursor: pointer; }
.clickable-row:hover .row-title { color: #5964ed; }
.clickable-row:focus-visible { border-radius: 8px; }
</style>
