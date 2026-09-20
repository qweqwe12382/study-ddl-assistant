<template>
  <section
    class="ledger-disclosure"
    :class="{ 'ledger-disclosure--open': props.open }"
    :data-section-id="props.sectionId"
  >

    <button
      :id="triggerId"
      type="button"
      class="ledger-disclosure__trigger"
      :aria-expanded="props.open"
      :aria-controls="panelId"
      :aria-label="`${props.open ? '收起' : '展开'}${props.title}`"
      @click="toggle"
    >
      <span class="ledger-disclosure__trigger-main">
        <span class="ledger-disclosure__copy">
          <span :id="titleId" class="ledger-disclosure__title">{{ props.title }}</span>
          <span v-if="props.description && props.open" class="ledger-disclosure__description">{{ props.description }}</span>
        </span>
      </span>

      <span class="ledger-disclosure__trigger-meta">
        <span v-if="props.meta" class="ledger-disclosure__meta">{{ props.meta }}</span>
        <span class="ledger-disclosure__chevron-wrap" aria-hidden="true">
          <span class="ledger-disclosure__chevron"></span>
        </span>
        <span class="ledger-disclosure__state">{{ props.open ? '收起' : '展开' }}</span>
      </span>
    </button>

    <Transition name="reveal-panel">
    <div v-if="props.open" class="ledger-disclosure__reveal"><div
      :id="panelId"
      class="ledger-disclosure__panel"
      role="region"
      :aria-labelledby="titleId"
    >
      <div class="ledger-disclosure__content">
        <slot />
      </div>
    </div></div>
    </Transition>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  sectionId: { type: String, required: true },
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  meta: { type: String, default: '' },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['update:open'])

const triggerId = computed(() => `${props.sectionId}-trigger`)
const titleId = computed(() => `${props.sectionId}-title`)
const panelId = computed(() => `${props.sectionId}-panel`)

function toggle() {
  emit('update:open', !props.open)
}
</script>

<style scoped>

.ledger-disclosure { min-width: 0; margin-top: 20px; color: var(--ledger-ink); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 10px; }
.ledger-disclosure__trigger { display: flex; align-items: center; justify-content: space-between; gap: 18px; width: 100%; min-height: 64px; padding: 16px 20px; border: 0; border-radius: 10px; color: inherit; background: transparent; font: inherit; text-align: left; cursor: pointer; }
.ledger-disclosure__trigger:hover { background: var(--ledger-canvas); }
.ledger-disclosure__trigger-main, .ledger-disclosure__copy { display: grid; gap: 6px; min-width: 0; }
.ledger-disclosure__title { font-size: 15px; font-weight: 600; }
.ledger-disclosure__description { max-width: 65ch; color: var(--ledger-muted); font-size: 12px; line-height: 1.7; }
.ledger-disclosure__trigger-meta { display: flex; align-items: center; gap: 14px; color: var(--ledger-muted); }
.ledger-disclosure__meta { font-size: 12px; line-height: 1.6; text-align: right; }
.ledger-disclosure__state { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.ledger-disclosure__chevron-wrap { display: grid; place-items: center; width: 24px; height: 24px; flex: 0 0 auto; }
.ledger-disclosure__chevron { width: 7px; height: 7px; border-right: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor; transform: translateY(-2px) rotate(45deg); transition: transform .18s ease; }
.ledger-disclosure--open .ledger-disclosure__chevron { transform: translateY(2px) rotate(225deg); }
.ledger-disclosure__reveal { display: grid; grid-template-rows: 1fr; }
.ledger-disclosure__panel { min-height: 0; overflow: hidden; }
.ledger-disclosure__content { min-width: 0; margin: 0 20px; padding: 18px 0; border-top: 1px solid var(--ledger-line); overflow-wrap: anywhere; }
@media (max-width: 560px) { .ledger-disclosure__trigger { padding: 14px; gap: 10px; } .ledger-disclosure__trigger-meta { gap: 8px; max-width: 45%; } .ledger-disclosure__content { margin: 0 14px; } }

</style>
