<template>
  <ElDatePicker
    :default-value="new Date(localReferenceDateTime())"
    :show-now="false"
    value-format="YYYY-MM-DDTHH:mm:ss"
    format="YYYY-MM-DD HH:mm"
    type="datetime"
  />
</template>

<script setup>
import { ElDatePicker } from 'element-plus'
import { localReferenceDateTime } from '../utils/pasteNotice'
</script>
