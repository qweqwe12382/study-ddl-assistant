<template>
  <el-form label-position="top" @submit.prevent="previewCalendar">
    <div class="local-route" aria-label="数据流向">
      <span>本机</span><b aria-hidden="true">→</b><span>南理工教务</span>
      <strong>同步结果只保存在本机</strong>
    </div>
    <div class="njust-form-grid">
      <el-form-item label="学号" required>
        <el-input v-model="form.username" maxlength="64" autocomplete="username" placeholder="仅用于本次教务登录" />
      </el-form-item>
      <el-form-item label="教务密码" required>
        <el-input v-model="form.password" type="password" maxlength="128" autocomplete="current-password" show-password placeholder="用后立即清除" />
      </el-form-item>
      <el-form-item label="学期" required>
        <el-input v-model="form.term" maxlength="11" placeholder="2026-2027-1" />
      </el-form-item>
      <el-form-item label="第一周开始日期" required>
        <el-date-picker v-model="form.semester_start" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="学期周数" required>
        <el-input-number v-model="form.semester_weeks" :min="1" :max="30" style="width: 100%" />
      </el-form-item>
      <el-form-item label="验证码" required class="captcha-form-item">
        <div class="captcha-control">
          <el-input v-model="form.captcha" maxlength="12" autocomplete="off" placeholder="输入右侧验证码" />
          <button v-if="captchaImage" type="button" class="captcha-image" title="刷新验证码" @click="refreshCaptcha">
            <img :src="captchaImage" alt="南理工教务验证码">
          </button>
          <el-button v-else :loading="captchaLoading" @click="refreshCaptcha">获取验证码</el-button>
        </div>
      </el-form-item>
    </div>
    <div class="transport-warning">
      <strong>安全提示</strong>
      <p>{{ transportWarning }}</p>
      <el-checkbox v-model="form.acknowledge_insecure_transport">我已了解 HTTP 传输风险，并确认当前使用可信网络</el-checkbox>
    </div>
    <p v-if="formError" class="field-error" role="alert">{{ formError }}</p>
    <div class="integration-actions">
      <el-button @click="emit('cancel')">取消</el-button>
      <el-button type="primary" native-type="submit" :loading="loading">读取并查看课表</el-button>
    </div>
  </el-form>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElButton, ElCheckbox, ElDatePicker, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage } from 'element-plus'

import { academicCalendarApi } from '../api'

const emit = defineEmits(['cancel', 'previewed'])
const form = reactive(defaultForm())
const loading = ref(false)
const captchaLoading = ref(false)
const captchaImage = ref('')
const captchaSessionId = ref('')
const formError = ref('')
const transportWarning = ref('南理工旧教务接口使用 HTTP；账号密码在本机到学校服务器之间可能不是加密传输。仅建议在可信校园网或学校 VPN 中使用。')

function defaultForm() {
  const now = new Date()
  const year = now.getFullYear()
  const autumn = now.getMonth() + 1 >= 7
  return {
    username: '', password: '', captcha: '',
    term: autumn ? `${year}-${year + 1}-1` : `${year - 1}-${year}-2`,
    semester_start: autumn ? `${year}-09-01` : `${year}-02-20`,
    semester_weeks: 18, acknowledge_insecure_transport: false,
  }
}

function discardCaptchaSession(discard = false) {
  const sessionId = captchaSessionId.value
  captchaSessionId.value = ''
  captchaImage.value = ''
  form.captcha = ''
  if (discard && sessionId) void academicCalendarApi.discardNjustSession(sessionId).catch(() => {})
}

function clearSecrets(discard = false) {
  discardCaptchaSession(discard)
  form.username = ''
  form.password = ''
}

async function refreshCaptcha() {
  discardCaptchaSession(true)
  captchaLoading.value = true
  formError.value = ''
  try {
    const response = await academicCalendarApi.createNjustCaptcha()
    captchaSessionId.value = response.session_id
    captchaImage.value = response.image_data_uri
    transportWarning.value = response.transport_warning
  } catch (error) {
    formError.value = error.message
  } finally {
    captchaLoading.value = false
  }
}

async function previewCalendar() {
  formError.value = ''
  if (!form.username || !form.password || !form.captcha || !captchaSessionId.value) {
      formError.value = '请填写学号、密码，并获取和输入验证码'
    return
  }
  if (!/^\d{4}-\d{4}-[12]$/.test(form.term) || !form.semester_start) {
      formError.value = '请按 2026-2027-1 格式填写学期，并填写第一周开始日期'
    return
  }
  if (!form.acknowledge_insecure_transport) {
    formError.value = '请先阅读并确认南理工旧教务接口的 HTTP 传输风险'
    return
  }
  loading.value = true
  try {
    const preview = await academicCalendarApi.previewNjustIntegration({
      session_id: captchaSessionId.value, username: form.username, password: form.password,
      captcha: form.captcha, term: form.term, semester_start: form.semester_start,
      semester_weeks: form.semester_weeks, acknowledge_insecure_transport: true,
    })
    emit('previewed', { preview, semester_start: form.semester_start })
  } catch (error) {
    formError.value = error.message
    ElMessage.error(error.message)
  } finally {
    clearSecrets(false)
    loading.value = false
  }
}

onBeforeUnmount(() => clearSecrets(true))
</script>

<style scoped>
.local-route { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding: 8px 10px; color: #526278; background: #f8fafc; border: 1px solid #e0e5ec; border-radius: 4px; font-size: 11px; }
.local-route span { padding: 3px 6px; color: #284e9a; background: #e7edff; border-radius: 3px; font-weight: 700; }
.local-route b { color: #8190a6; }
.local-route strong { margin-left: auto; color: #167565; font-size: 11px; }
.njust-form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 12px; }
.njust-form-grid :deep(.el-form-item) { margin-bottom: 12px; }
.captcha-form-item { grid-column: span 2; }
.captcha-control { display: grid; grid-template-columns: minmax(0, 1fr) 126px; gap: 8px; width: 100%; }
.captcha-image { height: 32px; padding: 0; overflow: hidden; background: #fff; border: 1px solid #ccd5e2; border-radius: 4px; cursor: pointer; }
.captcha-image img { display: block; width: 100%; height: 100%; object-fit: contain; }
.transport-warning { padding: 9px 11px; color: #725223; background: #fff9eb; border: 1px solid #ead8a8; border-radius: 4px; }
.transport-warning strong { font-size: 12px; }
.transport-warning p { margin: 5px 0 7px; font-size: 11px; line-height: 1.55; }
.transport-warning :deep(.el-checkbox__label) { color: #60491f; font-size: 11px; white-space: normal; }
.field-error { margin: 8px 0 0; color: #a53e3e; font-size: 12px; }
.integration-actions { display: flex; align-items: center; justify-content: flex-end; gap: 9px; margin-top: 12px; }
@media (max-width: 760px) {
  .njust-form-grid { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .captcha-form-item { grid-column: auto; }
  .local-route { flex-wrap: wrap; }
  .local-route strong { width: 100%; margin-left: 0; }
  .integration-actions { align-items: stretch; flex-wrap: wrap; }
  .integration-actions .el-button { flex: 1 1 auto; margin-left: 0; }
}
</style>
