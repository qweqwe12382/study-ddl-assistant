<template>
  <div class="landing-page">
    <a class="public-skip" href="#landing-main">跳到主要内容</a>
    <header class="landing-nav">
      <router-link class="landing-brand" to="/" aria-label="学伴管家首页">
        <span class="brand-mark" aria-hidden="true">学</span><strong>学伴管家</strong>
      </router-link>
      <nav class="landing-links" aria-label="首页导航"><a href="#workflow">怎么使用</a><a href="#workspace">全部功能</a></nav>
      <div class="landing-account">
        <router-link v-if="authSession.user" class="button button-primary" to="/app">进入学习空间</router-link>
        <template v-else>
          <router-link class="text-link" to="/login">登录</router-link>
          <router-link class="button button-primary" to="/register">注册</router-link>
        </template>
      </div>
    </header>
    <main id="landing-main" tabindex="-1">
      <section class="hero-section" aria-labelledby="hero-title">
        <div class="hero-copy">
          <h1 id="hero-title">资料收在一起，<br>今天心里有数。</h1>
          <p class="hero-lead">收好课程资料，记下作业截止，安排每天复习。通知临时改期，先看影响再确认。</p>
          <div class="hero-actions">
            <router-link class="button button-primary" :to="authSession.user ? '/app' : '/register'">{{ authSession.user ? '打开今天的安排' : '建立学习空间' }}</router-link>
            <router-link v-if="authSession.user" class="button button-secondary" to="/deadline-radar">打开 DDL 应变台</router-link>
            <button v-else class="button button-secondary" type="button" :disabled="demoLoading" @click="startDemo">{{ demoLoading ? '正在准备演示…' : '体验示例空间' }}</button>
          </div>
          <p v-if="demoError" class="demo-error" role="alert">{{ demoError }}</p>
          <p v-else-if="!authSession.user" class="hero-hint">演示无需注册，使用独立示例数据，仅本地开发环境提供。</p>
          <p v-else class="hero-hint">{{ authSession.user.display_name }}，欢迎回来。</p>
          <div class="hero-principle"><span aria-hidden="true">✓</span> 保留原文依据，确认后再更新。</div>
        </div>
        <section class="notice-example" aria-labelledby="example-title">
          <div class="example-topline"><span>DDL 应变台</span><span class="example-tag">交互示例</span></div>
          <h2 id="example-title">通知变了，安排怎么变？</h2>
          <div class="example-switch" role="group" aria-label="选择通知示例">
            <button type="button" :aria-pressed="exampleMode === 'earlier'" @click="exampleMode = 'earlier'">截止提前</button>
            <button type="button" :aria-pressed="exampleMode === 'later'" @click="exampleMode = 'later'">截止延期</button>
          </div>
          <div class="example-result" aria-live="polite" aria-atomic="true">
            <div class="notice-source"><span class="source-label">课程群通知 · 示例</span><blockquote>{{ example.notice }}</blockquote></div>
            <div class="deadline-change">
              <div><span>原截止时间</span><strong>9 月 20 日</strong><small>23:59</small></div>
              <span class="change-arrow" aria-hidden="true">→</span>
              <div class="proposed-date"><span>{{ example.label }}</span><strong>{{ example.date }}</strong><small>{{ example.time }}</small></div>
            </div>
            <p class="example-explanation">{{ example.explanation }}</p>
          </div>
          <div class="example-footnote"><span class="pending-mark" aria-hidden="true"></span>先核对通知，再确认执行</div>
          <p class="example-boundary">说明示例，不会修改任务。进入应变台可查看实际影响。</p>
          <router-link class="example-link" to="/deadline-radar">进入 DDL 应变台</router-link>
        </section>
      </section>
      <section id="workflow" class="workflow-section" aria-labelledby="workflow-title">
        <div class="section-heading"><h2 id="workflow-title">三步开始使用</h2><p>识别结果可以修改，核对后再保存。</p></div>
        <ol class="workflow-list">
          <li><span class="step-number" aria-hidden="true">1</span><div><h3>收好课程资料</h3><p>上传通知、文档或图片，也可以直接粘贴通知原文。</p><router-link to="/materials">进入资料库</router-link></div></li>
          <li><span class="step-number" aria-hidden="true">2</span><div><h3>核对任务与截止</h3><p>对照来源确认课程、日期和任务名称，再加入截止任务。</p><router-link to="/tasks">查看截止任务</router-link></div></li>
          <li><span class="step-number" aria-hidden="true">3</span><div><h3>安排复习与专注</h3><p>把复习拆成能完成的小步，用专注计时记录实际用时。</p><router-link to="/study-plans">安排复习计划</router-link></div></li>
        </ol>
      </section>
      <section id="workspace" class="workspace-section" aria-labelledby="workspace-title">
        <div><h2 id="workspace-title">学习空间，按需切换</h2><p>课程、任务、复习，每一页都能直接找到。</p></div>
        <nav class="workspace-links" aria-label="学习空间全部功能"><router-link v-for="entry in workspaceEntries" :key="entry.path" :to="entry.path">{{ entry.label }}</router-link></nav>
      </section>
    </main>
    <footer class="landing-footer"><strong>学伴管家</strong><p>学习安排由你决定。不会代交作业，也不会登录学校系统。</p><span>本地开发版本</span></footer>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { authSession, demoLogin } from '../auth/session'

