<template>
  <section class="source-picker" aria-label="选择复习范围" :aria-busy="loading">
    <p v-if="!courseId">选择课程后，这里会带出可复习的资料。</p>
    <p v-else-if="loading" role="status">正在读取课程内容…</p>
    <div v-else-if="error" class="source-error" role="alert"><p>{{ error }}</p><button type="button" :disabled="disabled" @click="loadSources(true)">重新读取范围</button><RouterLink v-if="materialId" to="/materials">返回资料重新选择</RouterLink></div>
    <template v-else>
      <header>
        <div>
          <h3>{{ selectedCount ? `已选 ${[selectedMaterials.length ? `${selectedMaterials.length} 份资料` : '', selectedTasks.length ? `${selectedTasks.length} 条待办` : ''].filter(Boolean).join('、')}` : '选择这次要复习的内容' }}</h3>
          <p>{{ materialId && selectedMaterials.includes(materialId) ? '已带入刚才的资料，可以直接设置复习时间。' : selectedCount ? '已选好复习内容，可以直接设置时间，也可以调整范围。' : '勾选资料，也可以把未完成的待办一起安排。' }}</p>
        </div>
        <button type="button" :aria-expanded="expanded" :disabled="disabled" @click="expanded = !expanded">{{ expanded ? '收起范围' : '调整范围' }}</button>
      </header>
      <ul v-if="selectedCount && !expanded" class="selected-sources" aria-label="本次已选内容">
        <li v-for="item in selectedRows.slice(0, 3)" :key="item.navigation_key">{{ item.label }}</li>
        <li v-if="selectedCount > 3" class="more-sources">另有 {{ selectedCount - 3 }} 项，可展开查看</li>
      </ul>
      <p v-if="hasReferencePlan" class="reference-note">已选计划文件会作为复习内容重新安排，原文件的日期不会导入。</p>
      <p v-if="refreshNotice" class="reference-note" role="status">{{ refreshNotice }}</p>
      <div v-if="expanded" class="source-options">
        <div class="source-tools">
          <label v-if="materials.length + tasks.length > 6" class="source-search"><span class="sr-only">搜索复习资料和待办</span><input v-model="search" type="search" placeholder="搜索资料或待办" :disabled="disabled" /></label>
          <button type="button" :disabled="disabled || (!materials.some(item => item.recommended && item.available) && !tasks.some(item => item.available))" @click="selectRecommended">恢复推荐范围</button>
          <button type="button" :disabled="disabled || !selectedCount" @click="clearSelection">清空选择</button>
          <button type="button" :disabled="disabled" @click="loadSources(true)">刷新范围</button>
        </div>
        <div class="source-group">
          <h4>复习资料</h4>
          <p v-if="!materials.length">还没有资料。<RouterLink :to="{ path: '/materials', query: { action: 'upload', intent: 'plan', course_id: courseId, ...(examDate ? { exam_date: examDate } : {}), ...(dailyMinutes ? { daily_minutes: dailyMinutes } : {}) } }">添加这门课的资料</RouterLink></p>
          <p v-else-if="!visibleMaterials.length">没有匹配的资料。</p>
          <label v-for="item in visibleMaterials" :key="item.navigation_key" class="source-row" :class="{ 'is-disabled': !item.available }">
            <input v-model="selectedMaterials" type="checkbox" :value="item.source_id" :disabled="disabled || !item.available" />
            <span><strong>{{ item.label }}</strong><small>{{ item.material_type || '未分类' }} · {{ item.hint }}</small></span>
          </label>
        </div>
        <details class="source-group" :open="!materials.length || Boolean(selectedTasks.length) || Boolean(search)">
          <summary>同时安排待办 <span>{{ selectedTasks.length ? `${selectedTasks.length} 条已选` : '可选' }}</span></summary>
          <p v-if="!tasks.length">这门课没有未完成的待办。</p>
          <p v-else-if="!visibleTasks.length">没有匹配的待办。</p>
          <label v-for="item in visibleTasks" :key="item.navigation_key" class="source-row">
            <input v-model="selectedTasks" type="checkbox" :value="item.source_id" :disabled="disabled || !item.available" />
            <span><strong>{{ item.label }}</strong><small>{{ item.due_at ? `截止 ${formatDateTime(item.due_at)}` : item.hint }}</small></span>
          </label>
        </details>
      </div>
      <p v-if="!selectedCount" class="selection-summary" role="status">至少选择一份资料或一条待办，才能生成计划。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { studyPlansApi } from '../api'
import { formatDateTime } from '../utils/format'
const props = defineProps({ courseId: { type: Number, default: null }, materialId: { type: Number, default: null }, materialKey: { type: String, default: '' }, examDate: { type: String, default: '' }, dailyMinutes: { type: Number, default: null }, disabled: Boolean })
const emit = defineEmits(['change'])
const loading = ref(false)
const error = ref('')
const materials = ref([])
const tasks = ref([])
const selectedMaterials = ref([])
const selectedTasks = ref([])
const expanded = ref(false)
const search = ref('')
const refreshNotice = ref('')
const selectedCount = computed(() => selectedMaterials.value.length + selectedTasks.value.length)
const selectedRows = computed(() => [...materials.value.filter(item => selectedMaterials.value.includes(item.source_id)), ...tasks.value.filter(item => selectedTasks.value.includes(item.source_id))])
const hasReferencePlan = computed(() => selectedRows.value.some(item => item.content_kind === 'review_outline'))
const matchesSearch = (item) => !search.value.trim() || String(item.label).toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase())
const visibleMaterials = computed(() => materials.value.filter(matchesSearch))
const visibleTasks = computed(() => tasks.value.filter(matchesSearch))
let requestId = 0

