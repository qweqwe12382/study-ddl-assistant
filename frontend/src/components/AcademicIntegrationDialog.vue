<template>
  <el-dialog v-model="visible" title="导入课表与考试" width="760px" top="4vh" destroy-on-close class="academic-integration-dialog">
    <div class="integration-contract" :class="{ 'is-njust': sourceMode === 'njust' }">
      <span class="contract-mark" aria-hidden="true">{{ sourceMode === 'njust' ? '本机' : '只读' }}</span>
      <div>
        <strong>{{ sourceMode === 'njust' ? '本机直连南理工，确认后才保存课表' : '读取教务日历，确认后才写入' }}</strong>
        <p v-if="sourceMode === 'njust'">账号、密码和教务会话只在本次请求中临时使用；不会写入数据库、浏览器存储，也不会经过第三方解析服务。</p>
        <p v-else>只接收教务系统导出的 iCalendar（.ics）文件，不收集账号或密码，也不会自动删除本地日程。</p>
      </div>
    </div>

    <div v-if="stage === 'configure'" class="integration-stage">
      <ol class="sync-steps" aria-label="接入步骤">
        <li class="is-active"><span>1</span>{{ sourceMode === 'njust' ? '登录并读取' : '选择日历' }}</li>
        <li><span>2</span>核对内容</li>
        <li><span>3</span>确认导入</li>
      </ol>

      <div class="source-switch" aria-label="选择接入方式">
        <button type="button" :class="{ 'is-active': sourceMode === 'njust' }" :aria-pressed="sourceMode === 'njust'" @click="setSourceMode('njust')">
          <span class="source-badge">NJUST</span>
          <span><strong>南京理工大学</strong><small>使用教务账号读取课表与考试</small></span>
        </button>
        <button type="button" :class="{ 'is-active': sourceMode === 'ical' }" :aria-pressed="sourceMode === 'ical'" @click="setSourceMode('ical')">
          <span class="source-badge is-file">ICS</span>
          <span><strong>日历文件</strong><small>适用于支持 iCalendar 的教务系统</small></span>
        </button>
      </div>

      <NjustAcademicConnectForm
        v-if="sourceMode === 'njust'"
        :semester-start="semesterStart"
        @cancel="visible = false"
        @previewed="handleNjustPreview"
      />

      <el-form v-else label-position="top" @submit.prevent="previewCalendar">
        <div class="integration-form-grid">
          <el-form-item label="学期第一周开始日期" required>
            <el-date-picker v-model="form.semester_start" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </div>
        <details class="import-options">
          <summary>导入选项 <span>{{ form.source_name }} · {{ form.semester_weeks }} 周</span></summary>
          <div class="integration-form-grid">
          <el-form-item label="来源名称（重复导入时保持一致）" required>
            <el-input v-model="form.source_name" maxlength="120" placeholder="例如：学校教务系统" />
          </el-form-item>
          <el-form-item label="学期周数" required>
            <el-input-number v-model="form.semester_weeks" :min="1" :max="30" style="width: 100%" />
          </el-form-item>
        </div>
        </details>
        <label class="calendar-file-field" :class="{ 'has-file': fileName }">
          <input ref="fileInput" type="file" accept=".ics,text/calendar" @change="readCalendarFile">
          <span class="file-mark" aria-hidden="true">ICS</span>
          <span class="file-copy">
            <strong>{{ fileName || '选择教务系统导出的 .ics 文件' }}</strong>
            <small>{{ fileName ? '文件只用于本次预览，不保存原文' : '最大 1 MB；课程重复规则会换算为学期周次' }}</small>
          </span>
          <span class="file-action">{{ fileName ? '重新选择' : '选择文件' }}</span>
        </label>
        <p v-if="formError" class="field-error" role="alert">{{ formError }}</p>
        <div class="integration-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="loading" :disabled="!calendarText || !form.semester_start">预览课表与考试</el-button>
        </div>
      </el-form>
    </div>

    <div v-else-if="stage === 'preview'" class="integration-stage">
      <ol class="sync-steps" aria-label="接入步骤">
        <li><span>1</span>{{ sourceMode === 'njust' ? '登录并读取' : '选择日历' }}</li>
        <li class="is-active"><span>2</span>核对内容</li>
        <li><span>3</span>确认导入</li>
      </ol>
      <div v-if="preview.credential_policy === 'ephemeral_memory'" class="credential-cleared" role="status">
        <span aria-hidden="true">✓</span>教务账号、密码和会话已清除
      </div>
      <div class="preview-toolbar">
        <div>
          <strong>找到 {{ preview.items.length }} 项日程</strong>
          <span>{{ preview.class_count }} 节课程 · {{ preview.exam_count }} 场考试</span>
        </div>
        <div class="preview-selection-actions">
          <button type="button" @click="selectAll">全选</button>
          <button type="button" @click="selectedKeys = []">清空</button>
        </div>
      </div>
      <p class="semester-preview">学期开始于 {{ sourceMode === 'njust' ? njustSemesterStart : form.semester_start }}，确认导入后用于自动定位本周。</p>
      <div class="preview-list" aria-label="待同步日程">
        <label v-for="item in preview.items" :key="item.item_key" class="preview-item">
          <el-checkbox :model-value="selectedKeys.includes(item.item_key)" :aria-label="`选择 ${item.course_name}`" @change="toggleItem(item.item_key, $event)" />
          <span class="preview-kind">{{ item.kind === 'exam' ? '考' : '课' }}</span>
          <span class="preview-main">
            <strong>{{ item.course_name }}</strong>
            <small>{{ itemSummary(item) }}</small>
          </span>
        </label>
      </div>
      <div v-if="preview.warnings.length" class="preview-warnings" role="status">
        <strong>{{ preview.warnings.length }} 条未导入说明</strong>
        <ul><li v-for="warning in preview.warnings" :key="warning">{{ warning }}</li></ul>
      </div>
      <div class="integration-actions">
        <el-button @click="stage = 'configure'">返回修改</el-button>
        <span class="action-spacer"></span>
        <span class="selection-count">已选 {{ selectedItems.length }} 项</span>
        <el-button type="primary" :disabled="!selectedItems.length" :loading="loading" @click="syncCalendar">确认导入到本地</el-button>
      </div>
    </div>

    <div v-else class="integration-stage sync-result" role="status">
      <ol class="sync-steps" aria-label="接入步骤">
        <li><span>1</span>{{ sourceMode === 'njust' ? '登录并读取' : '选择日历' }}</li>
        <li><span>2</span>核对内容</li>
        <li class="is-active"><span>3</span>确认导入</li>
      </ol>
      <div class="result-mark" aria-hidden="true">✓</div>
       <strong>课表与考试已导入本地</strong>
      <p>新增 {{ result.created }} 项，更新 {{ result.updated }} 项，无变化 {{ result.unchanged }} 项。</p>
      <div v-if="result.skipped" class="result-conflicts">
        <strong>{{ result.skipped }} 项需要人工处理</strong>
        <ul><li v-for="conflict in result.conflicts" :key="`${conflict.item_key}-${conflict.reason}`">{{ conflict.course_name }}：{{ conflict.message }}</li></ul>
      </div>
      <div class="integration-actions result-actions">
        <el-button @click="resetDialog">继续导入</el-button>
        <el-button type="primary" @click="visible = false">回到课表</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, defineAsyncComponent, reactive, ref, watch } from 'vue'
