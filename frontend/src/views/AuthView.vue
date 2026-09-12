<template>
  <div class="auth-page">
    <a class="auth-skip" href="#auth-form">跳到登录或注册表单</a>
    <router-link class="auth-brand" to="/" aria-label="返回学伴管家首页">
      <span class="auth-brand-mark">学</span>
      <span><strong>学伴管家</strong><small>课程资料与学习安排</small></span>
    </router-link>

    <section class="auth-story" aria-label="学习空间介绍">
      <div class="story-copy">
        <h2>{{ isRegister ? '先记下一件事，\n再整理整个学期。' : '今天的学习，\n从这里继续。' }}</h2>
        <p>课程资料、截止任务和复习安排，放在同一个学习空间。</p>
      </div>
      <ol class="story-steps">
        <li><span aria-hidden="true">1</span><div><strong>收好资料</strong><p>课程通知、文档、图片，都有地方放。</p></div></li>
        <li><span aria-hidden="true">2</span><div><strong>确认截止</strong><p>对照通知原文，核对后再创建任务。</p></div></li>
        <li><span aria-hidden="true">3</span><div><strong>开始行动</strong><p>安排复习，记录专注，完成一件算一件。</p></div></li>
      </ol>
      <p class="story-note">临时改期？在 DDL 应变台先预演，再决定是否更新。</p>
    </section>

    <main id="auth-form" class="auth-panel" tabindex="-1">
      <div class="auth-form-wrap">
        <router-link class="mobile-auth-brand" to="/"><span class="auth-brand-mark">学</span><strong>学伴管家</strong></router-link>
        <h1>{{ isRegister ? '用邮箱注册' : '登录' }}</h1>
        <p class="auth-intro">
          {{ isRegister ? '建立学习空间，课程和资料可以稍后添加。' : '登录你的学习空间。' }}
        </p>

        <div v-if="errorMessage" class="form-alert" role="alert">{{ errorMessage }}</div>

        <form :aria-busy="submitting || demoLoading" @submit.prevent="submitForm">
          <label v-if="isRegister" class="form-field">
            <span>怎么称呼你</span>
            <input
              v-model.trim="form.display_name"
              name="display_name"
              type="text"
              autocomplete="name"
              maxlength="40"
              placeholder="例如：小林"
              :disabled="submitting || demoLoading"
              required
            />
          </label>
          <label class="form-field">
            <span>邮箱</span>
            <input
              v-model.trim="form.email"
              name="email"
              type="email"
              autocomplete="email"
              maxlength="254"
              placeholder="name@example.com"
              :disabled="submitting || demoLoading"
              required
            />
          </label>
          <label class="form-field">
            <span>密码</span>
            <span class="password-input">
              <input
                v-model="form.password"
                name="password"
                :type="showPassword ? 'text' : 'password'"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                minlength="8"
                maxlength="128"
                :placeholder="isRegister ? '至少 8 位，包含字母和数字' : '输入密码'"
                :disabled="submitting || demoLoading"
                required
              />
              <button type="button" :aria-pressed="showPassword" :disabled="submitting || demoLoading" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
                {{ showPassword ? '隐藏' : '显示' }}
              </button>
            </span>
          </label>
          <label v-if="isRegister" class="form-field">
            <span>再次输入密码</span>
            <input
              v-model="form.confirmPassword"
              name="confirm_password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="new-password"
              minlength="8"
              maxlength="128"
              placeholder="再次输入密码"
              :disabled="submitting || demoLoading"
              required
            />
          </label>

          <p v-if="isRegister" class="password-tip">请使用至少 8 位、包含字母和数字的密码。</p>

          <button class="submit-button" type="submit" :disabled="submitting || demoLoading">
            <span v-if="submitting" class="submit-spinner" aria-hidden="true"></span>
            {{ submitting ? (isRegister ? '正在建立学习空间' : '正在登录') : (isRegister ? '注册并开始使用' : '登录') }}
          </button>
        </form>

        <div class="demo-entry">
          <button class="demo-button" type="button" :disabled="submitting || demoLoading" @click="startDemo">
            <span v-if="demoLoading" class="submit-spinner" aria-hidden="true"></span>
            {{ demoLoading ? '正在准备演示空间' : '体验示例空间' }}
          </button>
          <small>无需注册，使用独立的示例空间。仅本地开发环境提供。</small>
        </div>

        <p class="auth-switch">
          {{ isRegister ? '已经有账号？' : '还没有账号？' }}
          <router-link :to="{ path: isRegister ? '/login' : '/register', query: route.query.redirect ? { redirect: route.query.redirect } : {} }">{{ isRegister ? '直接登录' : '用邮箱注册' }}</router-link>
        </p>
        <p class="auth-boundary">资料识别与计划调整由你确认。学习安排，自己做主。</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { demoLogin, login, register } from '../auth/session'

