<template>
  <component
    :is="embedded ? 'section' : ElDialog"
    v-bind="embedded ? {} : { modelValue: visible, title: '添加资料 · 粘贴文字', width: '620px', closeOnClickModal: !submitting, closeOnPressEscape: !submitting, showClose: !submitting }"
    @update:model-value="onVisibleChange"
  >
    <el-form class="paste-notice-form" aria-describedby="paste-notice-help" label-position="top" @submit.prevent="emit('submit')">
      <p id="paste-notice-help" class="paste-notice-intro">贴入通知、笔记或复习提纲，保存后直接核对结果。只有你确认的事项才会加入任务。</p>
      <el-form-item label="文字内容" required>
        <el-input
          v-model="draft.text"
          type="textarea"
          :rows="9"
          :maxlength="MAX_PASTE_NOTICE_CHARACTERS"
          show-word-limit
          placeholder="在这里粘贴完整内容，例如老师的作业通知、课堂笔记或复习提纲"
          :disabled="submitting"
          aria-label="文字内容（通知正文）"
        />
      </el-form-item>
      <details class="paste-notice-details" :open="Boolean(error && !draft.sourceTime)">
        <summary>补充标题或修改参考时间<span>默认按当前时间理解“明天”等日期</span></summary>
        <el-form-item label="通知标题（可选）">
          <el-input v-model="draft.title" maxlength="120" show-word-limit placeholder="留空自动命名" :disabled="submitting" autocomplete="off" />
        </el-form-item>
      <el-form-item label="通知参考时间">
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
      </details>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" role="alert" />
      <el-alert v-else-if="duplicate" title="这段通知已作为资料保存。草稿仍保留，你可以查看已有资料后决定是否修改。" type="warning" show-icon :closable="false" />
    </el-form>
      <div class="paste-notice-actions">
        <el-button v-if="duplicate" plain :disabled="submitting" @click="emit('show-existing')">查看已有资料</el-button>
        <el-button :disabled="submitting" @click="emit('close')">保留草稿并关闭</el-button>
        <el-button type="primary" :loading="submitting" :disabled="submitting || !draft.text.trim()" @click="emit('submit')">保存并核对</el-button>
      </div>
  </component>
</template>

<script setup>
import { ElAlert, ElButton, ElDatePicker, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus'

import { MAX_PASTE_NOTICE_CHARACTERS } from '../utils/pasteNotice'

const props = defineProps({
  visible: { type: Boolean, default: false },
  embedded: { type: Boolean, default: false },
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
.paste-notice-details { margin-bottom: 16px; border-top: 1px solid var(--ledger-line, #d9e0ea); }
.paste-notice-details summary { padding: 14px 0; cursor: pointer; font-size: 13px; }
.paste-notice-details summary span { display: block; margin-top: 5px; color: var(--ledger-muted, #667085); font-size: 12px; }
.paste-notice-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
@media (max-width: 560px) {
  .paste-notice-intro { font-size: 13px; }
  .paste-notice-actions { align-items: stretch; flex-direction: column-reverse; }
  .paste-notice-actions :deep(.el-button) { width: 100%; margin-left: 0; }
  .paste-notice-form :deep(.el-textarea__inner) { font-size: 16px; }
}
</style>
