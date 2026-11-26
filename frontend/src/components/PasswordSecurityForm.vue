<template>
  <p v-if="done" role="status">密码已重置。请使用新密码登录。</p>
  <form v-else class="security-form" :aria-busy="busy" @submit.prevent="save">
    <p v-if="mode === 'reset'">使用已验证的注册邮箱接收找回验证码。</p>
    <p v-if="mode === 'verify'">验证 {{ authSession.user?.email }} 后，就可以通过此邮箱找回密码。</p>
    <label v-if="mode === 'reset'">注册邮箱
      <input ref="emailField" v-model.trim="email" type="email" autocomplete="email" maxlength="254" required :disabled="busy" />
    </label>
    <label v-else>当前密码
      <input ref="currentField" v-model="current" type="password" autocomplete="current-password" maxlength="128" required :disabled="busy" />
    </label>
    <template v-if="usesCode">
      <p v-if="configError" role="alert">{{ configError }} <button type="button" @click="loadConfig">重试</button></p>
      <p v-else-if="config && !config.password_recovery_available" role="status">本站暂未开通邮箱找回服务。</p>
      <TurnstileChallenge v-if="mode === 'reset' && config?.password_recovery_available && config.turnstile_site_key && !sent"
        ref="challenge" v-model:token="token" :site-key="config.turnstile_site_key" action="password_reset" />
      <div>
        <label for="security-email-code">邮箱验证码</label>
        <div class="security-code">
          <input id="security-email-code" v-model.trim="code" inputmode="numeric" autocomplete="one-time-code"
            maxlength="6" pattern="[0-9]{6}" required :disabled="busy" placeholder="6 位数字" />
          <button type="button" :disabled="busy || remaining > 0 || !mailReady || !canRequest" @click="sendCode">
            {{ sending ? '正在申请…' : remaining ? remaining + ' 秒后重发' : '发送验证码' }}
          </button>
        </div>
        <p v-if="sent" role="status">{{ mode === 'reset' ? '如果该邮箱可用于找回，你将收到验证码。' : '验证码已发送至你的注册邮箱。' }}验证码 10 分钟内有效。</p>
        <p v-else>每 60 秒可申请一次，每小时最多 5 封。</p>
      </div>
    </template>
    <template v-if="mode !== 'verify'">
      <label>新密码
        <input v-model="password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required :disabled="busy" aria-describedby="security-password-help" />
      </label>
      <p id="security-password-help">使用 8 至 128 位字符，包含字母和数字。保存后，所有设备都需要重新登录。</p>
      <label>确认新密码
        <input v-model="confirm" type="password" autocomplete="new-password" maxlength="128" required :disabled="busy" />
      </label>
    </template>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <button class="save" type="submit" :disabled="busy || (usesCode && !mailReady)">
      {{ saving ? '正在保存…' : mode === 'verify' ? '验证找回邮箱' : mode === 'reset' ? '重置密码' : '保存并重新登录' }}
    </button>
  </form>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { authApi } from '../api'
import { authSession } from '../auth/session'
import TurnstileChallenge from './TurnstileChallenge.vue'

const props = defineProps({ mode: { type: String, required: true } })
const emit = defineEmits(['changed', 'verified'])
const usesCode = computed(() => props.mode !== 'change')
const current = ref('')
const password = ref('')
const confirm = ref('')
const code = ref('')
const email = ref('')
const token = ref('')
const config = ref(null)
const configError = ref('')
const error = ref('')
const done = ref(false)
const sent = ref(false)
const sending = ref(false)
const saving = ref(false)
const remaining = ref(0)
const challenge = ref(null)
const currentField = ref(null)
const emailField = ref(null)
const busy = computed(() => sending.value || saving.value)
const mailReady = computed(() => config.value?.password_recovery_available)
const canRequest = computed(() => props.mode === 'verify' ? Boolean(current.value)
  : Boolean(email.value && (!config.value?.turnstile_site_key || token.value)))
let timer
let mounted = true

async function loadConfig() {
  configError.value = ''
  try { config.value = await authApi.config() }
  catch { configError.value = '无法读取邮箱验证配置。' }
}

async function sendCode() {
  const field = props.mode === 'reset' ? emailField.value : currentField.value
  if (busy.value || remaining.value || !canRequest.value || !mailReady.value || !field?.reportValidity()) return
  sending.value = true
  error.value = ''
  try {
    const result = props.mode === 'reset'
      ? await authApi.requestResetCode({ email: email.value, turnstile_token: token.value || undefined })
      : await authApi.requestRecoveryEmailCode({ current_password: current.value })
    if (!mounted) return
    code.value = ''
    sent.value = true
    remaining.value = result.retry_after_seconds
    const until = Date.now() + remaining.value * 1000
    timer = setInterval(() => {
      remaining.value = Math.max(0, Math.ceil((until - Date.now()) / 1000))
      if (!remaining.value) {
        clearInterval(timer)
        sent.value = false
      }
    }, 1000)
  } catch (err) { error.value = err.message }
  finally {
    sending.value = false
    challenge.value?.reset()
    token.value = ''
  }
}

async function save() {
  if (busy.value || (usesCode.value && !mailReady.value)) return
  error.value = ''
  if (props.mode !== 'verify' && password.value !== confirm.value) {
    error.value = '两次输入的新密码不一致。'
    return
  }
  saving.value = true
  const accountId = authSession.user?.id
  try {
    if (props.mode === 'change') {
      await authApi.changePassword({ current_password: current.value, new_password: password.value })
      if (authSession.user?.id === accountId) {
        authSession.user = null
        emit('changed')
      }
    } else if (props.mode === 'verify') {
      const verifiedUser = await authApi.verifyRecoveryEmail({ current_password: current.value, email_code: code.value })
      if (authSession.user?.id === verifiedUser.id) {
        authSession.user = verifiedUser
        emit('verified')
      }
    } else {
      await authApi.resetPassword({ email: email.value, email_code: code.value, new_password: password.value })
      done.value = true
    }
    current.value = password.value = confirm.value = code.value = ''
    clearInterval(timer)
  } catch (err) { error.value = err.message }
  finally { saving.value = false }
}

watch(email, () => { sent.value = false; code.value = ''; error.value = '' })
onMounted(() => { if (usesCode.value) loadConfig() })
onUnmounted(() => { mounted = false; clearInterval(timer) })
</script>

<style scoped>
.security-form, label { display: grid; gap: 7px; }
.security-form { gap: 16px; }
label { color: var(--ledger-ink); font-weight: 600; font-size: 14px; }
p { margin: 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
input, button { min-height: 42px; padding: 8px 12px; border: 1px solid var(--ledger-line); border-radius: 8px; background: var(--ledger-paper); color: var(--ledger-ink); }
input { min-width: 0; width: 100%; }
button { cursor: pointer; }
button:disabled { opacity: .65; cursor: default; }
.security-code { margin: 7px 0; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
.save { background: var(--ledger-primary); color: white; font-weight: 600; }
.form-error { color: var(--ledger-coral-text); }
</style>
