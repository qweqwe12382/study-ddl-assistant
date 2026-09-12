<template>
  <el-dialog
    :model-value="visible"
    title="粘贴通知"
    width="620px"
    :close-on-click-modal="!submitting"
    :close-on-press-escape="!submitting"
    :show-close="!submitting"
    @update:model-value="onVisibleChange"
  >
    <el-form class="paste-notice-form" aria-describedby="paste-notice-help" label-position="top" @submit.prevent="emit('submit')">
      <p id="paste-notice-help" class="paste-notice-intro">把课程群或教学平台的文字贴在这里。系统只保存为课程通知并展示识别候选，确认前不会创建任务。</p>
      <el-form-item label="通知标题（可选）">
        <el-input v-model="draft.title" maxlength="120" show-word-limit placeholder="例如：高等数学作业通知" :disabled="submitting" autocomplete="off" />
      </el-form-item>
      <el-form-item label="通知正文" required>
        <el-input
          v-model="draft.text"
          type="textarea"
          :rows="9"
          :maxlength="MAX_PASTE_NOTICE_CHARACTERS"
          show-word-limit
          placeholder="粘贴老师或教学平台发布的通知全文"
          :disabled="submitting"
          aria-label="通知正文"
        />
      </el-form-item>
      <el-form-item label="通知参考时间" required>
        <el-date-picker
          v-model="draft.sourceTime"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          format="YYYY-MM-DD HH:mm"
          placeholder="选择通知发布时间或阅读时间"
          :disabled="submitting"
          style="width: 100%"
          aria-label="通知参考时间"
        />
        <p class="paste-notice-reference">“明天”“本周”等相对日期会按这个时间理解。默认是现在，按北京时间（Asia/Shanghai）处理；可按通知实际时间修改。</p>
      </el-form-item>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" role="alert" />
      <el-alert v-else-if="duplicate" title="这段通知已作为资料保存。草稿仍保留，你可以查看已有资料后决定是否修改。" type="warning" show-icon :closable="false" />
    </el-form>
    <template #footer>
      <div class="paste-notice-actions">
        <el-button v-if="duplicate" plain :disabled="submitting" @click="emit('show-existing')">查看已有资料</el-button>
        <el-button :disabled="submitting" @click="emit('close')">保留草稿并关闭</el-button>
        <el-button type="primary" :loading="submitting" :disabled="submitting" @click="emit('submit')">保存并查看识别结果</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ElAlert, ElButton, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus'

import { MAX_PASTE_NOTICE_CHARACTERS } from '../utils/pasteNotice'

const props = defineProps({
  visible: { type: Boolean, default: false },
  draft: { type: Object, required: true },
  submitting: { type: Boolean, default: false },
  error: { type: String, default: '' },
  duplicate: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'show-existing', 'submit'])

function onVisibleChange(visible) {
  if (!visible && !props.submitting) emit('close')
}
</script>

<style scoped>
.paste-notice-form { min-width: 0; }
.paste-notice-intro { max-width: 54ch; margin: 0 0 18px; color: #667085; font-size: 14px; line-height: 1.65; }
.paste-notice-reference { margin: 8px 0 0; color: #667085; font-size: 12px; line-height: 1.55; }
.paste-notice-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
@media (max-width: 560px) {
  .paste-notice-intro { font-size: 13px; }
  .paste-notice-actions { align-items: stretch; flex-direction: column-reverse; }
  .paste-notice-actions :deep(.el-button) { width: 100%; margin-left: 0; }
  .paste-notice-form :deep(.el-textarea__inner) { font-size: 16px; }
}
</style>
