<template>
  <div class="auth-page">
    <a class="auth-skip" href="#auth-form">跳到登录或注册表单</a>
    <router-link class="auth-brand" to="/" aria-label="返回学伴管家首页">
      <BrandMark />
      <span><strong>学伴管家</strong><small>课程资料与学习安排</small></span>
    </router-link>

    <main id="auth-form" class="auth-panel" tabindex="-1">
      <div class="auth-form-wrap">
        <router-link class="mobile-auth-brand" to="/"><BrandMark /><strong>学伴管家</strong></router-link>
        <h1>{{ isRegister ? '创建账号' : '欢迎回来' }}</h1>
        <p class="auth-intro">
          {{ isRegister ? '用邮箱注册，课程和资料可以稍后添加。' : '登录你的学习空间。' }}
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
          <small>无需注册，使用示例数据。仅本地开发环境提供。</small>
        </div>

        <p class="auth-switch">
          {{ isRegister ? '已经有账号？' : '还没有账号？' }}
          <router-link :to="{ path: isRegister ? '/login' : '/register', query: route.query.redirect ? { redirect: route.query.redirect } : {} }">{{ isRegister ? '直接登录' : '用邮箱注册' }}</router-link>
        </p>
      </div>
    </main>

    <section class="auth-story" aria-label="学习空间介绍">
      <div class="story-copy">
        <h2>{{ isRegister ? '先记下一件事，\n再整理整个学期。' : '今天的学习，\n从这里继续。' }}</h2>
      </div>

      <div class="study-desk">
        <div v-folio-enter class="study-notebook">
          <div class="notebook-tabs" aria-label="选择手账示例">
            <button v-for="tab in previewTabs" :key="tab.id" type="button" :class="{ active: previewScene === tab.id }" :aria-pressed="previewScene === tab.id" aria-controls="notebook-preview" @click="previewScene = tab.id">{{ tab.label }}</button>
          </div>

          <div id="notebook-preview" class="notebook-preview">
            <Transition name="notebook-page" mode="out-in">
              <div v-if="previewScene === 'prepare'" key="prepare" class="notebook-sheet">
                <div class="sheet-heading"><h3>今天的课程</h3><span class="day-badge" aria-hidden="true">周<span>三</span></span></div>
                <div class="course-ticket"><span class="course-time">09:00<small>10:35</small></span><div><strong>高等数学</strong><span>A2 - 302 <span class="ticket-separator">/</span> 第三章 微分</span></div><svg viewBox="0 0 28 28" fill="none" aria-hidden="true"><path d="M4 7c4-2 7-2 10 0 3-2 6-2 10 0v16c-4-2-7-2-10 0-3-2-6-2-10 0V7Z" /><path d="M14 7v16M7.5 11h3M7.5 15h3M17.5 11h3M17.5 15h3" /></svg></div>
                <div class="preview-checklist">
                  <div class="checklist-item completed"><span class="check-box" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none"><path d="m3 8 3 3 7-7" /></svg></span><span>收好老师发的课件</span><small>已准备</small></div>
                  <button class="checklist-item interactive-check" :class="{ completed: preparationDone }" type="button" :aria-pressed="preparationDone" @click="preparationDone = !preparationDone"><span class="check-box" aria-hidden="true"><svg v-if="preparationDone" viewBox="0 0 16 16" fill="none"><path d="m3 8 3 3 7-7" /></svg></span><span>回顾上节课的重点</span><small>{{ preparationDone ? '已完成' : '点一下完成' }}</small></button>
                </div>
              </div>

              <div v-else-if="previewScene === 'focus'" key="focus" class="notebook-sheet">
                <div class="sheet-heading"><h3>微分的基本公式</h3><svg class="focus-spark" viewBox="0 0 36 36" fill="none" aria-hidden="true"><path d="m18 3 3 11 12 4-12 3-3 12-4-12L3 18l11-4 4-11Z" /></svg></div>
                <div class="focus-example" :class="{ 'focus-complete': focusDone }"><div class="focus-dial"><svg viewBox="0 0 132 132" fill="none" aria-hidden="true"><circle class="dial-track" cx="66" cy="66" r="57" /><circle class="dial-progress" cx="66" cy="66" r="57" /></svg><div aria-live="polite"><strong>{{ focusDone ? '完成' : '25:00' }}</strong><span>{{ focusDone ? '专注已完成' : '专注示例' }}</span></div></div></div>
                <button class="notebook-action" type="button" :aria-pressed="focusDone" @click="focusDone = !focusDone">{{ focusDone ? '重置示例' : '完成专注示例' }}<svg viewBox="0 0 18 18" fill="none" aria-hidden="true"><path d="m4 9 3 3 7-7" /></svg></button>
              </div>

              <div v-else key="notice" class="notebook-sheet">
                <div class="sheet-heading"><h3>习题提交提醒</h3><span class="notice-clip" aria-hidden="true"></span></div>
                <blockquote class="notice-source"><span>课程群通知</span><p>第三章习题请在<strong>周五 18:00 前</strong>提交，文件名写上姓名与学号。</p></blockquote>
                <div class="deadline-example" :class="{ 'deadline-confirmed': noticeConfirmed }"><span class="deadline-date">周五<strong>18:00</strong></span><div><strong>提交第三章习题</strong><span aria-live="polite">{{ noticeConfirmed ? '已确认' : '待确认' }}</span></div><svg v-if="noticeConfirmed" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m4 10 4 4 8-8" /></svg></div>
                <button class="notebook-action" type="button" :aria-pressed="noticeConfirmed" @click="noticeConfirmed = !noticeConfirmed">{{ noticeConfirmed ? '重置示例' : '确认截止时间' }}<svg viewBox="0 0 18 18" fill="none" aria-hidden="true"><path d="m4 9 3 3 7-7" /></svg></button>
              </div>
            </Transition>
          </div>
          <p class="notebook-footer">交互示例，不计时、不创建任务或保存数据。</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { demoLogin, login, register } from '../auth/session'
