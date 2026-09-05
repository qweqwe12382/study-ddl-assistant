<template>
  <section
    v-if="normalizedItems.length"
    class="source-disclosure"
    :class="{ 'source-disclosure--compact': compact }"
    :aria-label="label"
  >
    <span class="source-disclosure__label">{{ label }}</span>
    <div :id="sourceGroupId" class="source-disclosure__items" role="group" :aria-label="label">
      <button
        v-for="(item, index) in visibleItems"
        :key="sourceKey(item, index)"
        type="button"
        class="source-disclosure__item"
        :aria-label="sourceAriaLabel(item)"
        :aria-busy="item.loading || undefined"
        :disabled="item.disabled || item.loading"
        @click="openItem(item)"
      >
        <span class="source-disclosure__item-label">{{ item.label }}</span>
        <span v-if="item.loading" class="sr-only">正在打开</span>
      </button>
    </div>
    <button
      v-if="hasHiddenItems"
      type="button"
      class="source-disclosure__toggle"
      :aria-expanded="expanded"
      :aria-controls="sourceGroupId"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起' : `展开其余 ${hiddenItemCount} 条` }}
    </button>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

let nextSourceGroupId = 0

const props = defineProps({
  items: { type: Array, default: () => [] },
  label: { type: String, default: '查看来源' },
  initialLimit: { type: Number, default: 3 },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['open'])
const expanded = ref(false)
const sourceGroupId = `evidence-source-list-${++nextSourceGroupId}`

const normalizedItems = computed(() => (Array.isArray(props.items) ? props.items : []))
const displayLimit = computed(() => Math.max(0, Math.floor(Number(props.initialLimit) || 0)))
const hasHiddenItems = computed(() => normalizedItems.value.length > displayLimit.value)
const hiddenItemCount = computed(() => Math.max(0, normalizedItems.value.length - displayLimit.value))
const visibleItems = computed(() => (
  expanded.value || !hasHiddenItems.value
    ? normalizedItems.value
    : normalizedItems.value.slice(0, displayLimit.value)
))

function sourceKey(item, index) {
  return item?.key ?? `source-${index}`
}

function sourceAriaLabel(item) {
  const itemLabel = String(item?.ariaLabel || `${props.label}：${item?.label || '未命名来源'}`)
  if (item?.loading) return `${itemLabel}，正在打开`
  if (item?.disabled) return `${itemLabel}，当前不可用`
  return itemLabel
}

function openItem(item) {
  if (item?.disabled || item?.loading) return
  emit('open', item?.payload)
}
</script>

<style scoped>
.source-disclosure {
  display: flex;
  min-width: 0;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
  color: var(--ledger-muted, #667085);
  font-size: 12px;
  line-height: 1.5;
}

.source-disclosure__label {
  flex: 0 0 auto;
  color: var(--ledger-ink, #1e2a44);
  font-weight: 600;
}

.source-disclosure__items {
  display: flex;
  min-width: 0;
  flex: 1 1 180px;
  flex-wrap: wrap;
  gap: 6px;
}

.source-disclosure__item,
.source-disclosure__toggle {
  max-width: 100%;
  min-height: 44px;
  padding: 8px 11px;
  color: var(--ledger-ink, #1e2a44);
  text-align: left;
  background: var(--ledger-paper, #fffefb);
  border: 1px solid var(--ledger-line, #d9e0ea);
  border-radius: 4px;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  line-height: 1.35;
}

.source-disclosure__item-label {
  display: block;
  overflow-wrap: anywhere;
}

.source-disclosure__item:hover:not(:disabled),
.source-disclosure__toggle:hover {
  background: #f4f5ff;
  border-color: #aeb6ff;
}

.source-disclosure__item:focus-visible,
.source-disclosure__toggle:focus-visible {
  position: relative;
  z-index: 1;
  outline: 3px solid rgba(89, 100, 237, .72);
  outline-offset: 2px;
}

.source-disclosure__item:disabled {
  color: #667085;
  background: #f6f7f9;
  border-color: #dfe3e9;
  cursor: not-allowed;
}

.source-disclosure--compact {
  gap: 5px;
  margin-top: 7px;
  font-size: 12px;
}

.source-disclosure--compact .source-disclosure__items { gap: 5px; }
.source-disclosure--compact .source-disclosure__item,
.source-disclosure--compact .source-disclosure__toggle { padding: 7px 10px; }

@media (max-width: 390px) {
  .source-disclosure__items { flex-basis: 100%; }
  .source-disclosure__item,
  .source-disclosure__toggle { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .source-disclosure__item,
  .source-disclosure__toggle { transition: none; }
}
</style>
