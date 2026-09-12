<template>
  <el-dialog :model-value="visible" title="刚创建的任务" width="520px" @update:model-value="onVisibleChange">
    <template v-if="taskRefs.length">
      <p class="confirmed-tasks-intro">选择一项任务，继续安排或记录进度。</p>
      <div class="confirmed-task-list" role="list" aria-label="刚创建的任务">
        <div v-for="task in taskRefs" :key="`${task.id}:${task.navigation_key}`" class="confirmed-task" role="listitem">
          <span>{{ task.name || '已创建任务' }}</span>
          <el-button link type="primary" :loading="loadingKey === taskKey(task)" :disabled="Boolean(loadingKey)" @click="openTask(task)">查看任务</el-button>
        </div>
      </div>
      <el-alert v-if="error" :title="error" type="warning" show-icon :closable="false" role="alert" />
    </template>
    <el-alert v-else title="这个历史确认记录没有可验证的任务身份。你仍可在任务清单中查看任务。" type="info" show-icon :closable="false" />
    <template #footer>
      <div class="confirmed-tasks-actions">
        <el-button @click="emit('close')">关闭</el-button>
        <el-button type="primary" @click="emit('open-task-list')">查看任务清单</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElAlert, ElButton, ElDialog } from 'element-plus'

import { agentApi } from '../api'
import { navigationKey, positiveMaterialId, validatedSourceNavigationTarget } from '../utils/materialSourceNavigation'

const props = defineProps({
  visible: { type: Boolean, default: false },
  refs: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'navigate', 'open-task-list'])
const loadingKey = ref('')
const error = ref('')
const taskRefs = computed(() => (Array.isArray(props.refs) ? props.refs : []).map((item) => {
  const id = positiveMaterialId(item?.id)
  const key = navigationKey(item?.navigation_key)
  const name = typeof item?.name === 'string' ? item.name.trim().slice(0, 200) : ''
  return id !== null && key ? { id, navigation_key: key, name } : null
}).filter(Boolean))

function taskKey(task) {
  return `${task.id}:${task.navigation_key}`
}

function onVisibleChange(visible) {
  if (!visible) emit('close')
}

async function openTask(task) {
  const sourceRef = { source_type: 'task', source_id: String(task.id), navigation_key: task.navigation_key }
  const key = taskKey(task)
  if (loadingKey.value) return
  loadingKey.value = key
  error.value = ''
  try {
    const resolved = await agentApi.resolveSourceRefs([sourceRef])
    const target = validatedSourceNavigationTarget(resolved, sourceRef)
    if (!target) {
      error.value = '这项任务已删除或暂时无法打开。请从任务清单中查看。'
      return
    }
    emit('navigate', target)
  } catch (err) {
    error.value = err?.message || '任务入口暂时无法解析，请稍后重试。'
  } finally {
    loadingKey.value = ''
  }
}
</script>

<style scoped>
.confirmed-tasks-intro { margin: 0 0 14px; color: #667085; font-size: 14px; line-height: 1.6; }
.confirmed-task-list { display: grid; gap: 8px; margin-bottom: 14px; }
.confirmed-task { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; padding: 10px 12px; color: #344054; background: #fbfcff; border: 1px solid #e7eaf5; border-radius: 7px; font-size: 14px; line-height: 1.45; }
.confirmed-task > span { min-width: 0; overflow-wrap: anywhere; }
.confirmed-task :deep(.el-button) { flex: 0 0 auto; min-height: 38px; }
.confirmed-tasks-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
@media (max-width: 560px) {
  .confirmed-task { align-items: flex-start; flex-direction: column; }
  .confirmed-task :deep(.el-button) { min-height: 44px; }
  .confirmed-tasks-actions { align-items: stretch; flex-direction: column-reverse; }
  .confirmed-tasks-actions :deep(.el-button) { width: 100%; margin-left: 0; }
}
</style>
