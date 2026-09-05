<template>
  <section v-if="visible" class="edit-conflict-card" role="status" aria-live="polite">
    <div>
      <strong>{{ title }}</strong>
      <p>{{ message }}</p>
    </div>
    <dl v-if="latestFields.length" class="edit-conflict-card__latest" aria-label="最新内容">
      <div v-for="field in latestFields" :key="field.label">
        <dt>{{ field.label }}</dt><dd>{{ field.value }}</dd>
      </div>
    </dl>
    <div class="edit-conflict-card__actions">
      <button type="button" @click="$emit('view-latest')">查看最新内容</button>
      <button type="button" @click="$emit('discard')">放弃我的修改并重读</button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  latestFields: { type: Array, default: () => [] },
  title: { type: String, default: '这份内容刚被其他页面更新了' },
  message: { type: String, default: '本次未覆盖新内容，当前草稿仍保留。先查看最新内容，再决定是否放弃这次修改。' },
})
defineEmits(['view-latest', 'discard'])
</script>

<style scoped>
.edit-conflict-card { display: grid; gap: 10px; margin: 0 0 14px; padding: 12px 14px; color: var(--ledger-ink, #1e2a44); background: #fff8ed; border: 1px solid #efd0ab; border-left: 3px solid var(--ledger-amber, #c9822e); border-radius: 6px; }
.edit-conflict-card strong { font-size: 14px; line-height: 1.5; }
.edit-conflict-card p { margin: 3px 0 0; color: var(--ledger-muted, #667085); font-size: 13px; line-height: 1.55; }
.edit-conflict-card__actions { display: flex; flex-wrap: wrap; gap: 8px; }
.edit-conflict-card__latest { display: grid; gap: 7px; max-height: 190px; margin: 0; padding: 10px; overflow: auto; background: rgba(255, 255, 255, .72); border: 1px solid #efd0ab; border-radius: 4px; }
.edit-conflict-card__latest > div { display: grid; gap: 2px; }
.edit-conflict-card__latest dt { color: var(--ledger-muted, #667085); font-size: 11px; font-weight: 700; }
.edit-conflict-card__latest dd { margin: 0; color: var(--ledger-ink, #1e2a44); font-size: 13px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
.edit-conflict-card button { min-height: 44px; padding: 8px 10px; color: #3f54bd; background: #fff; border: 1px solid #b9c8f3; border-radius: 5px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.edit-conflict-card button:focus-visible { outline: 3px solid rgba(89, 100, 237, .35); outline-offset: 2px; }
@media (max-width: 560px) { .edit-conflict-card__actions { display: grid; grid-template-columns: 1fr; } .edit-conflict-card button { width: 100%; } }
</style>
