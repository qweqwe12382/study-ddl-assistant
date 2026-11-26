<template>
  <span class="course-label"><i aria-hidden="true" :style="{ backgroundColor: swatch }"></i>{{ name }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ name: { type: String, required: true }, color: { type: String, default: '' } })
const swatch = computed(() => /^#[0-9a-f]{6}$/i.test(props.color) ? props.color : 'var(--ledger-muted)')
</script>

<style scoped>
.course-label { display: inline-flex; align-items: baseline; gap: 6px; max-width: 100%; overflow-wrap: anywhere; color: var(--ledger-ink); font: 500 13px/1.6 var(--font-content); }
i { flex: none; width: 8px; height: 8px; border-radius: 50%; box-shadow: inset 0 0 0 1px rgb(0 0 0 / 14%); }
</style>