const router = useRouter()
const demoLoading = ref(false)
const demoError = ref('')
const exampleMode = ref('earlier')
const examples = {
  earlier: {
    notice: '数据结构实验报告提交时间提前至 9 月 18 日 20:00，请同学们重新安排。',
    label: '提前后的截止',
    date: '9 月 18 日',
    time: '20:00',
    explanation: '提交窗口变短，先看这几天能否留出完成时间。',
  },
  later: {
    notice: '数据结构实验报告提交时间延期至 9 月 22 日 23:59，其他要求不变。',
    label: '延期后的截止',
    date: '9 月 22 日',
    time: '23:59',
    explanation: '提交窗口变长，可以重新核对它和其他任务的安排。',
  },
}
const example = computed(() => examples[exampleMode.value])
const workspaceEntries = [
  { path: '/app', label: '学习总览' },
  { path: '/materials', label: '资料库' },
  { path: '/tasks', label: '截止任务' },
  { path: '/deadline-radar', label: 'DDL 应变台' },
  { path: '/focus', label: '专注计时' },
  { path: '/schedule', label: '课表与考试' },
  { path: '/study-plans', label: '复习计划' },
  { path: '/settings', label: '设置' },
]

async function startDemo() {
  if (demoLoading.value) return
  demoError.value = ''
  demoLoading.value = true
  try {
    await demoLogin()
    await router.push('/app')
  } catch (error) {
    demoError.value = error?.message || '演示暂不可用，请稍后重试，或使用邮箱注册。'
  } finally {
    demoLoading.value = false
  }
}
</script>