const props = defineProps({ mode: { type: String, required: true } })
const router = useRouter()
const route = useRoute()
const isRegister = computed(() => props.mode === 'register')
const submitting = ref(false)
const demoLoading = ref(false)
const errorMessage = ref('')
const showPassword = ref(false)
const form = reactive({ display_name: '', email: '', password: '', confirmPassword: '' })

function safeRedirect() {
  const value = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  if (!value.startsWith('/') || value.startsWith('//') || ['/login', '/register'].includes(value.split('?')[0])) return '/app'
  return value
}

async function startDemo() {
  if (submitting.value || demoLoading.value) return
  errorMessage.value = ''
  demoLoading.value = true
  try {
    await demoLogin()
    await router.replace('/app')
  } catch (error) {
    errorMessage.value = error?.message || '演示模式暂不可用，请稍后重试或直接注册'
  } finally {
    demoLoading.value = false
  }
}

async function submitForm() {
  if (submitting.value || demoLoading.value) return
  errorMessage.value = ''
  if (isRegister.value && form.password !== form.confirmPassword) {
    errorMessage.value = '两次输入的密码不一致'
    return
  }
  submitting.value = true
  try {
    if (isRegister.value) {
      await register({ display_name: form.display_name, email: form.email, password: form.password })
    } else {
      await login({ email: form.email, password: form.password })
    }
    await router.replace(safeRedirect())
  } catch (error) {
    errorMessage.value = error?.message || (isRegister.value ? '注册失败，请检查填写内容' : '登录失败，请检查邮箱和密码')
  } finally {
    submitting.value = false
  }
}

watch(() => props.mode, () => {
  errorMessage.value = ''
  showPassword.value = false
  form.password = ''
  form.confirmPassword = ''
})
</script>

