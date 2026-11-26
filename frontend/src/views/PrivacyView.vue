<template>
  <main class="privacy-page">
    <nav aria-label="返回学伴管家">
      <router-link to="/" class="privacy-home"><BrandMark /> 学伴管家</router-link>
      <router-link v-if="authSession.user" to="/app">返回学习空间</router-link>
    </nav>
    <article aria-labelledby="privacy-title">
      <h1 id="privacy-title">隐私与数据</h1>
      <p>学伴管家用这些数据提供登录、资料整理和学习安排。</p>

      <h2>我们保存什么</h2>
      <p>账号包括邮箱、昵称、密码的哈希值和登录会话。课程、上传的文件、粘贴的通知、任务、课表、考试、复习计划和专注用时保存在本站服务器上，按账号划分学习空间。</p>

      <h2>哪些服务会处理数据</h2>
      <p>默认识别由本站服务器运行规则。选择已启用的外部 AI 并确认后，待识别的资料内容会发送给该服务。公网登录和注册使用 Cloudflare Turnstile 验证，发验证码时邮件服务会处理收件邮箱和验证码邮件。</p>

      <h2>怎样管理数据</h2>
      <p>登录后，可以从资料库删除文件，从截止任务删除任务，从课表与考试移除日程。删除资料后，已经确认创建的任务仍可在任务列表中管理。复习计划支持归档。</p>
      <p v-if="contactEmail">申请删除账号及剩余资料，请用注册邮箱联系 <a :href="`mailto:${contactEmail}`">{{ contactEmail }}</a>。</p>
      <p v-else>账号和剩余数据的删除需要由本站管理员处理，网页暂未提供账号自助删除入口。</p>

      <h2>上传资料前</h2>
      <p>请只上传你有权处理的学习资料。通知里有与学习安排无关的个人信息时，可以先去掉再粘贴。</p>
    </article>
  </main>
</template>

<script setup>
import { authSession } from '../auth/session'
import BrandMark from '../components/BrandMark.vue'

const configuredContact = (import.meta.env.VITE_PUBLIC_CONTACT_EMAIL || '').trim()
const contactEmail = /^[\w.+-]+@[\w.-]+\.[a-z]{2,}$/i.test(configuredContact) ? configuredContact : ''
</script>

<style scoped>
.privacy-page { max-width: 720px; margin: 0 auto; padding: 28px 22px 64px; color: var(--ledger-ink); }
nav { display: flex; justify-content: space-between; flex-wrap: wrap; align-items: center; gap: 12px; }
nav a, article a { color: var(--ledger-link); }
.privacy-home { display: inline-flex; align-items: center; gap: 9px; font-weight: 700; text-decoration: none; }
article { margin-top: 34px; padding: clamp(20px, 5vw, 44px); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 14px; }
h1 { margin: 0 0 12px; font-size: 32px; }
h2 { margin: 24px 0 8px; font-size: 18px; }
p { margin: 0 0 10px; line-height: 1.8; overflow-wrap: anywhere; }
</style>