function selection(rows, ids) {
  return rows.filter(row => row.available && ids.includes(row.source_id)).map(({ source_id, navigation_key, revision }) => ({ source_id, navigation_key, revision }))
}
function publish() {
  emit('change', { ready: !loading.value && !error.value && Boolean(props.courseId), courseId: props.courseId,
    material_sources: selection(materials.value, selectedMaterials.value), task_sources: selection(tasks.value, selectedTasks.value) })
}
function selectRecommended() {
  selectedMaterials.value = materials.value.filter(item => item.recommended && item.available).map(item => item.source_id)
  selectedTasks.value = selectedMaterials.value.length ? [] : tasks.value.filter(item => item.available).map(item => item.source_id)
}
function clearSelection() { selectedMaterials.value = []; selectedTasks.value = [] }
async function loadSources(preserveSelection = false) {
  const request = ++requestId
  const previousMaterials = selection(materials.value, selectedMaterials.value)
  const previousTasks = selection(tasks.value, selectedTasks.value)
  loading.value = true
  error.value = ''; refreshNotice.value = ''
  materials.value = []; tasks.value = []; selectedMaterials.value = []; selectedTasks.value = []
  publish()
  try {
    if (!props.courseId) return
    const result = await studyPlansApi.sources(props.courseId)
    if (request !== requestId) return
    if (result.course_id !== props.courseId || !Array.isArray(result.materials) || !Array.isArray(result.tasks)) throw new Error('无法确认课程范围，请刷新重试')
    materials.value = result.materials; tasks.value = result.tasks
    if (props.materialId && !materials.value.some(item => item.source_id === props.materialId && item.navigation_key === props.materialKey && item.available)) throw new Error('原来的资料已变更、移出课程或不可读取，请从资料页重新选择。')
    if (preserveSelection) {
      const retainedIds = (rows, previous) => rows.filter(item => item.available && previous.some(ref => ref.source_id === item.source_id && ref.navigation_key === item.navigation_key)).map(item => item.source_id)
      selectedMaterials.value = retainedIds(materials.value, previousMaterials)
      selectedTasks.value = retainedIds(tasks.value, previousTasks)
      refreshNotice.value = '范围已刷新，请核对当前选择；已移除的内容不会再加入。'
    } else if (props.materialId) selectedMaterials.value = [props.materialId]
    else selectRecommended()
    expanded.value = !selectedCount.value || (preserveSelection && expanded.value)
  } catch (err) { if (request === requestId) error.value = err.message }
  finally { if (request === requestId) { loading.value = false; publish() } }
}
watch(() => [props.courseId, props.materialId, props.materialKey], () => { search.value = ''; expanded.value = false; loadSources() }, { immediate: true })
watch([selectedMaterials, selectedTasks], publish, { deep: true })
defineExpose({ refreshSources: () => loadSources(true) })
</script>

<style scoped>
.source-picker { width: 100%; min-width: 0; padding: 16px; border: 1px solid var(--ledger-line); border-radius: 10px; background: var(--ledger-paper); box-sizing: border-box; }
header { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
h3, h4 { margin: 0; color: var(--ledger-ink); font-size: 14px; } h4 { margin-bottom: 8px; }
p { margin: 5px 0 0; line-height: 1.65; color: var(--ledger-muted); font-size: 13px; }
button { flex-shrink: 0; min-height: 36px; border: 0; background: transparent; color: var(--ledger-link); cursor: pointer; padding: 6px 8px; font: inherit; font-size: 13px; }
button:disabled { opacity: .5; cursor: default; }
button:focus-visible, input:focus-visible, summary:focus-visible, a:focus-visible { outline: 2px solid var(--ledger-indigo); outline-offset: 3px; }
.selected-sources { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; padding: 0; margin: 12px 0 0; }
.selected-sources li { max-width: 100%; padding: 5px 9px; background: #f1f7f3; border-radius: 4px; color: var(--ledger-ink); font-size: 13px; overflow-wrap: anywhere; }
.selected-sources .more-sources { background: transparent; color: var(--ledger-muted); }
.source-tools { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-top: 12px; }
.source-search { flex: 1 1 190px; min-width: 0; }
.source-search input { width: 100%; min-height: 38px; padding: 7px 10px; border: 1px solid var(--ledger-line); border-radius: 5px; font: inherit; box-sizing: border-box; }
.source-group { border-top: 1px solid var(--ledger-line); padding-top: 12px; margin-top: 12px; max-height: 300px; overflow: auto; }
summary span { font-size: 12px; font-weight: 400; color: var(--ledger-muted); margin-left: 8px; }
summary { cursor: pointer; padding: 4px 0 10px; font-size: 14px; font-weight: 600; }
.source-row { display: flex; gap: 10px; padding: 10px 8px; border-radius: 6px; cursor: pointer; align-items: start; }
.source-row:has(input:checked) { background: #f1f7f3; }
.source-row:hover { background: var(--ledger-canvas); }
.source-row input { margin-top: 4px; width: 17px; height: 17px; flex-shrink: 0; accent-color: var(--ledger-indigo); }
strong { font-weight: 500; font-size: 14px; overflow-wrap: anywhere; } small { display: block; margin-top: 4px; font-size: 12px; color: var(--ledger-muted); line-height: 1.6; }
.is-disabled { opacity: .6; cursor: default; } .source-error p { color: #a12f25; }
.reference-note { margin-top: 10px; color: #80582e; }
.selection-summary { margin-top: 12px; }
@media (max-width: 600px) { .source-picker { padding: 12px; } header { flex-wrap: wrap; gap: 5px; } }
</style>