import { ElButton, ElCheckbox, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage } from 'element-plus'

import { academicCalendarApi } from '../api'

const NjustAcademicConnectForm = defineAsyncComponent(() => import('./NjustAcademicConnectForm.vue'))

const props = defineProps({ modelValue: { type: Boolean, default: false }, semesterStart: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue', 'synced'])
const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })
const sourceMode = ref('njust')
const form = reactive(defaultForm())
const njustSemesterStart = ref('')
const stage = ref('configure')
const loading = ref(false)
const fileName = ref('')
const calendarText = ref('')
const formError = ref('')
const fileInput = ref(null)
const preview = ref({ items: [], class_count: 0, exam_count: 0, warnings: [] })
const selectedKeys = ref([])
const result = ref({ created: 0, updated: 0, unchanged: 0, skipped: 0, conflicts: [] })
const selectedItems = computed(() => preview.value.items.filter((item) => selectedKeys.value.includes(item.item_key)))

function defaultForm() { return { source_name: '学校教务处', semester_start: props.semesterStart || '', semester_weeks: 18 } }
function setSourceMode(mode) {
  if (sourceMode.value === mode) return
  sourceMode.value = mode
  formError.value = ''
}
function resetDialog() {
  Object.assign(form, defaultForm())
  njustSemesterStart.value = ''
  stage.value = 'configure'
  fileName.value = ''
  calendarText.value = ''
  formError.value = ''
  preview.value = { items: [], class_count: 0, exam_count: 0, warnings: [] }
  selectedKeys.value = []
  result.value = { created: 0, updated: 0, unchanged: 0, skipped: 0, conflicts: [] }
  if (fileInput.value) fileInput.value.value = ''
}
function handleNjustPreview(payload) {
  preview.value = payload.preview
  njustSemesterStart.value = payload.semester_start
  selectedKeys.value = preview.value.items.map((item) => item.item_key)
  stage.value = 'preview'
}
async function readCalendarFile(event) {
  const file = event.target.files?.[0]
  formError.value = ''
  fileName.value = ''
  calendarText.value = ''
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.ics')) {
    formError.value = '请选择 .ics 格式的教务日历文件'
    event.target.value = ''
    return
  }
  if (file.size > 1_000_000) {
    formError.value = '日历文件不能超过 1 MB'
    event.target.value = ''
    return
  }
  try {
    calendarText.value = await file.text()
    fileName.value = file.name
  } catch {
    formError.value = '无法读取该文件，请重新导出后再试'
  }
}
async function previewCalendar() {
  if (loading.value) return
  if (!form.source_name.trim() || !form.semester_start || !calendarText.value) {
    formError.value = '请填写来源、学期开始日期并选择 .ics 文件'
    return
  }
  loading.value = true
  try {
    preview.value = await academicCalendarApi.previewIntegration({
      source_type: 'ical', source_name: form.source_name.trim(), semester_start: form.semester_start,
      semester_weeks: form.semester_weeks, calendar_text: calendarText.value,
    })
    selectedKeys.value = preview.value.items.map((item) => item.item_key)
    stage.value = 'preview'
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}
function selectAll() { selectedKeys.value = preview.value.items.map((item) => item.item_key) }
function toggleItem(key, checked) {
  if (checked && !selectedKeys.value.includes(key)) selectedKeys.value = [...selectedKeys.value, key]
  if (!checked) selectedKeys.value = selectedKeys.value.filter((value) => value !== key)
}
function itemSummary(item) {
  if (item.kind === 'exam') {
    const value = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(item.starts_at))
    return `${value} · ${item.location || '地点待补充'}${item.seat_number ? ` · 座位 ${item.seat_number}` : ''}`
  }
  const weekday = ['一', '二', '三', '四', '五', '六', '日'][item.weekday - 1]
  const pattern = { all: '每周', odd: '单周', even: '双周' }[item.week_pattern]
  const teacher = item.teacher ? ` · ${item.teacher}` : ''
  return `周${weekday} ${item.start_time.slice(0, 5)}–${item.end_time.slice(0, 5)} · ${pattern} ${item.start_week}–${item.end_week} 周 · ${item.location || '地点待补充'}${teacher}`
}
async function syncCalendar() {
  if (loading.value || !selectedItems.value.length) return
  loading.value = true
  try {
    result.value = await academicCalendarApi.syncIntegration({
      source_key: preview.value.source_key, source_type: preview.value.source_type, source_name: preview.value.source_name, items: selectedItems.value,
    })
    stage.value = 'result'
    emit('synced', {
      ...result.value,
      semester_start: sourceMode.value === 'njust' ? njustSemesterStart.value : form.semester_start,
    })
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}
watch(() => props.modelValue, (value) => {
  if (value && stage.value === 'result') resetDialog()
})
watch(() => props.semesterStart, value => {
  if (value && !form.semester_start && stage.value === 'configure') form.semester_start = value
})
</script>

<style scoped>
.import-options { margin: 0 0 14px; }
.import-options summary { padding: 10px 0; cursor: pointer; font-size: 13px; }
.import-options summary span { color: var(--ledger-muted); margin-left: 8px; }
.semester-preview { font-size: 13px; color: var(--ledger-muted); line-height: 1.6; }
.integration-contract { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; padding: 11px 13px; color: #334158; background: #f1f5f4; border: 1px solid #cadbd6; border-radius: 5px; }
.integration-contract.is-njust { background: #f2f6ff; border-color: #cdd8ef; }
.contract-mark { flex: 0 0 auto; padding: 5px 7px; color: #136d62; background: #d8f3ec; border-radius: 3px; font: 700 10px Bahnschrift, "Microsoft YaHei", sans-serif; letter-spacing: .06em; }
.is-njust .contract-mark { color: #284e9a; background: #dfe8ff; }
.integration-contract strong { font-size: 14px; }
.integration-contract p { margin: 5px 0 0; color: #5f6d79; font-size: 12px; line-height: 1.55; }
.integration-stage { min-width: 0; }
.sync-steps { display: grid; grid-template-columns: repeat(3, 1fr); margin: 0 0 12px; padding: 0; list-style: none; border-bottom: 1px solid #dce2eb; }
.sync-steps li { display: flex; align-items: center; gap: 7px; padding: 0 0 10px; color: #7a8495; font-size: 11px; }
.sync-steps li span { display: grid; place-items: center; width: 20px; height: 20px; border: 1px solid #cbd3df; border-radius: 50%; font: 700 10px Bahnschrift, sans-serif; }
.sync-steps li.is-active { color: #25354e; border-bottom: 2px solid #3157e6; }
.sync-steps li.is-active span { color: #fff; background: #3157e6; border-color: #3157e6; }
.source-switch { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
.source-switch button { display: flex; align-items: center; gap: 11px; min-height: 58px; padding: 9px 12px; color: #46556c; text-align: left; background: #fff; border: 1px solid #d8dee8; border-radius: 5px; cursor: pointer; }
.source-switch button:hover { border-color: #99a9cf; }
.source-switch button.is-active { color: #203b73; background: #f4f7ff; border-color: #6782c7; box-shadow: inset 3px 0 #3157e6; }
.source-switch button > span:last-child { display: grid; gap: 4px; }
.source-switch strong { font-size: 13px; }
.source-switch small { color: #718096; font-size: 11px; line-height: 1.35; }
.source-badge { display: grid; place-items: center; width: 42px; height: 32px; flex: 0 0 auto; color: #fff; background: #3157e6; border-radius: 3px; font: 700 9px Bahnschrift, sans-serif; letter-spacing: .04em; }
.source-badge.is-file { color: #3157e6; background: #e8edff; }
.integration-form-grid { display: grid; grid-template-columns: 1.35fr 1fr .65fr; gap: 14px; }
.calendar-file-field { display: flex; align-items: center; gap: 14px; min-height: 86px; padding: 14px 16px; color: #46556e; background: #fafbfc; border: 1px dashed #b9c4d4; border-radius: 5px; cursor: pointer; }
.calendar-file-field:hover, .calendar-file-field.has-file { border-color: #879bdc; background: #f6f7ff; }
.calendar-file-field input { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
.file-mark { display: grid; place-items: center; width: 44px; height: 44px; flex: 0 0 auto; color: #3157e6; background: #e9edff; border-radius: 4px; font: 700 11px Bahnschrift, sans-serif; }
.file-copy { min-width: 0; display: grid; gap: 5px; flex: 1; }
.file-copy strong { font-size: 13px; overflow-wrap: anywhere; }
.file-copy small { color: #718096; font-size: 11px; line-height: 1.45; }
.file-action { flex: 0 0 auto; font-size: 12px; font-weight: 700; }
.field-error { margin: 8px 0 0; color: #a53e3e; font-size: 12px; }
.integration-actions { display: flex; align-items: center; justify-content: flex-end; gap: 9px; margin-top: 18px; }
.action-spacer { flex: 1; }
.selection-count { color: #69768a; font-size: 12px; }
.credential-cleared { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding: 8px 10px; color: #176e60; background: #eef8f5; border: 1px solid #cce6df; border-radius: 4px; font-size: 11px; }
.credential-cleared span { font-weight: 800; }
.preview-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 10px; }
.preview-toolbar > div:first-child { display: grid; gap: 4px; }
.preview-toolbar strong { font-size: 14px; }
.preview-toolbar span { color: #68758a; font-size: 11px; }
.preview-selection-actions { display: flex; gap: 7px; }
.preview-selection-actions button { min-height: 36px; padding: 0 10px; color: #42516a; background: #fff; border: 1px solid #d1d8e2; border-radius: 4px; cursor: pointer; }
.preview-list { max-height: 310px; overflow-y: auto; border: 1px solid #dce2eb; border-radius: 5px; }
.preview-item { display: grid; grid-template-columns: auto 30px minmax(0, 1fr); gap: 10px; align-items: center; min-height: 64px; padding: 10px 13px; border-bottom: 1px solid #e4e8ee; cursor: pointer; }
.preview-item:last-child { border-bottom: 0; }
.preview-item:hover { background: #f8f9fc; }
.preview-kind { display: grid; place-items: center; width: 30px; height: 30px; color: #3157e6; background: #edf0ff; border-radius: 4px; font-size: 12px; font-weight: 700; }
.preview-main { min-width: 0; display: grid; gap: 5px; }
.preview-main strong { font-size: 13px; overflow-wrap: anywhere; }
.preview-main small { color: #66748a; font-size: 11px; line-height: 1.45; overflow-wrap: anywhere; }
.preview-warnings, .result-conflicts { margin-top: 12px; padding: 12px 14px; color: #765625; background: #fff9eb; border: 1px solid #ead8a8; border-radius: 4px; }
.preview-warnings strong, .result-conflicts strong { font-size: 12px; }
.preview-warnings ul, .result-conflicts ul { margin: 7px 0 0; padding-left: 18px; font-size: 11px; line-height: 1.6; }
.sync-result { display: grid; justify-items: center; text-align: center; }
.sync-result .sync-steps { width: 100%; text-align: left; }
.result-mark { display: grid; place-items: center; width: 46px; height: 46px; margin-top: 4px; color: #fff; background: #168b7a; border-radius: 50%; font-size: 20px; }
.sync-result > strong { margin-top: 12px; font-size: 15px; }
.sync-result > p { margin: 7px 0 0; color: #657287; font-size: 12px; }
.result-conflicts { width: 100%; box-sizing: border-box; text-align: left; }
.result-actions { width: 100%; }
@media (max-width: 760px) {
  .source-switch, .integration-form-grid { grid-template-columns: minmax(0, 1fr); }
  .integration-form-grid { gap: 0; }
  .sync-steps li { align-items: flex-start; flex-direction: column; gap: 4px; }
  .calendar-file-field { align-items: flex-start; flex-wrap: wrap; }
  .file-copy { min-width: calc(100% - 60px); }
  .file-action { margin-left: 58px; }
  .preview-toolbar { align-items: flex-start; }
  .preview-list { max-height: 330px; }
  .integration-actions { align-items: stretch; flex-wrap: wrap; }
  .integration-actions .el-button { flex: 1 1 auto; margin-left: 0; }
  .action-spacer { display: none; }
  .selection-count { width: 100%; }
}
</style>
