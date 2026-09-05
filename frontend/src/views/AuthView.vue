<template>
  <div class="auth-page">
    <router-link class="auth-brand" to="/" aria-label="返回学伴管家首页">
      <span class="auth-brand-mark">学</span>
      <span><strong>学伴管家</strong><small>课程资料与学习任务助手</small></span>
    </router-link>

    <section class="auth-story" aria-label="产品能力介绍">
      <div class="story-copy">
        <p>STUDY SPACE / 学习空间</p>
        <h1>{{ isRegister ? '把新学期，整理成能完成的每一天。' : '欢迎回来，今天先处理最重要的一件。' }}</h1>
      </div>
      <div class="story-board" aria-hidden="true">
        <div class="board-header"><span>本周课表</span><small>资料已整理成行动</small></div>
        <div class="board-row"><span>MON</span><div class="course course-blue"><strong>数据结构</strong><small>实验报告 · 23:59</small></div></div>
        <div class="board-row"><span>TUE</span><div class="course course-yellow"><strong>线性代数</strong><small>错题回看 · 35 min</small></div></div>
        <div class="board-row"><span>WED</span><div class="course course-mint"><strong>大学英语</strong><small>展示资料待确认</small></div></div>
        <div class="board-note">先核对，再创建正式任务 ✓</div>
      </div>
      <ul>
        <li><span>01</span>找出课程资料里的截止时间</li>
        <li><span>02</span>保留字段依据与建议来源</li>
        <li><span>03</span>根据完成反馈调整计划</li>
      </ul>
    </section>

    <main class="auth-panel">
      <div class="auth-form-wrap">
        <router-link class="mobile-auth-brand" to="/"><span class="auth-brand-mark">学</span><strong>学伴管家</strong></router-link>
        <p class="auth-kicker">{{ isRegister ? '建立你的学习空间' : '继续你的学习记录' }}</p>
        <h2>{{ isRegister ? '用邮箱注册' : '登录' }}</h2>
        <p class="auth-intro">
          {{ isRegister ? '一个账号对应一个独立学习空间。注册后即可添加第一门课程。' : '输入邮箱和密码，继续处理今天的任务与资料。' }}
        </p>

        <div v-if="errorMessage" class="form-alert" role="alert">{{ errorMessage }}</div>

        <form @submit.prevent="submitForm">
          <label v-if="isRegister" class="form-field">
            <span>怎么称呼你</span>
            <input
              v-model.trim="form.display_name"
              name="display_name"
              type="text"
              autocomplete="name"
              maxlength="40"
              placeholder="例如：小林"
              :disabled="submitting"
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
              :disabled="submitting"
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
                :disabled="submitting"
                required
              />
              <button type="button" :aria-pressed="showPassword" @click="showPassword = !showPassword">
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
              :disabled="submitting"
              required
            />
          </label>

          <p v-if="isRegister" class="password-tip">密码仅用于登录，系统不会保存明文密码。请勿与教务系统使用相同密码。</p>

          <button class="submit-button" type="submit" :disabled="submitting || demoLoading">
            <span v-if="submitting" class="submit-spinner" aria-hidden="true"></span>
            {{ submitting ? (isRegister ? '正在建立学习空间' : '正在登录') : (isRegister ? '注册并开始使用' : '登录并继续学习') }}
          </button>
        </form>

        <div class="demo-entry">
          <button class="demo-button" type="button" :disabled="submitting || demoLoading" @click="startDemo">
            <span v-if="demoLoading" class="submit-spinner" aria-hidden="true"></span>
            {{ demoLoading ? '正在准备演示空间' : '一键体验演示模式' }}
          </button>
          <small>无需注册，进入带示例数据的学习空间；演示账号与真实账号相互隔离，仅本地开发环境提供。</small>
        </div>

        <p class="auth-switch">
          {{ isRegister ? '已经有账号？' : '还没有账号？' }}
          <router-link :to="isRegister ? '/login' : '/register'">{{ isRegister ? '直接登录' : '用邮箱注册' }}</router-link>
        </p>
        <p class="auth-boundary">学伴管家不会替你登录学校系统、提交作业或在未确认时创建正式任务。</p>
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
  form.password = ''
  form.confirmPassword = ''
})
</script>

