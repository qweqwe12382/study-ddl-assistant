<template>
  <div>
    <div class="page-intro">
      <div>
        <h1>资料库</h1>
        <p>上传课程资料，系统会保存原文件并自动提取可检索文本。</p>
      </div>
      <div class="page-actions">
        <el-button @click="openCreate">手动新增</el-button>
        <el-button type="primary" @click="openUpload">上传文件</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon closable class="mb-18" @close="error = ''" />

    <el-card class="table-card" shadow="never" v-loading="loading">
      <div class="table-toolbar">
        <div>
          <h2>我的资料 <el-tag size="small" effect="plain">{{ materials.length }}</el-tag></h2>
        </div>
        <div class="toolbar-actions material-filters">
          <el-input v-model="keyword" placeholder="搜索文件名、摘要或正文" clearable style="width: 230px" />
          <el-select v-model="courseFilter" clearable placeholder="全部课程" style="width: 150px">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
          <el-select v-model="materialTypeFilter" clearable placeholder="资料类型" style="width: 145px">
            <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
          </el-select>
          <el-select v-model="processingStatusFilter" clearable placeholder="处理状态" style="width: 125px">
            <el-option label="已处理" value="processed" />
            <el-option label="处理失败" value="failed" />
            <el-option label="待处理" value="pending" />
          </el-select>
          <el-input v-model="tagFilter" placeholder="标签" clearable style="width: 110px" />
        </div>
      </div>
      <div class="table-wrap">
        <el-table :data="filteredMaterials" empty-text="还没有资料记录">
          <el-table-column label="文件名称" min-width="220">
            <template #default="{ row }">
              <div class="row-title">{{ row.original_filename }}</div>
              <div class="row-meta">{{ row.file_type || '未知格式' }}</div>
              <div v-for="snippet in row.match_snippets || []" :key="snippet" class="match-snippet">{{ snippet }}</div>
            </template>
          </el-table-column>
          <el-table-column label="所属课程" min-width="150">
            <template #default="{ row }">{{ courseName(row.course_id) }}</template>
          </el-table-column>
          <el-table-column label="资料类型" width="140">
            <template #default="{ row }">{{ row.material_type || '未分类' }}</template>
          </el-table-column>
          <el-table-column label="标签" min-width="180">
            <template #default="{ row }">
              <el-tag v-for="tag in row.tags || []" :key="tag" size="small" effect="plain" class="tag-gap">{{ tag }}</el-tag>
              <span v-if="!row.tags?.length" class="muted">暂无</span>
            </template>
          </el-table-column>
          <el-table-column label="处理状态" width="120">
            <template #default="{ row }"><el-tag size="small" :type="statusType(row.processing_status)">{{ statusLabel(row.processing_status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              <el-button v-if="row.processing_status === 'processed'" link type="success" @click="openExtraction(row)">{{ row.extraction_status === 'confirmed' ? '查看抽取' : 'AI抽取' }}</el-button>
              <el-button v-if="row.processing_status === 'failed'" link type="warning" @click="retryMaterial(row)">重试</el-button>
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="removeMaterial(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑资料' : '新增资料'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="92px" class="dialog-form">
        <el-form-item label="文件名称" required>
          <el-input v-model="form.original_filename" placeholder="例如：数据结构实验一.pdf" />
        </el-form-item>
        <el-form-item label="所属课程">
          <el-select v-model="form.course_id" clearable placeholder="选择课程" style="width: 100%">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件格式">
          <el-input v-model="form.file_type" placeholder="pdf / docx / txt / png" />
        </el-form-item>
        <el-form-item label="资料类型">
          <el-select v-model="form.material_type" clearable placeholder="选择资料类型" style="width: 100%">
            <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tagsText" placeholder="多个标签用逗号分隔" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="填写资料摘要或备注" />
        </el-form-item>
        <el-form-item label="提取文本">
          <el-input v-model="form.extracted_text" type="textarea" :rows="5" placeholder="解析失败时可在这里手动补充正文" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveMaterial">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传课程资料" width="620px" destroy-on-close>
      <el-form label-width="92px" class="dialog-form">
        <el-form-item label="所属课程">
          <el-select v-model="uploadCourseId" clearable placeholder="可选，稍后也可以编辑" style="width: 100%">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="资料类型">
          <el-select v-model="uploadMaterialType" clearable placeholder="可选" style="width: 100%">
            <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件" required>
          <el-upload
            v-model:file-list="uploadFileList"
            drag
            multiple
            :auto-upload="false"
            :limit="uploadPolicy.max_upload_files"
            :before-upload="validateUploadFile"
            :on-exceed="handleUploadExceed"
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.gif,.bmp,.webp"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到这里，或 <em>点击选择</em></div>
            <template #tip><div class="el-upload__tip">支持 PDF、DOCX、TXT、MD 和常见图片，单个文件不超过 {{ uploadPolicy.max_upload_size_mb }} MB。</div></template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="form-actions">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="uploading" @click="submitUpload">开始上传并解析</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="资料详情" width="680px" destroy-on-close>
      <template v-if="detailMaterial">
        <div class="detail-grid">
          <div><span>文件名</span><strong>{{ detailMaterial.original_filename }}</strong></div>
          <div><span>格式</span><strong>{{ (detailMaterial.file_type || '未知').toUpperCase() }}</strong></div>
          <div><span>大小</span><strong>{{ formatFileSize(detailMaterial.file_size) }}</strong></div>
          <div><span>状态</span><el-tag size="small" :type="statusType(detailMaterial.processing_status)">{{ statusLabel(detailMaterial.processing_status) }}</el-tag></div>
          <div><span>AI抽取</span><el-tag size="small" :type="extractionStatusType(detailMaterial.extraction_status)">{{ extractionStatusLabel(detailMaterial.extraction_status) }}</el-tag></div>
        </div>
        <el-alert v-if="detailMaterial.processing_error" :title="detailMaterial.processing_error" type="warning" show-icon class="detail-alert" />
        <div class="detail-section">
          <div class="detail-label">提取文本</div>
          <pre v-if="detailMaterial.extracted_text" class="text-preview">{{ detailMaterial.extracted_text }}</pre>
          <div v-else class="empty-state">暂无提取文本，可以编辑资料后手动补充。</div>
        </div>
        <div class="detail-actions">
          <el-button v-if="detailMaterial.stored_path" @click="downloadMaterial(detailMaterial)">下载原文件</el-button>
          <el-button v-if="detailMaterial.processing_status === 'processed'" type="success" @click="openExtraction(detailMaterial)">AI抽取并确认</el-button>
          <el-button v-if="detailMaterial.processing_status === 'failed'" type="warning" @click="retryMaterial(detailMaterial)">重新解析</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="extractionDialogVisible" title="AI 抽取结果确认" width="900px" destroy-on-close>
      <template v-if="extractionResult">
        <el-alert
          :title="extractionResult.needs_review ? '结果包含待确认信息，请核对日期、任务名称和来源原文。' : '结果已通过基础校验，确认后才会创建正式任务。'"
          :type="extractionResult.needs_review ? 'warning' : 'success'"
          show-icon
          class="detail-alert"
        />
        <div class="extraction-meta">
          <span>课程识别：<strong>{{ extractionResult.course_name || '未识别' }}</strong></span>
          <span>Provider：<strong>{{ extractionResult.provider || '本地规则' }}</strong></span>
        </div>
        <div class="extraction-editors">
          <el-select v-model="extractionCourseId" clearable placeholder="确认所属课程" style="width: 220px">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
          <el-select v-model="extractionMaterialType" clearable placeholder="资料类型" style="width: 180px">
            <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
          </el-select>
          <el-input v-model="extractionTagsText" placeholder="标签，用逗号分隔" style="width: 260px" />
        </div>
        <el-table :data="extractionTasks" empty-text="没有抽取到任务">
          <el-table-column label="确认" width="70">
            <template #default="{ row }"><el-checkbox v-model="row.selected" /></template>
          </el-table-column>
          <el-table-column label="任务名称" min-width="210">
            <template #default="{ row }"><el-input v-model="row.name" size="small" /></template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }"><el-input v-model="row.task_type" size="small" /></template>
          </el-table-column>
          <el-table-column label="截止时间" width="205">
            <template #default="{ row }">
              <el-date-picker v-model="row.due_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" size="small" placeholder="待补充" />
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="100">
            <template #default="{ row }">{{ `${Math.round((row.confidence || 0) * 100)}%` }}</template>
          </el-table-column>
          <el-table-column label="来源 / 提示" min-width="230">
            <template #default="{ row }">
              <div class="row-meta">{{ row.source_quote || '无来源原文' }}</div>
              <el-tag v-for="warning in row.warnings || []" :key="warning" size="small" type="warning" class="tag-gap">{{ warning }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <div class="form-actions">
          <el-button @click="extractionDialogVisible = false">取消</el-button>
          <el-button v-if="extractionResult && extractionResult.status !== 'confirmed'" type="primary" :loading="extractionSaving" @click="confirmExtraction">确认并创建任务</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import {
  ElAlert,
  ElCard,
  ElCheckbox,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElUpload,
} from 'element-plus'
import { useRoute } from 'vue-router'

import { coursesApi, materialsApi } from '../api'

const materialTypes = ['课程大纲', '课堂讲义', '教材或阅读材料', '作业要求', '实验资料', '复习资料', '其他']
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const keyword = ref('')
const courseFilter = ref(null)
const materialTypeFilter = ref('')
const processingStatusFilter = ref('')
const tagFilter = ref('')
const dialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const extractionDialogVisible = ref(false)
const editingId = ref(null)
const courses = ref([])
const materials = ref([])
const uploadFileList = ref([])
const uploadCourseId = ref(null)
const uploadMaterialType = ref('')
const uploading = ref(false)
const detailMaterial = ref(null)
const extractionMaterial = ref(null)
const extractionResult = ref(null)
const extractionTasks = ref([])
const extractionSaving = ref(false)
const extractionCourseId = ref(null)
const extractionMaterialType = ref('')
const extractionTagsText = ref('')
const uploadPolicy = ref({ max_upload_size_mb: 20, max_upload_files: 10, extensions: [] })
const form = reactive(emptyForm())
const route = useRoute()
let materialRequestId = 0
let initialized = false

const filteredMaterials = computed(() => {
  return materials.value
})

function emptyForm() {
  return {
    original_filename: '',
    course_id: null,
    file_type: '',
    material_type: '',
    tagsText: '',
    summary: '',
    extracted_text: '',
    originalExtractedText: '',
  }
}

function resetForm() {
  Object.assign(form, emptyForm())
  editingId.value = null
}

function courseName(courseId) {
  return courses.value.find((course) => course.id === courseId)?.name || '未归类课程'
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openUpload() {
  uploadFileList.value = []
  uploadCourseId.value = null
  uploadMaterialType.value = ''
  uploadDialogVisible.value = true
}

function openDetail(material) {
  detailMaterial.value = material
  detailDialogVisible.value = true
}

const statusLabels = { pending: '待处理', processing: '处理中', processed: '已处理', failed: '处理失败' }
function statusLabel(status) { return statusLabels[status] || status || '未知' }
function statusType(status) { return { processed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }[status] || 'info' }
const extractionStatusLabels = { not_started: '未抽取', ready: '待确认', needs_review: '需复核', confirmed: '已确认', failed: '抽取失败' }
function extractionStatusLabel(status) { return extractionStatusLabels[status] || status || '未抽取' }
function extractionStatusType(status) { return { confirmed: 'success', ready: 'info', needs_review: 'warning', failed: 'danger' }[status] || 'info' }
function formatFileSize(size) {
  if (!size) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function validateUploadFile(file) {
  const maxBytes = uploadPolicy.value.max_upload_size_mb * 1024 * 1024
  if (file.size > maxBytes) {
    ElMessage.warning(`“${file.name}”超过 ${uploadPolicy.value.max_upload_size_mb} MB 限制`)
    return false
  }
  return true
}

function handleUploadExceed() {
  ElMessage.warning(`一次最多选择 ${uploadPolicy.value.max_upload_files} 个文件`)
}

function openEdit(material) {
  Object.assign(form, {
    original_filename: material.original_filename,
    course_id: material.course_id,
    file_type: material.file_type || '',
    material_type: material.material_type || '',
    tagsText: (material.tags || []).join(', '),
    summary: material.summary || '',
    extracted_text: material.extracted_text || '',
    originalExtractedText: material.extracted_text || '',
  })
  editingId.value = material.id
  dialogVisible.value = true
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [courseData, policy] = await Promise.all([
      coursesApi.list(),
      materialsApi.uploadPolicy(),
    ])
    courses.value = courseData
    uploadPolicy.value = policy
    await loadMaterials()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function loadMaterials() {
  const requestId = ++materialRequestId
  try {
    const result = await materialsApi.list({
      q: keyword.value,
      course_id: courseFilter.value,
      material_type: materialTypeFilter.value,
      processing_status: processingStatusFilter.value,
      tag: tagFilter.value,
    })
    if (requestId === materialRequestId) materials.value = result
  } catch (err) {
    if (requestId === materialRequestId) error.value = err.message
  }
}

async function saveMaterial() {
  if (!form.original_filename.trim()) {
    ElMessage.warning('请填写文件名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      original_filename: form.original_filename.trim(),
      course_id: form.course_id,
      file_type: form.file_type.trim() || null,
      material_type: form.material_type || null,
      tags: form.tagsText.split(',').map((tag) => tag.trim()).filter(Boolean),
      summary: form.summary.trim() || null,
    }
    if (!editingId.value || form.extracted_text.trim() !== form.originalExtractedText.trim()) {
      payload.extracted_text = form.extracted_text.trim() || null
    }
    if (editingId.value) {
      await materialsApi.update(editingId.value, payload)
      ElMessage.success('资料已更新')
    } else {
      await materialsApi.create(payload)
      ElMessage.success('资料已添加')
    }
    dialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function submitUpload() {
  const files = uploadFileList.value.map((item) => item.raw).filter(Boolean)
  if (!files.length) {
    ElMessage.warning('请先选择文件')
    return
  }
  uploading.value = true
  try {
    const uploaded = await materialsApi.upload(files, uploadCourseId.value, uploadMaterialType.value)
    const failed = uploaded.filter((material) => material.processing_status === 'failed').length
    ElMessage[failed ? 'warning' : 'success'](failed ? `${uploaded.length} 个文件已入库，其中 ${failed} 个解析失败，可重试` : `已上传并处理 ${uploaded.length} 个文件`)
    uploadDialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    uploading.value = false
  }
}

async function retryMaterial(material) {
  try {
    const updated = await materialsApi.retry(material.id)
    Object.assign(material, updated)
    ElMessage[updated.processing_status === 'processed' ? 'success' : 'warning'](updated.processing_status === 'processed' ? '资料已重新解析' : updated.processing_error || '重新解析失败')
  } catch (err) {
    ElMessage.error(err.message)
  }
}

async function openExtraction(material) {
  if (!material.extracted_text) {
    ElMessage.warning('资料没有可用正文，请先补充或重新解析')
    return
  }
  extractionMaterial.value = material
  extractionDialogVisible.value = true
  extractionResult.value = null
  extractionTasks.value = []
  try {
    const result = material.extraction_result && material.extraction_status !== 'not_started'
      ? await materialsApi.extraction(material.id)
      : await materialsApi.extract(material.id)
    extractionResult.value = result
    extractionTasks.value = result.tasks.map((task) => ({ ...task }))
    extractionCourseId.value = material.course_id || null
    extractionMaterialType.value = result.material_type || material.material_type || ''
    extractionTagsText.value = (result.tags || material.tags || []).join(', ')
    Object.assign(material, {
      extraction_status: result.status,
      extraction_result: result,
      material_type: result.material_type || material.material_type,
      tags: result.tags || material.tags,
    })
  } catch (err) {
    extractionDialogVisible.value = false
    ElMessage.error(err.message)
  }
}

async function confirmExtraction() {
  if (!extractionMaterial.value || !extractionTasks.value.some((task) => task.selected)) {
    ElMessage.warning('请至少勾选一条任务')
    return
  }
  extractionSaving.value = true
  try {
    const result = await materialsApi.confirmExtraction(extractionMaterial.value.id, {
      tasks: extractionTasks.value,
      course_id: extractionCourseId.value,
      material_type: extractionMaterialType.value || null,
      tags: extractionTagsText.value.split(',').map((tag) => tag.trim()).filter(Boolean),
    })
    Object.assign(extractionMaterial.value, {
      extraction_status: result.status,
      extraction_result: result,
      material_type: result.material_type || extractionMaterialType.value || extractionMaterial.value.material_type,
      tags: result.tags || extractionMaterial.value.tags,
    })
    extractionDialogVisible.value = false
    ElMessage.success(`已确认并创建 ${result.confirmed_task_ids.length} 条任务`)
    await loadData()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    extractionSaving.value = false
  }
}

function downloadMaterial(material) {
  window.open(materialsApi.fileUrl(material.id), '_blank', 'noopener,noreferrer')
}

async function removeMaterial(material) {
  try {
    await ElMessageBox.confirm(`确定删除“${material.original_filename}”吗？`, '删除资料', { type: 'warning' })
    await materialsApi.remove(material.id)
    ElMessage.success('资料已删除')
    await loadData()
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

let searchTimer
watch([keyword, courseFilter, materialTypeFilter, processingStatusFilter, tagFilter], () => {
  if (!initialized) return
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadMaterials, 250)
})

onMounted(() => {
  keyword.value = typeof route.query.q === 'string' ? route.query.q : ''
  loadData().finally(() => { initialized = true })
})
</script>

<style scoped>
.mb-18 { margin-bottom: 18px; }
.tag-gap { margin: 2px 4px 2px 0; }
.muted { color: #a0a8b6; font-size: 12px; }
.detail-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px 22px; padding: 4px 0 18px; }
.detail-grid > div { display: flex; align-items: center; gap: 10px; color: #7f8a9c; font-size: 13px; }
.detail-grid strong { color: #344054; font-weight: 600; }
.detail-alert { margin-bottom: 18px; }
.detail-label { margin-bottom: 8px; color: #667085; font-size: 13px; font-weight: 600; }
.detail-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.text-preview { max-height: 280px; overflow: auto; margin: 0; padding: 14px; color: #475467; background: #f8fafc; border: 1px solid #edf0f5; border-radius: 8px; font: 12px/1.7 "SFMono-Regular", Consolas, monospace; white-space: pre-wrap; }
.extraction-meta { display: flex; gap: 28px; margin-bottom: 16px; color: #667085; font-size: 13px; }
.extraction-meta strong { color: #344054; }
.extraction-editors { display: flex; gap: 10px; margin-bottom: 16px; }
.material-filters { flex-wrap: wrap; justify-content: flex-end; }
.match-snippet { max-width: 360px; margin-top: 5px; overflow: hidden; color: #7b65e8; font-size: 11px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
</style>
