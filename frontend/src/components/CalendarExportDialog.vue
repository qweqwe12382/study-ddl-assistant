<template>
  <el-dialog :model-value="modelValue" title="带到手机日历" width="min(520px, 94vw)" @update:model-value="$emit('update:modelValue', $event)">
    <p>下载全部有截止时间的未完成任务，不受当前列表筛选影响。</p>
    <ol class="calendar-steps">
      <li>下载日历文件，用支持导入的日历应用打开。</li>
      <li>核对任务和截止时间，选择保存到哪个日历。</li>
      <li>检查提醒设置与日历通知权限，再保存。</li>
    </ol>
    <p>文件包含提前一天提醒。能否保留提醒取决于日历应用，下载文件本身不会开启通知。</p>
    <details>
      <summary>手机打不开文件，或任务修改了？</summary>
      <p>Android 与 iPhone 的导入入口因日历应用而异。若没有导入选项，可用支持导入的电脑日历导入，再通过你的日历账户同步到手机。</p>
      <p>这是一次导出，后续修改和完成状态不会自动同步。再次导入前检查已有日程，避免重复；已保存的旧日程需要在日历中自行调整。</p>
    </details>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" @click="downloadFile(exportsApi.tasksCalendarUrl())">下载日历文件</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ElDialog } from 'element-plus'
import { exportsApi } from '../api'
import { downloadFile } from '../utils/download'

defineProps({ modelValue: Boolean })
defineEmits(['update:modelValue'])
</script>

<style scoped>
p { line-height: 1.75; overflow-wrap: anywhere; }
.calendar-steps { padding-left: 1.5em; line-height: 1.9; }
details { margin-top: 18px; }
summary { cursor: pointer; color: var(--el-color-primary); }
summary:focus-visible { outline: 2px solid currentColor; outline-offset: 4px; }
</style>
