<template>
  <el-dialog v-model="visible" title="补充预计用时" width="420px" destroy-on-close>
     <p class="estimate-dialog-help">这次填写的预计用时只用于当前建议，不会自动替你估算。</p>
    <el-form label-width="96px">
      <el-form-item label="预计用时" required>
        <div class="estimate-input-wrap">
          <el-input-number v-model="minutes" :min="15" :max="10080" :step="15" controls-position="right" />
          <span class="unit-label">分钟</span>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="form-actions">
        <el-button @click="emit('cancel')">取消</el-button>
       <el-button type="primary" :loading="busy" @click="emit('submit')">保存预计用时</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ElDialog, ElForm, ElFormItem, ElInputNumber } from 'element-plus'

defineProps({ busy: { type: Boolean, default: false } })
const visible = defineModel('visible', { type: Boolean, default: false })
const minutes = defineModel('minutes', { type: Number, default: null })
const emit = defineEmits(['cancel', 'submit'])
</script>

<style scoped>
.estimate-dialog-help { margin: 0 0 18px; color: #667085; font-size: 12px; line-height: 1.7; }
.estimate-input-wrap { display: flex; align-items: center; gap: 8px; }
.estimate-input-wrap .el-input-number { width: 190px; }
.unit-label { color: #667085; font-size: 12px; }
</style>
