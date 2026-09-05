<template>
  <section
    class="ledger-disclosure"
    :class="{ 'ledger-disclosure--open': props.open }"
    :data-section-id="props.sectionId"
  >
    <span class="ledger-disclosure__spine" aria-hidden="true"></span>

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
        <span class="ledger-disclosure__archive-mark" aria-hidden="true">
          <span class="ledger-disclosure__archive-lines"></span>
        </span>
        <span class="ledger-disclosure__copy">
          <span :id="titleId" class="ledger-disclosure__title">{{ props.title }}</span>
          <span v-if="props.description" class="ledger-disclosure__description">{{ props.description }}</span>
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

    <div
      v-if="props.open"
      :id="panelId"
      class="ledger-disclosure__panel"
      role="region"
      :aria-labelledby="titleId"
    >
      <div class="ledger-disclosure__content">
        <slot />
      </div>
    </div>
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
.ledger-disclosure {
  position: relative;
  min-width: 0;
  margin-top: 20px;
  color: var(--ledger-ink, #1e2a44);
  background: var(--ledger-paper, #fffefb);
  border: 1px solid var(--ledger-line, #d9e0ea);
  border-left: 3px solid var(--ledger-indigo, #5964ed);
  border-radius: 5px;
  box-shadow: 0 5px 16px rgba(30, 42, 68, .05);
}

.ledger-disclosure::before {
  position: absolute;
  top: -5px;
  left: 17px;
  width: 82px;
  height: 5px;
  background: #f4ecdc;
  border: 1px solid #d8cdbb;
  border-bottom: 0;
  content: '';
}

.ledger-disclosure__spine {
  position: absolute;
  top: 0;
  bottom: 0;
  left: -3px;
  width: 3px;
  background: repeating-linear-gradient(
    to bottom,
    var(--ledger-indigo, #5964ed) 0,
    var(--ledger-indigo, #5964ed) 12px,
    #8891f2 12px,
    #8891f2 13px,
    var(--ledger-indigo, #5964ed) 13px,
    var(--ledger-indigo, #5964ed) 24px
  );
  pointer-events: none;
}

.ledger-disclosure__trigger {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 42%);
  align-items: center;
  gap: 18px;
  width: 100%;
  min-height: 68px;
  padding: 13px 16px 13px 18px;
  color: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-bottom: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  font: inherit;
  line-height: 1.45;
}

.ledger-disclosure--open .ledger-disclosure__trigger {
  border-bottom-color: #ece5d8;
}

.ledger-disclosure__trigger:hover {
  background: #fcfaf5;
}

.ledger-disclosure__trigger:focus-visible {
  position: relative;
  z-index: 1;
  outline: 3px solid rgba(89, 100, 237, .58);
  outline-offset: 2px;
}

.ledger-disclosure__trigger-main,
.ledger-disclosure__trigger-meta {
  display: flex;
  min-width: 0;
  align-items: center;
}

.ledger-disclosure__trigger-main {
  gap: 11px;
}

.ledger-disclosure__archive-mark {
  display: grid;
  flex: 0 0 29px;
  place-items: center;
  width: 29px;
  height: 35px;
  padding: 6px 5px;
  background: #f7f1e6;
  border: 1px solid #d8cdbb;
  border-top: 2px solid #b59661;
  border-radius: 2px;
  transform: rotate(-1deg);
}

.ledger-disclosure__archive-lines,
.ledger-disclosure__archive-lines::before,
.ledger-disclosure__archive-lines::after {
  display: block;
  width: 100%;
  height: 1px;
  background: #b8a480;
  content: '';
}

.ledger-disclosure__archive-lines::before,
.ledger-disclosure__archive-lines::after {
  position: relative;
}

.ledger-disclosure__archive-lines::before {
  top: -5px;
}

.ledger-disclosure__archive-lines::after {
  top: 4px;
}

.ledger-disclosure__copy {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.ledger-disclosure__title,
.ledger-disclosure__description,
.ledger-disclosure__meta,
.ledger-disclosure__state {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.ledger-disclosure__title {
  color: #2e3b54;
  font-size: 15px;
  font-weight: 750;
  line-height: 1.4;
}

.ledger-disclosure__description {
  color: var(--ledger-muted, #667085);
  font-size: 13px;
  line-height: 1.6;
}

.ledger-disclosure__trigger-meta {
  justify-content: flex-end;
  gap: 11px;
  color: var(--ledger-muted, #667085);
}

.ledger-disclosure__meta {
  color: #8d713b;
  font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif;
  font-size: 12px;
  letter-spacing: .04em;
  line-height: 1.5;
  text-align: right;
}

.ledger-disclosure__state {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.ledger-disclosure__chevron-wrap {
  display: grid;
  flex: 0 0 34px;
  place-items: center;
  width: 34px;
  height: 34px;
  color: var(--ledger-indigo, #5964ed);
  border: 1px solid #d9d7ff;
  border-radius: 3px;
}

.ledger-disclosure__chevron {
  display: block;
  width: 9px;
  height: 9px;
  border-right: 2px solid currentColor;
  border-bottom: 2px solid currentColor;
  transform: translateY(-2px) rotate(45deg);
  transition: transform .18s ease;
}

.ledger-disclosure--open .ledger-disclosure__chevron {
  transform: translateY(2px) rotate(225deg);
}

.ledger-disclosure__panel {
  min-width: 0;
  padding: 0 18px 18px 58px;
  background:
    linear-gradient(to right, rgba(216, 205, 187, .18) 0, rgba(216, 205, 187, .18) 1px, transparent 1px) 30px 0 / 1px 100% no-repeat,
    var(--ledger-paper, #fffefb);
  border-radius: 0 0 4px 4px;
}

.ledger-disclosure__content {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

@media (max-width: 560px) {
  .ledger-disclosure__trigger {
    grid-template-columns: minmax(0, 1fr);
    gap: 9px;
    min-height: 64px;
    padding: 12px;
  }

  .ledger-disclosure__trigger-meta {
    justify-content: space-between;
    width: 100%;
    padding-left: 40px;
  }

  .ledger-disclosure__meta {
    flex: 1 1 auto;
    text-align: left;
  }

  .ledger-disclosure__panel {
    padding: 0 12px 14px 16px;
    background: var(--ledger-paper, #fffefb);
  }
}

@media (prefers-reduced-motion: reduce) {
  .ledger-disclosure__chevron {
    transition: none;
  }
}
</style>
