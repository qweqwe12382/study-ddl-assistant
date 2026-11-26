<template>
  <section v-if="draft?.kind === 'class_change'" class="notice-review" aria-label="核对调课通知">
    <strong>{{ draft.courseName || '课程' }} · 调课通知</strong>
    <p>原时段 {{ draft.original_date }} {{ draft.original_time_text || '待核对' }}</p>
    <p>拟调整至 {{ draft.starts_at ? formatDateTime(draft.starts_at) : '待核对' }}（北京时间）</p>
    <p v-if="draft.location">地点 {{ draft.location }}</p>
    <p>请对照原通知和课表确认这一次调课。课表中的课程会按周重复。</p>
    <details><summary>查看通知原文</summary><p>{{ draft.source_quote }}</p></details>
    <el-button size="small" @click="closeReview">关闭提示</el-button>
  </section>
</template>

<script setup>
import { onMounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authSession } from '../auth/session'
import { formatDateTime } from '../utils/format'

const emit = defineEmits(['exam'])
const route = useRoute()
const router = useRouter()
const draft = shallowRef(null)

function closeReview() {
  router.replace({ path: route.path, state: { noticeDraft: null } })
}

onMounted(() => {
  const saved = window.history.state?.noticeDraft
  if (!authSession.user || saved?.owner !== authSession.user.id) return closeReview()
  if (saved.kind === 'class_change') {
    draft.value = saved
    return
  }
  if (saved.kind === 'exam') {
    emit('exam', {
      course_id: saved.courseId,
      title: saved.courseName && !saved.title.includes(saved.courseName) ? `${saved.courseName}${saved.title}` : saved.title,
      exam_type: saved.title.includes('期中') ? 'midterm' : saved.title.includes('期末') ? 'final' : 'other',
      starts_at: saved.starts_at,
      location: saved.location,
      note: saved.scope ? `考试范围：${saved.scope}` : '',
    })
  }
  closeReview()
})
</script>

<style scoped>
.notice-review { margin-bottom: 18px; padding: 16px; border: 1px solid var(--ledger-line); border-radius: 10px; overflow-wrap: anywhere; }
p { margin: 6px 0; }
.el-button { margin-top: 10px; }
</style>