import BrandMark from '../components/BrandMark.vue'
import { vFolioEnter } from '../directives/folioEnter'

const props = defineProps({ mode: { type: String, required: true } })
const router = useRouter()
const route = useRoute()
const isRegister = computed(() => props.mode === 'register')
const submitting = ref(false)
const demoLoading = ref(false)
const errorMessage = ref('')
const showPassword = ref(false)
const form = reactive({ display_name: '', email: '', password: '', confirmPassword: '' })
const previewTabs = [
  { id: 'prepare', label: '课前准备' },
  { id: 'focus', label: '专注时刻' },
  { id: 'notice', label: '通知整理' },
]
const previewScene = ref('prepare')
const preparationDone = ref(false)
const focusDone = ref(false)
const noticeConfirmed = ref(false)

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
.auth-page { --auth-ink: var(--ledger-ink); --auth-green: var(--ledger-primary); --auth-muted: var(--ledger-muted); --auth-line: var(--ledger-line); min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1.07fr) minmax(0, 1fr); color: var(--auth-ink); background: #fff; font-family: var(--font-ui); }
.auth-page * { box-sizing: border-box; }
.auth-page a { color: inherit; text-decoration: none; }
.auth-page :is(a, button):focus-visible { outline: 3px solid #287560; outline-offset: 4px; }
.auth-skip { position: fixed; z-index: 100; top: -70px; left: 16px; padding: 12px 16px; background: #fff; border-radius: 6px; }
.auth-skip:focus { top: 12px; }
.auth-brand { position: absolute; z-index: 2; top: 30px; left: clamp(30px, 4vw, 68px); display: flex; align-items: center; gap: 10px; color: var(--auth-ink); }
.auth-brand-mark { display: grid; place-items: center; width: 34px; height: 36px; border-radius: 9px 9px 3px 9px; color: #fff; background: var(--auth-green); font-size: 18px; font-weight: 650; }
.auth-brand > span:last-child { display: grid; gap: 3px; }
.auth-brand strong { font-size: 19px; font-weight: 750; }
.auth-brand small { color: var(--auth-muted); font-size: 10px; }
.auth-story { grid-column: 1; grid-row: 1; min-width: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 118px clamp(30px, 4vw, 68px) 40px; background: #f4f8f7; border-right: 1px solid var(--auth-line); }
.story-copy { width: 100%; max-width: 460px; }
.story-copy h2 { margin: 0; font-family: var(--font-display); font-size: clamp(32px, 3.1vw, 46px); font-weight: 750; letter-spacing: -.035em; line-height: 1.4; white-space: pre-line; }
.study-desk { position: relative; width: 100%; max-width: 460px; margin-top: 44px; padding: 0 12px 12px 0; isolation: isolate; }
.study-notebook { position: relative; padding: 25px 26px 0; border: 1px solid #cbdad1; border-top: 3px solid var(--auth-green); border-radius: 10px; background: #fff; box-shadow: 0 16px 45px -24px #244b3938; }
.notebook-binding { position: absolute; top: 30px; bottom: 45px; left: -8px; display: flex; flex-direction: column; justify-content: space-between; }
.notebook-binding i { width: 15px; height: 7px; border: 2px solid #97aa9c; border-right-color: transparent; border-radius: 5px; background: #f4f8f7; }
.notebook-tabs { display: flex; gap: 21px; margin-top: 0; border-bottom: 1px solid #e2e9e4; }
.notebook-tabs button { position: relative; min-height: 44px; padding: 5px 0 10px; border: 0; color: var(--auth-muted); background: none; font: inherit; font-size: 12px; cursor: pointer; transition: color .18s ease; }
.notebook-tabs button::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 3px; border-radius: 3px 3px 0 0; background: var(--auth-green); content: ''; transform: scaleX(0); transform-origin: center; transition: transform .2s ease; }
.notebook-tabs button.active { color: var(--auth-green); font-weight: 650; }
.notebook-tabs button.active::after { transform: scaleX(1); }
.notebook-tabs button:hover { color: var(--auth-green); }
.notebook-preview { min-height: 286px; }
.notebook-sheet { padding-top: 21px; }
.sheet-heading { min-height: 56px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.sheet-heading h3 { margin: 0; font-size: 20px; line-height: 1.45; font-weight: 650; letter-spacing: -.035em; }
.day-badge { width: 43px; flex-shrink: 0; padding-top: 4px; border: 1px solid #d9e3dc; border-radius: 5px; color: #5f7469; background: #f5f8f5; font-size: 9px; text-align: center; }
.day-badge > span { display: block; margin-top: 3px; padding: 3px 0 5px; border-top: 1px solid #d9e3dc; color: var(--auth-ink); background: #fff; font-size: 19px; font-weight: 650; }
.course-ticket { display: flex; align-items: center; gap: 14px; margin-top: 20px; padding: 14px 16px; border-radius: 4px 10px 10px 4px; border-left: 3px solid #6697b7; background: #e7f1f9; }
.course-time { padding-right: 14px; border-right: 1px solid #c7d9e6; color: #345e7b; font-size: 15px; font-weight: 650; font-variant-numeric: tabular-nums; }
.course-time small { display: block; margin-top: 4px; color: #5b788c; font-size: 10px; font-weight: 400; }
.course-ticket > div { min-width: 0; }
.course-ticket strong { display: block; font-size: 13px; font-weight: 650; }
.course-ticket > div > span { display: block; margin-top: 6px; color: #536d7e; font-size: 10px; }
.ticket-separator { padding: 0 6px; color: #98b0be; }
.course-ticket > svg { width: 27px; margin-left: auto; flex-shrink: 0; stroke: #537a93; stroke-width: 1.4; stroke-linecap: round; stroke-linejoin: round; }
.preview-checklist { display: grid; margin-top: 15px; }
.checklist-item { min-height: 41px; display: flex; align-items: center; gap: 9px; padding: 8px 0; border: 0; border-bottom: 1px solid #edf0eb; color: var(--auth-ink); background: none; font: inherit; font-size: 11px; text-align: left; }
.checklist-item > small { margin-left: auto; color: #63766a; font-size: 9px; white-space: nowrap; }
.check-box { width: 18px; height: 18px; display: grid; place-items: center; flex-shrink: 0; border: 1px solid #a7b9ad; border-radius: 5px; background: #fff; transition: background .2s ease, border-color .2s ease; }
.check-box svg { width: 14px; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.completed .check-box { border-color: var(--auth-green); color: #fff; background: var(--auth-green); }
.completed > span:nth-child(2) { color: var(--auth-muted); text-decoration: line-through; text-decoration-color: #8ea597; }
.interactive-check { width: 100%; cursor: pointer; }
.interactive-check:hover { background: #f4f8f4; }
.interactive-check.completed .check-box { animation: check-complete .35s ease both; }
.notebook-footer { margin: 10px 0 0; padding: 14px 0; border-top: 1px solid #e7ece6; color: #60796b; font-size: 9px; }
.desk-pencil { position: absolute; z-index: -1; right: -11px; bottom: 39px; width: 10px; height: 164px; border-left: 2px solid #78958b; border-right: 3px solid #416a5b; border-radius: 3px 3px 0 0; background: #5c8875; transform: rotate(10deg); }
.desk-pencil::after { position: absolute; top: 100%; left: -2px; width: 10px; height: 19px; background: #d1b989; clip-path: polygon(0 0, 100% 0, 50% 100%); content: ''; }
.focus-spark { width: 34px; flex-shrink: 0; stroke: #9b8bc0; stroke-width: 1.5; }
.focus-example { display: flex; align-items: center; justify-content: center; gap: 23px; margin: 18px 0 15px; }
.focus-dial { position: relative; width: 132px; height: 132px; flex-shrink: 0; }
.focus-dial > svg { position: absolute; inset: 0; width: 100%; transform: rotate(-90deg); }
.dial-track { stroke: #ebe8fa; stroke-width: 7; }
.dial-progress { stroke: #8973af; stroke-width: 7; stroke-linecap: round; stroke-dasharray: 358.2; stroke-dashoffset: 90; transition: stroke-dashoffset .65s cubic-bezier(.2,.75,.2,1), stroke .3s ease; }
.focus-dial > div { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.focus-dial strong { color: #61517d; font-size: 27px; font-weight: 600; font-variant-numeric: tabular-nums; letter-spacing: -.04em; }
.focus-dial span { margin-top: 7px; color: #776d85; font-size: 9px; }
.focus-complete .dial-progress { stroke: var(--auth-green); stroke-dashoffset: 0; }
.focus-complete .focus-dial strong { color: var(--auth-green); font-size: 24px; }
.notebook-action { width: 100%; min-height: 39px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 11px; border: 1px solid #d7e3da; border-radius: 5px; color: var(--auth-green); background: #f4f8f4; font: inherit; font-size: 11px; cursor: pointer; transition: background .18s ease; }
.notebook-action:hover { background: #e7f0e8; }
.notebook-action svg { width: 18px; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.notice-clip { width: 17px; height: 34px; margin-right: 10px; flex-shrink: 0; border: 2px solid #91a79a; border-radius: 9px; transform: rotate(25deg); }
.notice-clip::after { display: block; width: 6px; height: 21px; margin: 3px; border: 1.5px solid #91a79a; border-top: 0; border-radius: 0 0 5px 5px; content: ''; }
.notice-source { margin: 17px 0 13px; padding: 11px 13px; border-left: 2px solid #d0bd7a; border-radius: 0 6px 6px 0; background: #fbf5e4; }
.notice-source > span { color: #7c7357; font-size: 9px; }
.notice-source p { margin: 6px 0 0; color: #605b48; font-size: 11px; line-height: 1.8; }
.notice-source strong { padding: 1px 2px; background: #f0dfa5; font-weight: 600; }
.deadline-example { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.deadline-date { padding-right: 11px; border-right: 1px solid #d9e3dc; color: var(--auth-muted); font-size: 9px; }
.deadline-date > strong { display: block; margin-top: 4px; color: var(--auth-ink); font-size: 16px; font-weight: 650; font-variant-numeric: tabular-nums; }
.deadline-example > div > strong { font-size: 13px; font-weight: 600; }
.deadline-example > div > span { display: block; margin-top: 5px; color: var(--auth-muted); font-size: 9px; }
.deadline-example > svg { width: 21px; margin-left: auto; flex-shrink: 0; stroke: var(--auth-green); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; animation: check-complete .35s ease both; }
.deadline-confirmed > div > span { color: var(--auth-green); }
.study-notebook, .notebook-sheet { transform-origin: left center; }
.notebook-page-enter-active { transition: opacity .24s var(--motion-ease), transform .24s var(--motion-ease); }
.notebook-page-leave-active { transition: opacity .1s ease, transform .1s ease; }
.notebook-page-enter-from { opacity: 0; transform: perspective(800px) rotateY(-5deg); }
.notebook-page-leave-to { opacity: 0; transform: translateX(-5px); }
.auth-panel { grid-column: 2; grid-row: 1; min-width: 0; min-height: 100vh; display: grid; place-items: center; padding: 54px clamp(30px, 5vw, 84px); }
.auth-form-wrap { width: 100%; max-width: 374px; }
.mobile-auth-brand { display: none; }
.auth-form-wrap h1 { margin: 0; font-family: var(--font-display); font-size: 34px; font-weight: 750; letter-spacing: -.035em; line-height: 1.4; }
.auth-intro { margin: 11px 0 28px; color: var(--auth-muted); font-size: 14px; line-height: 1.8; }
.form-alert { margin-bottom: 18px; padding: 11px 13px; border: 1px solid #e7c8c0; border-radius: 7px; color: #a2463e; background: #fdf3ef; font-size: 12px; line-height: 1.65; overflow-wrap: anywhere; }
form { display: grid; gap: 15px; }
.form-field { display: grid; gap: 7px; color: #466151; font-size: 13px; font-weight: 600; }
.form-field > input, .password-input { min-height: 48px; width: 100%; border: 1px solid #cddbd1; border-radius: 8px; background: #fff; transition: border-color .2s ease, box-shadow .2s ease; }
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
.submit-button { min-height: 49px; width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 9px; margin-top: 5px; border: 0; border-radius: 8px; color: #fff; background: var(--auth-green); font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; transition: background .18s ease, transform .18s ease; }
.submit-button:hover { background: #296651; }
.submit-button:active:not(:disabled) { transform: translateY(1px); }
.submit-button:disabled { background: #80a891; cursor: wait; }
.submit-spinner { width: 15px; height: 15px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: spin .7s linear infinite; }
.demo-entry { display: grid; justify-items: center; gap: 9px; margin-top: 23px; padding-top: 20px; border-top: 1px solid var(--auth-line); }
.demo-button { min-height: 44px; width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 9px; padding: 8px 18px; border: 1px solid #cddbd1; border-radius: 7px; color: #496f57; background: #fff; font: inherit; font-size: 13px; cursor: pointer; }
.demo-button:hover:not(:disabled) { background: #f5f8f6; border-color: #a9c5b1; }
.demo-button:disabled { opacity: .6; cursor: wait; }
.demo-entry small { color: var(--auth-muted); font-size: 10px; line-height: 1.7; text-align: center; }
.auth-switch { margin: 22px 0 0; color: var(--auth-muted); font-size: 12px; text-align: center; }
.auth-switch a { display: inline-block; padding: 4px; color: var(--auth-green); font-weight: 600; text-decoration: underline; text-underline-offset: 4px; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes notebook-arrive { from { opacity: 0; transform: translateY(16px) rotate(1.5deg); } to { opacity: 1; transform: translateY(0) rotate(-1.3deg); } }
@keyframes check-complete { 0% { transform: scale(.7); } 70% { transform: scale(1.12); } 100% { transform: scale(1); } }
@media (min-width: 1500px) { .auth-story { padding-top: 128px; padding-bottom: 60px; } .story-copy h2 { font-size: 43px; } .study-desk { margin-top: 49px; } }
@media (max-width: 1100px) { .auth-story { padding-right: 30px; padding-left: 30px; } .auth-panel { padding-right: 38px; padding-left: 38px; } .auth-brand { left: 30px; } .story-copy h2 { font-size: 33px; } .study-notebook { padding-right: 20px; padding-left: 24px; } .focus-example { gap: 13px; } .focus-dial { width: 115px; height: 115px; } }
@media (min-width: 801px) and (max-width: 930px) { .auth-story { padding-right: 23px; padding-left: 25px; } .auth-panel { padding-right: 30px; padding-left: 30px; } .story-copy h2 { font-size: 30px; } .study-desk { margin-top: 28px; } .study-notebook { padding-right: 17px; padding-left: 21px; } .sheet-heading h3 { font-size: 17px; } .course-ticket { gap: 10px; padding: 12px 10px; } .course-time { padding-right: 10px; } .course-ticket > svg { display: none; } .focus-example { gap: 11px; } .focus-dial { width: 105px; height: 105px; } .focus-dial strong { font-size: 24px; } .checklist-item { gap: 7px; font-size: 10px; } .checklist-item > small { font-size: 8px; } }
@media (max-width: 800px) { .auth-page { grid-template-columns: 1fr; } .auth-brand { display: none; } .auth-panel { grid-column: auto; grid-row: auto; min-height: auto; padding: 29px 26px 42px; } .mobile-auth-brand { display: inline-flex; align-items: center; gap: 10px; margin-bottom: 31px; } .mobile-auth-brand strong { font-size: 16px; font-weight: 650; } .auth-form-wrap { max-width: 390px; } .auth-form-wrap h1 { font-size: 28px; } .auth-intro { margin-top: 8px; margin-bottom: 23px; } .auth-story { grid-column: auto; grid-row: auto; padding: 37px 26px 31px; border-top: 1px solid var(--auth-line); border-right: 0; } .story-copy { max-width: 390px; } .story-copy h2 { font-size: 25px; line-height: 1.45; } .study-desk { max-width: 390px; margin-top: 29px; } .study-notebook { padding-top: 19px; } .notebook-preview { min-height: 280px; } }
@media (max-width: 420px) { .auth-panel { padding-right: 22px; padding-left: 22px; } .auth-form-wrap h1 { font-size: 27px; } .form-field input { font-size: 16px; } .auth-story { padding-right: 22px; padding-left: 22px; } .story-copy h2 { font-size: 23px; } .study-notebook { padding-right: 16px; padding-left: 20px; } .notebook-tabs { gap: 19px; } .notebook-tabs button { font-size: 11px; } .sheet-heading h3 { font-size: 17px; } .course-ticket { gap: 10px; padding: 12px 10px; } .course-time { padding-right: 10px; } .course-ticket > svg { display: none; } .course-ticket > div > span { font-size: 9px; } .ticket-separator { padding: 0 3px; } .checklist-item { gap: 7px; font-size: 10px; } .checklist-item > small { font-size: 8px; } .focus-example { gap: 13px; } .focus-dial { width: 106px; height: 106px; } .focus-dial strong { font-size: 24px; } .deadline-example { gap: 9px; } .deadline-example > div > strong { font-size: 11px; } .deadline-example > div > span { font-size: 8px; } .notebook-footer { font-size: 8px; } }
@media (prefers-reduced-motion: reduce) { .auth-page *, .auth-page *::before, .auth-page *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
</style>
