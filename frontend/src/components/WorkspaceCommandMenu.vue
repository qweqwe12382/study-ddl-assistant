<template>
  <el-dialog :model-value="open" title="快捷入口" class="command-dialog" width="540px" append-to-body :show-close="false" @update:model-value="emit('update:open', $event)" @open="resetSearch" @opened="focusSearch" @closed="finishClose">
    <div class="command-search">
      <el-icon aria-hidden="true"><Search /></el-icon>
      <input ref="searchInput" v-model="query" type="search" placeholder="想做什么？" aria-label="搜索页面和快捷操作" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="workspace-command-results" :aria-activedescendant="results.length ? `command-${results[selectedIndex]?.id}` : undefined" autocomplete="off" @keydown="handleKey" />
      <button type="button" class="command-close" aria-label="关闭快捷入口" @click="emit('update:open', false)"><el-icon aria-hidden="true"><Close /></el-icon></button>
    </div>
    <p class="sr-only" role="status">找到 {{ results.length }} 个入口</p>
    <ul id="workspace-command-results" role="listbox" aria-label="页面和快捷操作" class="command-results">
      <li v-for="(item, index) in results" :id="`command-${item.id}`" :key="item.id" role="option" :aria-selected="selectedIndex === index" class="command-result" :class="{ 'is-selected': selectedIndex === index }" @mouseenter="selectedIndex = index">
        <button type="button" tabindex="-1" @click="choose(item)">
          <el-icon aria-hidden="true"><component :is="icons[item.icon] || item.icon" /></el-icon>
          <span>{{ item.label }}</span><small>{{ item.group }}</small>
          <el-icon class="command-enter" aria-hidden="true"><Right /></el-icon>
        </button>
      </li>
    </ul>
    <div v-if="!results.length" class="command-empty"><strong>没有找到“{{ query }}”</strong><p>试试“任务”“通知”或“专注”。</p><button type="button" @click="query = ''; focusSearch()">查看全部入口</button></div>
    <p v-if="navigationError" class="command-error" role="alert">{{ navigationError }}</p>
    <div class="command-footer"><span><kbd>↑</kbd><kbd>↓</kbd> 选择</span><span><kbd>Enter</kbd> 打开</span><span><kbd>Esc</kbd> 关闭</span></div>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElDialog } from 'element-plus'
import { Calendar, Close, Document, EditPen, Right, Search, Timer } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { QUICK_COMMANDS, filterWorkspaceCommands } from '../utils/workspaceCommands'

const props = defineProps({ open: Boolean, navigation: { type: Array, default: () => [] } })
const emit = defineEmits(['update:open', 'closed'])
const router = useRouter()
const icons = { Calendar, Document, EditPen, Timer }
const query = ref('')
const selectedIndex = ref(0)
const searchInput = ref(null)
const navigationError = ref('')
let pendingCommand = null
const commands = computed(() => [...QUICK_COMMANDS, ...props.navigation.map(item => ({ id: item.path.slice(1), label: item.label, keywords: `${item.description} ${item.path}`, to: item.path, icon: item.icon, group: '页面' }))])
const results = computed(() => filterWorkspaceCommands(commands.value, query.value))
watch(query, () => { selectedIndex.value = 0 })
function resetSearch() { query.value = ''; selectedIndex.value = 0; navigationError.value = ''; pendingCommand = null }
function focusSearch() { searchInput.value?.focus() }
async function handleKey(event) {
  if (event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter') { event.preventDefault(); choose(results.value[selectedIndex.value]); return }
  if (!['ArrowDown', 'ArrowUp'].includes(event.key) || !results.value.length) return
  event.preventDefault()
  selectedIndex.value = (selectedIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + results.value.length) % results.value.length
  await nextTick()
  document.getElementById(`command-${results.value[selectedIndex.value]?.id}`)?.scrollIntoView({ block: 'nearest' })
}
function choose(item) {
  if (!item || pendingCommand) return
  pendingCommand = item
  emit('update:open', false)
}
async function finishClose() {
  const command = pendingCommand
  pendingCommand = null
  // Close the modal and restore its focus before opening a destination dialog.
  emit('closed', Boolean(command))
  if (!command) return
  try {
    await router.push(command.to)
  } catch {
    emit('update:open', true)
    await nextTick()
    navigationError.value = '页面暂时没有打开，请再试一次。'
  }
}
</script>

<style>
.command-dialog { padding: 0; border-radius: 16px; overflow: hidden; box-shadow: 0 24px 72px #20392f26; }
.command-dialog .el-dialog__header { margin: 0; padding: 0; }
.command-dialog .el-dialog__title { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.command-dialog .el-dialog__body { padding: 0; }
.command-search { display: flex; align-items: center; gap: 12px; padding: 16px 18px; border-bottom: 1px solid var(--ledger-line); }
.command-search > .el-icon { font-size: 20px; color: var(--ledger-muted); }
.command-search input { flex: 1; min-width: 0; height: 40px; padding: 0; color: var(--ledger-ink); border: 0; background: transparent; outline: none; font-size: 16px; }
.command-search:focus-within { box-shadow: inset 0 -2px var(--ledger-primary); }
.command-close { display: grid; place-items: center; flex-shrink: 0; width: 44px; height: 44px; background: transparent; border: 0; border-radius: 8px; color: var(--ledger-muted); cursor: pointer; }
.command-results { max-height: min(420px, 52dvh); overflow: auto; margin: 0; padding: 8px; list-style: none; }
.command-result button { display: flex; width: 100%; min-height: 46px; align-items: center; gap: 12px; padding: 10px 12px; border: 0; border-radius: 8px; color: var(--ledger-ink); background: transparent; text-align: left; cursor: pointer; }
.command-result.is-selected button { background: #edf4ef; color: var(--ledger-link); }
.command-result .el-icon { font-size: 18px; }
.command-result span { flex: 1; min-width: 0; font-size: 14px; }
.command-result small { color: var(--ledger-muted); font-size: 11px; }
.command-enter { opacity: 0; }
.command-result.is-selected .command-enter { opacity: 1; }
.command-footer { display: flex; gap: 16px; padding: 12px 20px; background: var(--ledger-canvas); color: var(--ledger-muted); font-size: 11px; }
.command-footer kbd { margin-right: 3px; font: inherit; }
.command-empty { padding: 32px 24px; text-align: center; overflow-wrap: anywhere; }
.command-empty p { color: var(--ledger-muted); font-size: 13px; }
.command-empty button { min-height: 44px; color: var(--ledger-link); background: transparent; border: 0; cursor: pointer; }
.command-error { padding: 0 20px; color: var(--ledger-coral); }
@media (max-width: 560px) { .command-dialog { margin-top: 8vh !important; } .command-footer { display: none; } }
</style>