<style scoped>
.auth-page { --auth-ink: #243d36; --auth-green: #327864; --auth-muted: #607268; --auth-line: #e0e8e3; min-height: 100vh; display: grid; grid-template-columns: minmax(360px, .9fr) minmax(440px, 1.1fr); color: var(--auth-ink); background: #fff; font-family: "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif; }
.auth-page * { box-sizing: border-box; }
.auth-page a { color: inherit; text-decoration: none; }
.auth-page :is(a, button):focus-visible { outline: 3px solid #79aa98; outline-offset: 4px; }
.auth-skip { position: fixed; z-index: 100; top: -70px; left: 16px; padding: 12px 16px; background: #fff; border-radius: 6px; }
.auth-skip:focus { top: 12px; }
.auth-brand { position: absolute; z-index: 2; top: 32px; left: 40px; display: flex; align-items: center; gap: 10px; color: var(--auth-ink); }
.auth-brand-mark { display: grid; place-items: center; width: 34px; height: 36px; border-radius: 9px 9px 3px 9px; color: #fff; background: var(--auth-green); font-size: 18px; font-weight: 650; }
.auth-brand > span:last-child { display: grid; gap: 3px; }
.auth-brand strong { font-size: 17px; font-weight: 650; }
.auth-brand small { color: var(--auth-muted); font-size: 10px; }
.auth-story { display: flex; flex-direction: column; justify-content: center; padding: 128px clamp(36px, 6vw, 90px) 72px; background: #f0f5f1; border-right: 1px solid var(--auth-line); }
.story-copy h2 { margin: 0; font-size: clamp(28px, 3vw, 38px); font-weight: 600; letter-spacing: -.035em; line-height: 1.6; white-space: pre-line; }
.story-copy > p { max-width: 320px; margin: 18px 0 0; color: var(--auth-muted); font-size: 14px; line-height: 1.85; }
.story-steps { display: grid; gap: 27px; margin: 42px 0 0; padding: 0; list-style: none; }
.story-steps li { display: flex; align-items: flex-start; gap: 15px; }
.story-steps li > span { display: grid; place-items: center; width: 27px; height: 27px; flex-shrink: 0; border: 1px solid #c6d9cb; border-radius: 50%; color: var(--auth-green); font-size: 12px; }
.story-steps strong { display: block; margin-top: 2px; color: #3c614b; font-size: 14px; font-weight: 600; }
.story-steps p { margin: 7px 0 0; color: var(--auth-muted); font-size: 12px; line-height: 1.75; }
.story-note { max-width: 340px; margin: 39px 0 0; padding-top: 22px; border-top: 1px solid #dce7de; color: #607268; font-size: 12px; line-height: 1.8; }
.auth-panel { min-height: 100vh; display: grid; place-items: center; padding: 46px 40px; }
.auth-form-wrap { width: 100%; max-width: 390px; }
.mobile-auth-brand { display: none; }
.auth-form-wrap h1 { margin: 0; font-size: 30px; font-weight: 600; letter-spacing: -.035em; line-height: 1.4; }
.auth-intro { margin: 12px 0 26px; color: var(--auth-muted); font-size: 13px; line-height: 1.85; }
.form-alert { margin-bottom: 18px; padding: 11px 13px; border: 1px solid #e7c8c0; border-radius: 7px; color: #a2463e; background: #fdf3ef; font-size: 12px; line-height: 1.65; overflow-wrap: anywhere; }
form { display: grid; gap: 15px; }
.form-field { display: grid; gap: 7px; color: #466151; font-size: 12px; font-weight: 600; }
.form-field > input, .password-input { min-height: 46px; width: 100%; border: 1px solid #cddbd1; border-radius: 7px; background: #fff; }
.form-field input { color: var(--auth-ink); font: inherit; font-size: 14px; font-weight: 400; }
.form-field > input { padding: 0 13px; }
.form-field input::placeholder { color: #607268; }
.form-field > input:focus, .password-input:focus-within { outline: none; border-color: var(--auth-green); box-shadow: 0 0 0 3px #eaf2ed; }
.password-input { display: flex; align-items: center; }
.password-input input { min-width: 0; flex: 1; align-self: stretch; padding: 0 13px; border: 0; border-radius: 7px; outline: none; background: transparent; }
.password-input button { min-width: 54px; min-height: 40px; margin-right: 3px; border: 0; border-radius: 4px; color: #617c6b; background: transparent; font: inherit; font-size: 11px; cursor: pointer; }
.password-input button:hover { color: var(--auth-green); }
.password-input button:disabled { cursor: wait; }
.form-field input:disabled, .password-input:has(input:disabled) { color: #82948a; background: #f4f7f5; cursor: wait; }
.password-tip { margin: -3px 0 0; color: var(--auth-muted); font-size: 11px; font-weight: 400; line-height: 1.65; }
.submit-button { min-height: 47px; width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 9px; margin-top: 4px; border: 0; border-radius: 7px; color: #fff; background: var(--auth-green); font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
.submit-button:hover { background: #296651; }
.submit-button:disabled { background: #80a891; cursor: wait; }
.submit-spinner { width: 15px; height: 15px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: spin .7s linear infinite; }
.demo-entry { display: grid; justify-items: center; gap: 9px; margin-top: 23px; padding-top: 20px; border-top: 1px solid var(--auth-line); }
.demo-button { min-height: 44px; width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 9px; padding: 8px 18px; border: 1px solid #cddbd1; border-radius: 7px; color: #496f57; background: #fff; font: inherit; font-size: 13px; cursor: pointer; }
.demo-button:hover:not(:disabled) { background: #f5f8f6; border-color: #a9c5b1; }
.demo-button:disabled { opacity: .6; cursor: wait; }
.demo-entry small { color: var(--auth-muted); font-size: 10px; line-height: 1.7; text-align: center; }
.auth-switch { margin: 22px 0 0; color: var(--auth-muted); font-size: 12px; text-align: center; }
.auth-switch a { display: inline-block; padding: 4px; color: var(--auth-green); font-weight: 600; text-decoration: underline; text-underline-offset: 4px; }
.auth-boundary { margin: 27px 0 0; color: var(--auth-muted); font-size: 10px; line-height: 1.75; text-align: center; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 960px) { .auth-page { grid-template-columns: minmax(300px, .85fr) minmax(380px, 1.15fr); } .auth-story { padding-right: 30px; padding-left: 30px; } .auth-panel { padding-right: 30px; padding-left: 30px; } .auth-brand { left: 30px; } }
@media (max-width: 760px) { .auth-page { grid-template-columns: 1fr; background: #f5f8f7; } .auth-story, .auth-brand { display: none; } .auth-panel { min-height: 100svh; padding: 30px 24px 40px; } .mobile-auth-brand { display: inline-flex; align-items: center; gap: 10px; margin-bottom: 39px; } .mobile-auth-brand strong { font-size: 16px; font-weight: 650; } .auth-form-wrap { max-width: 390px; } }
@media (max-width: 420px) { .auth-panel { align-items: start; padding: 25px 22px 32px; } .mobile-auth-brand { margin-bottom: 34px; } .auth-form-wrap h1 { font-size: 28px; } .auth-intro { margin-bottom: 23px; } .form-field input { font-size: 16px; } .form-field > input, .password-input { min-height: 48px; } .auth-boundary { margin-top: 23px; } }
@media (prefers-reduced-motion: reduce) { .submit-spinner { animation: none; } }
</style>