<style scoped>
.landing-page { --landing-ink: #243d36; --landing-green: #327864; --landing-muted: #607268; --landing-line: #e0e8e3; min-height: 100vh; color: var(--landing-ink); background: #f5f8f7; font-family: "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif; }
.landing-page * { box-sizing: border-box; }
.landing-page a { color: inherit; text-decoration: none; }
.landing-page button { font: inherit; }
.landing-page :is(a, button):focus-visible { outline: 3px solid #79aa98; outline-offset: 4px; }
.public-skip { position: fixed; z-index: 100; top: -70px; left: 16px; padding: 12px 16px; border-radius: 6px; background: #fff; }
.public-skip:focus { top: 12px; }
.landing-nav { min-height: 80px; max-width: 1200px; margin: auto; padding: 18px 36px; display: flex; align-items: center; gap: 44px; border-bottom: 1px solid var(--landing-line); }
.landing-brand { display: inline-flex; align-items: center; gap: 10px; flex-shrink: 0; }
.brand-mark { display: grid; place-items: center; width: 34px; height: 36px; border-radius: 9px 9px 3px 9px; color: #fff; background: var(--landing-green); font-size: 18px; font-weight: 650; }
.landing-brand strong { font-size: 18px; font-weight: 650; }
.landing-links, .landing-account { display: flex; align-items: center; gap: 26px; }
.landing-links { font-size: 13px; color: var(--landing-muted); }
.landing-links a:hover, .text-link:hover { color: var(--landing-green); }
.landing-account { margin-left: auto; gap: 20px; font-size: 13px; }
.button { display: inline-flex; min-height: 46px; align-items: center; justify-content: center; padding: 11px 21px; border: 1px solid transparent; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; line-height: 1.5; }
.landing-nav .button { min-height: 40px; padding: 8px 19px; font-size: 13px; }
.landing-page .button-primary { color: #fff; background: var(--landing-green); }
.button-primary:hover { background: #296651; }
.button-secondary { color: var(--landing-ink); border-color: #c7d8ce; background: transparent; }
.button-secondary:hover { background: #eaf1ed; }
.button:disabled { opacity: .65; cursor: wait; }
.hero-section { display: grid; grid-template-columns: 1fr minmax(0, 430px); align-items: center; gap: 70px; max-width: 1200px; margin: auto; padding: 56px 36px 60px; }
.hero-context { margin: 0 0 23px; color: var(--landing-muted); font-size: 13px; line-height: 1.7; }
.hero-copy h1 { margin: 0; font-size: clamp(36px, 3.8vw, 50px); line-height: 1.38; letter-spacing: -.035em; font-weight: 650; }
.hero-lead { max-width: 420px; margin: 24px 0 28px; color: #5d7268; font-size: 15px; line-height: 1.9; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 12px; }
.hero-hint, .demo-error { max-width: 420px; margin: 13px 0 0; color: var(--landing-muted); font-size: 11px; line-height: 1.7; }
.demo-error { color: #a2463e; }
.hero-principle { display: flex; align-items: center; gap: 7px; margin-top: 38px; color: #526c5e; font-size: 12px; }
.hero-principle span { color: var(--landing-green); }
.notice-example { min-width: 0; padding: 26px 28px 22px; border: 1px solid #dce6df; border-radius: 12px; background: #fff; }
.example-topline { display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: 12px; color: var(--landing-muted); }
.example-tag { padding: 3px 7px; border-radius: 4px; color: #607569; background: #f0f5f1; font-size: 10px; }
.notice-example h2 { margin: 19px 0 18px; font-size: 21px; line-height: 1.5; font-weight: 650; }
.example-switch { display: flex; gap: 4px; width: fit-content; margin-bottom: 20px; padding: 3px; border: 1px solid var(--landing-line); border-radius: 7px; background: #f5f8f6; }
.example-switch button { min-height: 34px; padding: 6px 14px; border: 0; border-radius: 4px; color: #607268; background: transparent; font-size: 12px; cursor: pointer; }
.example-switch button[aria-pressed="true"] { color: var(--landing-green); background: #fff; box-shadow: 0 1px 3px rgba(36, 61, 54, .08); font-weight: 600; }
.notice-source { padding-left: 13px; border-left: 2px solid #cadccd; }
.source-label { color: var(--landing-muted); font-size: 11px; }
.notice-source blockquote { min-height: 50px; margin: 6px 0 0; color: #435e50; font-size: 13px; line-height: 1.85; }
.deadline-change { display: grid; grid-template-columns: 1fr 24px 1fr; align-items: center; gap: 12px; margin: 22px 0 15px; padding: 18px 0; border-top: 1px solid var(--landing-line); border-bottom: 1px solid var(--landing-line); }
.deadline-change > div { min-width: 0; display: grid; gap: 4px; }
.deadline-change div > span { margin-bottom: 3px; color: var(--landing-muted); font-size: 11px; }
.deadline-change strong { font-size: 20px; font-weight: 600; }
.deadline-change small { color: var(--landing-muted); font-size: 12px; }
.deadline-change .proposed-date strong, .deadline-change .proposed-date small { color: var(--landing-green); }
.change-arrow { color: #97afa0; font-size: 21px; text-align: center; }
.example-explanation { min-height: 42px; margin: 0; color: #5d7268; font-size: 12px; line-height: 1.8; }
.example-footnote { display: flex; align-items: center; gap: 7px; margin-top: 12px; color: #567461; font-size: 12px; }
.pending-mark { width: 7px; height: 7px; border: 1px solid #729a7e; border-radius: 50%; }
.example-boundary { margin: 8px 0 12px; color: var(--landing-muted); font-size: 11px; line-height: 1.7; }
.landing-page .example-link { display: inline-block; padding: 4px 0; color: var(--landing-green); font-size: 12px; text-decoration: underline; text-underline-offset: 4px; }
.workflow-section { max-width: 1200px; margin: auto; padding: 44px 36px 52px; border-top: 1px solid var(--landing-line); scroll-margin-top: 24px; }
.section-heading h2, .workspace-section h2 { margin: 0; font-size: 23px; font-weight: 600; line-height: 1.5; letter-spacing: -.02em; }
.section-heading > p, .workspace-section > div p { margin: 10px 0 0; color: var(--landing-muted); font-size: 13px; line-height: 1.7; }
.workflow-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 38px; margin: 34px 0 0; padding: 0; list-style: none; }
.workflow-list li { display: flex; align-items: flex-start; gap: 14px; }
.step-number { display: grid; place-items: center; flex-shrink: 0; width: 26px; height: 26px; border: 1px solid #cbdccf; border-radius: 50%; color: var(--landing-green); font-size: 12px; }
.workflow-list h3 { margin: 2px 0 10px; font-size: 15px; font-weight: 600; }
.workflow-list p { margin: 0 0 12px; color: var(--landing-muted); font-size: 13px; line-height: 1.8; }
.workflow-list a { display: inline-flex; min-height: 30px; align-items: center; color: var(--landing-green); font-size: 12px; text-decoration: underline; text-underline-offset: 4px; }
.workspace-section { max-width: 1128px; display: grid; grid-template-columns: 1fr 1.1fr; align-items: center; gap: 30px; margin: 0 auto 48px; padding: 29px 30px; border-radius: 10px; background: #eaf2ec; scroll-margin-top: 24px; }
.workspace-section h2 { font-size: 20px; }
.workspace-links { display: flex; flex-wrap: wrap; gap: 6px 20px; }
.workspace-links a { display: inline-flex; align-items: center; min-height: 36px; color: #496d57; font-size: 13px; }
.workspace-links a:hover { text-decoration: underline; text-underline-offset: 4px; }
.landing-footer { max-width: 1200px; display: flex; align-items: center; gap: 24px; margin: auto; padding: 24px 36px 30px; border-top: 1px solid var(--landing-line); color: var(--landing-muted); font-size: 11px; line-height: 1.8; }
.landing-footer strong { color: #56715f; font-size: 13px; font-weight: 600; white-space: nowrap; }
.landing-footer p { margin: 0; }
.landing-footer > span { margin-left: auto; white-space: nowrap; }
@media (max-width: 980px) { .hero-section { grid-template-columns: 1fr minmax(0, 390px); gap: 30px; padding-top: 48px; } .hero-copy h1 { font-size: 38px; } .notice-example { padding: 22px; } .workspace-section { margin-right: 36px; margin-left: 36px; } .workflow-list { gap: 22px; } }
@media (max-width: 760px) { .landing-nav { min-height: 70px; gap: 20px; padding: 15px 24px; } .landing-links { display: none; } .hero-section { grid-template-columns: 1fr; gap: 36px; padding: 40px 24px 44px; } .hero-copy h1 { font-size: 40px; } .hero-context { margin-bottom: 17px; } .hero-lead { margin-top: 18px; } .hero-principle { margin-top: 22px; } .notice-example { max-width: 490px; width: 100%; justify-self: center; } .workflow-section { padding: 34px 24px 38px; } .workflow-list { grid-template-columns: 1fr; gap: 28px; margin-top: 27px; } .workflow-list p { margin-bottom: 4px; } .section-heading h2 { font-size: 21px; } .workspace-section { grid-template-columns: 1fr; gap: 16px; margin: 0 24px 32px; padding: 23px; } .workspace-links { gap: 4px 22px; } .landing-footer { flex-wrap: wrap; gap: 8px 20px; padding: 22px 24px; } .landing-footer p { width: 100%; order: 2; } }
@media (max-width: 420px) { .landing-nav { padding: 14px 18px; } .landing-brand strong { font-size: 16px; } .landing-account { gap: 14px; } .landing-nav .button { padding-right: 15px; padding-left: 15px; } .hero-section { padding: 32px 18px 38px; } .hero-copy h1 { font-size: 36px; } .hero-context { font-size: 12px; } .hero-lead { font-size: 14px; } .hero-actions { gap: 10px; } .hero-actions .button { flex: 1; padding-right: 12px; padding-left: 12px; font-size: 13px; } .notice-example { padding: 22px 20px; } .notice-example h2 { font-size: 20px; } .deadline-change { gap: 7px; } .deadline-change strong { font-size: 19px; } .workflow-section { padding-right: 18px; padding-left: 18px; } .workspace-section { margin-right: 18px; margin-left: 18px; padding: 21px; } .workspace-section h2 { font-size: 19px; } .landing-footer { padding-right: 18px; padding-left: 18px; } }
</style>
