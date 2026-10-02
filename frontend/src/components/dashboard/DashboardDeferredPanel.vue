<template>
  <component v-if="panel" :is="panel" v-bind="$attrs" @cancel="emit('cancel')" />
  <div v-else class="deferred-panel-state" :aria-busy="loading">
    <p :role="failed ? 'alert' : 'status'" aria-live="polite">
      {{ failed ? `${label}暂时未能加载，请重试。` : `正在加载${label}…` }}
    </p>
    <div class="deferred-panel-actions">
      <button v-if="failed" type="button" @click="loadPanel">重新加载{{ label }}</button>
      <button v-if="cancelable" type="button" @click="emit('cancel')">取消</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, shallowRef } from 'vue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  loader: { type: Function, required: true },
  label: { type: String, required: true },
  cancelable: { type: Boolean, default: false },
})
const emit = defineEmits(['cancel'])
const panel = shallowRef(null)
const loading = ref(false)
const failed = ref(false)

async function loadPanel() {
  if (loading.value || panel.value) return
  loading.value = true
  failed.value = false
  try {
    const loaded = await props.loader()
    panel.value = loaded.default
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(loadPanel)
</script>

<style scoped>
.deferred-panel-state { padding: 12px 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; }
.deferred-panel-state p { margin: 0; }
.deferred-panel-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.deferred-panel-actions button { min-height: 44px; padding: 8px 0; color: var(--ledger-link); background: transparent; border: 0; font: inherit; text-align: left; cursor: pointer; }
.deferred-panel-actions button:focus-visible { outline: 3px solid var(--ledger-link); outline-offset: 3px; }
</style>