<style scoped>
.auth-page { --auth-ink: #16213d; --auth-blue: #3157e6; --auth-mint: #78e5cc; --auth-yellow: #ffc857; min-height: 100vh; display: grid; grid-template-columns: minmax(420px, .88fr) minmax(500px, 1.12fr); color: var(--auth-ink); background: #f8f9fc; }
.auth-brand { position: absolute; z-index: 2; top: 29px; left: 38px; display: flex; align-items: center; gap: 11px; color: #fff; }
.auth-brand-mark { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 11px; color: #fff; background: var(--auth-blue); box-shadow: 4px 4px 0 var(--auth-yellow); font-weight: 850; }
.auth-brand > span:last-child { display: grid; }
.auth-brand strong { font-size: 17px; }
.auth-brand small { margin-top: 3px; color: #b9c3da; font-size: 10px; }
.auth-story { position: relative; display: flex; flex-direction: column; justify-content: center; min-height: 100vh; padding: 118px 9% 62px; overflow: hidden; color: #fff; background: var(--auth-ink); }
.auth-story::after { position: absolute; right: -100px; bottom: -150px; width: 330px; height: 330px; content: ""; border: 42px solid rgba(120, 229, 204, .09); border-radius: 50%; }
.story-copy, .story-board, .auth-story ul { position: relative; z-index: 1; }
.story-copy p { margin: 0 0 14px; color: var(--auth-mint); font: 750 10px/1.3 Bahnschrift, sans-serif; letter-spacing: .12em; }
.story-copy h1 { max-width: 520px; margin: 0; font-family: "Aptos Display", "Microsoft YaHei", sans-serif; font-size: clamp(32px, 3vw, 47px); line-height: 1.22; letter-spacing: -.04em; }
.story-board { max-width: 500px; margin-top: 42px; padding: 20px; border: 1px solid rgba(255,255,255,.22); border-radius: 19px; background: #fff; box-shadow: 10px 11px 0 rgba(120, 229, 204, .82); transform: rotate(-1deg); }
.board-header { display: flex; justify-content: space-between; padding-bottom: 15px; color: var(--auth-ink); border-bottom: 1px solid #e5e9f1; font-size: 12px; font-weight: 850; }
.board-header small { color: #778298; font-size: 9px; font-weight: 600; }
.board-row { display: grid; grid-template-columns: 44px 1fr; align-items: center; gap: 10px; margin-top: 9px; color: #8390a7; font: 700 9px/1 Bahnschrift, sans-serif; }
.course { min-width: 0; display: flex; justify-content: space-between; gap: 12px; padding: 12px 13px; border-radius: 10px; color: var(--auth-ink); }
.course-blue { background: #edf1ff; }
.course-yellow { width: 86%; background: #fff3d3; }
.course-mint { width: 94%; background: #e7faf5; }
.course strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.course small { color: #65718a; font-size: 9px; font-weight: 600; }
.board-note { width: fit-content; margin: 14px 0 -6px auto; padding: 7px 10px; color: #6c4c13; background: var(--auth-yellow); font-size: 9px; font-weight: 800; transform: rotate(1deg); }
.auth-story ul { display: flex; flex-wrap: wrap; gap: 10px 18px; margin: 42px 0 0; padding: 0; list-style: none; color: #c3cce0; font-size: 10px; }
.auth-story li { display: flex; align-items: center; gap: 6px; }
.auth-story li span { color: var(--auth-mint); font: 800 9px/1 Bahnschrift, sans-serif; }
.auth-panel { min-height: 100vh; display: grid; place-items: center; padding: 70px 28px; }
.auth-form-wrap { width: 100%; max-width: 430px; }
.mobile-auth-brand { display: none; }
.auth-kicker { margin: 0 0 12px; color: var(--auth-blue); font: 800 11px/1.3 Bahnschrift, "Microsoft YaHei", sans-serif; letter-spacing: .09em; }
.auth-form-wrap h2 { margin: 0; font-family: "Aptos Display", "Microsoft YaHei", sans-serif; font-size: 39px; letter-spacing: -.04em; }
.auth-intro { margin: 15px 0 29px; color: #68748b; font-size: 13px; line-height: 1.7; }
.form-alert { margin-bottom: 18px; padding: 12px 14px; color: #963e3e; border: 1px solid #efc5c5; border-radius: 10px; background: #fff2f2; font-size: 12px; line-height: 1.5; }
form { display: grid; gap: 17px; }
.form-field { display: grid; gap: 7px; color: #35425d; font-size: 12px; font-weight: 750; }
.form-field > input, .password-input { width: 100%; min-height: 50px; border: 1px solid #c8d1e0; border-radius: 11px; background: #fff; transition: border-color .16s, box-shadow .16s; }
.form-field > input { padding: 0 14px; color: var(--auth-ink); }
.form-field > input::placeholder, .password-input input::placeholder { color: #9aa4b6; }
.form-field > input:focus, .password-input:focus-within { outline: none; border-color: var(--auth-blue); box-shadow: 0 0 0 3px rgba(49, 87, 230, .13); }
.password-input { display: flex; align-items: center; overflow: hidden; }
.password-input input { min-width: 0; flex: 1; align-self: stretch; padding: 0 14px; border: 0; outline: none; background: transparent; }
.password-input button { min-width: 56px; min-height: 44px; margin-right: 3px; color: #66728a; border: 0; background: transparent; font-size: 11px; cursor: pointer; }
.password-input button:hover { color: var(--auth-blue); }
.form-field input:disabled, .password-input:has(input:disabled) { color: #818b9f; background: #f0f2f6; cursor: not-allowed; }
.password-tip { margin: -3px 0 0; color: #788399; font-size: 10px; line-height: 1.55; }
.submit-button { width: 100%; min-height: 52px; display: inline-flex; align-items: center; justify-content: center; gap: 9px; margin-top: 4px; color: #fff; border: 0; border-radius: 11px; background: var(--auth-blue); box-shadow: 0 9px 18px rgba(49, 87, 230, .2); font-weight: 800; cursor: pointer; }
.submit-button:hover { background: #2648c6; }
.submit-button:disabled { background: #8c9ddb; box-shadow: none; cursor: wait; }
.submit-spinner { width: 15px; height: 15px; border: 2px solid rgba(255,255,255,.45); border-top-color: #fff; border-radius: 50%; animation: spin .7s linear infinite; }
.auth-switch { margin: 25px 0 0; color: #6f7a90; font-size: 12px; text-align: center; }
.auth-switch a { margin-left: 5px; color: var(--auth-blue); font-weight: 800; }
.demo-entry { display: grid; justify-items: center; gap: 9px; margin-top: 23px; padding-top: 21px; border-top: 1px dashed #ccd4e4; }
.demo-button { min-height: 46px; display: inline-flex; align-items: center; justify-content: center; gap: 9px; width: 100%; padding: 0 18px; color: var(--auth-ink); border: 1px solid #b9c3d9; border-radius: 11px; background: #fff; font-size: 13px; font-weight: 750; cursor: pointer; transition: border-color .18s ease, color .18s ease, translate .18s ease; }
.demo-button:hover:not(:disabled) { color: var(--auth-blue); border-color: var(--auth-blue); translate: 0 -1px; }
.demo-button:disabled { opacity: .62; cursor: default; }
.demo-entry small { max-width: 360px; color: #8590a6; font-size: 11px; line-height: 1.6; text-align: center; }
.auth-boundary { margin: 28px 0 0; padding-top: 20px; color: #8992a4; border-top: 1px solid #dfe4ed; font-size: 10px; line-height: 1.65; text-align: center; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 900px) { .auth-page { grid-template-columns: 1fr; } .auth-story, .auth-brand { display: none; } .auth-panel { min-height: 100svh; padding: 45px 20px; } .mobile-auth-brand { display: inline-flex; align-items: center; gap: 10px; margin-bottom: 58px; color: var(--auth-ink); } .mobile-auth-brand .auth-brand-mark { width: 36px; height: 36px; } }
@media (max-width: 480px) { .auth-panel { align-items: start; padding: 25px 16px 40px; } .mobile-auth-brand { margin-bottom: 45px; } .auth-form-wrap h2 { font-size: 34px; } .form-field > input, .password-input { min-height: 52px; } .form-field input { font-size: 16px; } }
@media (prefers-reduced-motion: reduce) { .submit-spinner { animation-duration: 1.5s; } }
</style>
