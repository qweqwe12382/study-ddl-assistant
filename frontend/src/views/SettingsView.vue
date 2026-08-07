<template>
  <div>
    <div class="page-intro">
      <div>
        <h1>设置</h1>
        <p>管理课程基础信息，后续可在这里配置智能解析与演示模式。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增课程</el-button>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon closable class="mb-18" @close="error = ''" />

    <div class="settings-grid">
      <el-card class="table-card" shadow="never" v-loading="loading">
        <div class="table-toolbar">
          <h2>课程管理 <el-tag size="small" effect="plain">{{ courses.length }}</el-tag></h2>
        </div>
        <div class="table-wrap">
          <el-table :data="courses" empty-text="还没有课程，请先新增">
            <el-table-column prop="name" label="课程名称" min-width="220" />
            <el-table-column prop="teacher" label="教师" width="160">
              <template #default="{ row }">{{ row.teacher || '未填写' }}</template>
            </el-table-column>
            <el-table-column prop="semester" label="学期" width="140">
              <template #default="{ row }">{{ row.semester || '未填写' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="removeCourse(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <el-card class="content-card" shadow="never">
        <div class="card-heading"><h2>当前版本</h2><el-tag type="success">M7</el-tag></div>
        <div class="settings-note">
          <p><strong>已启用：</strong>课程、资料、DDL 任务和可编辑复习计划。</p>
          <p><strong>本地测试：</strong>可以使用下方按钮清空全部业务数据，从 0 开始测试。</p>
          <p><strong>数据位置：</strong><code>data/app.db</code> 和 <code>data/uploads/</code>。</p>
          <p><strong>提醒：</strong>复习计划来自本地规则生成，建议根据实际复习进度人工调整。</p>
        </div>
        <div class="reset-zone">
          <div>
            <h3>测试数据重置</h3>
            <p>清空课程、资料、DDL 任务、复习计划和上传文件，仅保留数据库结构。</p>
          </div>
          <el-button type="danger" plain :loading="resetting" @click="resetTestData">重置测试数据</el-button>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑课程' : '新增课程'" width="480px" destroy-on-close>
      <el-form :model="form" label-width="80px" class="dialog-form">
        <el-form-item label="课程名称" required><el-input v-model="form.name" placeholder="例如：数据结构" /></el-form-item>
        <el-form-item label="任课教师"><el-input v-model="form.teacher" placeholder="可选" /></el-form-item>
        <el-form-item label="学期"><el-input v-model="form.semester" placeholder="例如：2026 秋" /></el-form-item>
        <el-form-item label="主题色"><el-color-picker v-model="form.color" /></el-form-item>
      </el-form>
      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveCourse">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { coursesApi, resetApi } from '../api'

const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const error = ref('')
const dialogVisible = ref(false)
const editingId = ref(null)
const courses = ref([])
const form = reactive(emptyForm())

function emptyForm() {
  return { name: '', teacher: '', semester: '', color: '#5964ed' }
}

function resetForm() {
  Object.assign(form, emptyForm())
  editingId.value = null
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(course) {
  Object.assign(form, {
    name: course.name,
    teacher: course.teacher || '',
    semester: course.semester || '',
    color: course.color || '#5964ed',
  })
  editingId.value = course.id
  dialogVisible.value = true
}

async function loadCourses() {
  loading.value = true
  error.value = ''
  try {
    courses.value = await coursesApi.list()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function saveCourse() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写课程名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      teacher: form.teacher.trim() || null,
      semester: form.semester.trim() || null,
      color: form.color || null,
    }
    if (editingId.value) {
      await coursesApi.update(editingId.value, payload)
      ElMessage.success('课程已更新')
    } else {
      await coursesApi.create(payload)
      ElMessage.success('课程已添加')
    }
    dialogVisible.value = false
    await loadCourses()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function removeCourse(course) {
  try {
    await ElMessageBox.confirm(`删除课程可能同时删除关联资料和任务，确定删除“${course.name}”吗？`, '删除课程', { type: 'warning' })
    await coursesApi.remove(course.id)
    ElMessage.success('课程已删除')
    await loadCourses()
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

async function resetTestData() {
  try {
    await ElMessageBox.confirm(
      '这会删除全部课程、资料、DDL 任务、复习计划和上传文件，且不可恢复。确定继续吗？',
      '重置全部测试数据',
      {
        type: 'warning',
        confirmButtonText: '确认重置',
        cancelButtonText: '取消',
        distinguishCancelAndClose: true,
      },
    )
    resetting.value = true
    const result = await resetApi.all()
    await loadCourses()
    ElMessage.success(`已重置：${result.deleted_files} 个上传文件和全部业务数据`)
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  } finally {
    resetting.value = false
  }
}

onMounted(loadCourses)
</script>

<style scoped>
.mb-18 { margin-bottom: 18px; }
.reset-zone {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #f3c7c7;
  border-radius: 10px;
  background: #fff8f8;
}
.reset-zone h3 { margin: 0 0 6px; color: #b42318; font-size: 15px; }
.reset-zone p { margin: 0; color: #7a4b4b; font-size: 13px; line-height: 1.6; }
@media (max-width: 720px) {
  .reset-zone { align-items: flex-start; flex-direction: column; }
}
</style>
