<template>
  <div class="tasks-page">
    <div class="page-intro">
      <div>
        <h1>截止任务</h1>
        <p>把课程截止日期变成可执行的清单；完成后补充反馈，安排会逐步贴合实际用时。</p>
      </div>
      <div class="page-actions task-page-actions">
        <el-button class="task-create-action" type="primary" @click="openCreate">新增任务</el-button>
        <div v-if="isDetailedView" class="task-export-actions" role="group" aria-label="导出任务清单">
          <el-button @click="downloadFile(exportsApi.tasksCsvUrl())">导出 CSV</el-button>
          <el-button @click="downloadFile(exportsApi.tasksCalendarUrl())">导出待办日历</el-button>
        </div>
      </div>
    </div>

    <div v-if="error" class="task-load-error mb-18" role="alert">
      <el-alert :title="error" type="error" show-icon :closable="false" />
      <el-button type="primary" plain :loading="loading" @click="loadData">重新读取任务</el-button>
    </div>
    <EditConflictCard :visible="Boolean(taskConflict) && !dialogVisible && !completionDialogVisible" :title="taskConflictTitle" :message="taskConflictMessage" :latest-fields="taskConflict?.latestFields || []" @view-latest="viewLatestTask" @discard="discardTaskDraft" />
    <div v-if="deepLinkLabel" class="task-deep-link mb-18" role="status">
      <el-alert :title="deepLinkEmpty && !taskNavigationMismatch ? `${deepLinkLabel}；当前筛选无结果。` : deepLinkLabel" type="info" show-icon :closable="false" />
      <el-button v-if="deepLinkEmpty" link type="primary" @click="clearRouteFilters">清除定位筛选</el-button>
    </div>
    <div v-if="loading" class="sr-only" role="status" aria-live="polite">正在加载任务列表…</div>

    <TaskAgenda
      v-if="isConciseView"
      class="task-agenda-section"
      :state="taskDataState"
      :tasks="agendaTasks"
      :busy-task-ids="completionBusyTaskIds"
      :busy-material-ids="materialNavigationBusyIds"
      @complete-task="completeTask"
      @feedback-task="openCompletionFeedback"
      @edit-task="openEdit"
      @open-material="openMaterialSource"
      @show-all="showDetailedTaskList"
    />

    <section v-if="isDetailedView" class="task-summary" aria-labelledby="task-summary-heading" :aria-busy="!taskDataReady">
      <div class="task-summary-heading">
        <div>
          <p class="task-summary-kicker">执行状态 / LIVE LEDGER</p>
          <h2 id="task-summary-heading">今天先看这几项</h2>
        </div>
        <span class="task-summary-state" :class="`task-summary-state--${taskDataState}`" role="status" aria-live="polite">
          {{ taskSummaryStateLabel }}
        </span>
      </div>
      <dl class="task-summary-grid">
        <div class="task-summary-item task-summary-item--action">
          <dt>待行动</dt>
          <dd v-if="taskDataReady" class="task-summary-value">{{ taskSummary.pending }}</dd>
          <dd v-else class="task-summary-value task-summary-value--pending" aria-label="数据尚未就绪">—</dd>
          <p>全部未完成</p>
        </div>
        <div class="task-summary-item task-summary-item--today">
          <dt>今日截止</dt>
          <dd v-if="taskDataReady" class="task-summary-value">{{ taskSummary.dueToday }}</dd>
          <dd v-else class="task-summary-value task-summary-value--pending" aria-label="数据尚未就绪">—</dd>
          <p>按本地日期 · 未完成</p>
        </div>
        <div class="task-summary-item task-summary-item--overdue">
          <dt>已逾期</dt>
          <dd v-if="taskDataReady" class="task-summary-value">{{ taskSummary.overdue }}</dd>
          <dd v-else class="task-summary-value task-summary-value--pending" aria-label="数据尚未就绪">—</dd>
          <p>截止已过 · 未完成</p>
        </div>
        <div class="task-summary-item task-summary-item--completed">
          <dt>已完成</dt>
          <dd v-if="taskDataReady" class="task-summary-value">{{ taskSummary.completed }}</dd>
          <dd v-else class="task-summary-value task-summary-value--pending" aria-label="数据尚未就绪">—</dd>
          <p>状态已标记完成</p>
        </div>
      </dl>
    </section>

    <el-card v-if="isDetailedView" class="table-card" shadow="never" v-loading="loading" :aria-busy="loading" aria-labelledby="task-list-heading">
      <div class="table-toolbar">
        <div class="task-table-heading">
          <p class="task-table-kicker">行动列表</p>
          <h2 id="task-list-heading" tabindex="-1">
            任务清单
            <span v-if="taskDataReady" class="task-count">{{ filteredTasks.length }}<span v-if="hasActiveFilters"> / {{ tasks.length }}</span></span>
            <span v-else class="task-count task-count--state">{{ taskCountStateLabel }}</span>
          </h2>
          <p class="task-table-note">先处理临近截止项；完成后可补充实际用时和难度。</p>
        </div>
        <div class="toolbar-actions task-toolbar-actions" role="group" aria-label="筛选任务清单">
          <span class="task-filter-label">筛选</span>
          <el-select v-model="statusFilter" clearable placeholder="全部状态" aria-label="按任务状态筛选" style="width: 140px">
            <el-option label="未开始" value="not_started" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已逾期" value="overdue" />
          </el-select>
          <el-input v-model="keyword" placeholder="搜索任务名称" clearable aria-label="搜索任务名称" style="width: 180px" />
          <el-button v-if="hasActiveFilters" link aria-label="清除任务筛选条件" @click="resetFilters">清除筛选</el-button>
        </div>
      </div>
      <div class="table-wrap">
        <el-table :data="filteredTasks" :empty-text="tableEmptyText" :row-class-name="taskRowClassName">
          <el-table-column label="任务名称" min-width="240">
            <template #default="{ row }">
              <div class="row-title task-table-name">{{ row.name }}</div>
              <div class="row-meta task-table-meta">{{ row.task_type || '未分类' }} · 优先级 {{ row.priority }}</div>
            </template>
          </el-table-column>
          <el-table-column label="所属课程" width="150">
            <template #default="{ row }"><div class="task-table-course">{{ courseName(row.course_id) }}</div></template>
          </el-table-column>
          <el-table-column label="截止时间" width="170">
            <template #default="{ row }">
              <span :class="{ overdue: isOverdue(row) }">{{ formatDateTime(row.due_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="工作量" min-width="190">
            <template #default="{ row }">
              <span :class="{ muted: !hasWorkload(row) }">{{ workloadLabel(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }"><el-tag :type="displayStatusType(row)" size="small">{{ displayStatus(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="来源" min-width="150">
            <template #default="{ row }">
              <button
                v-if="taskSourceContext(row).state === 'available'"
                type="button"
                class="task-table-source-action"
                :disabled="isMaterialNavigationLoading(row)"
                :aria-label="`${isMaterialNavigationLoading(row) ? '正在打开资料' : '打开资料'}：${taskSourceContext(row).label}`"
                @click="openMaterialSource(row)"
              >
                {{ isMaterialNavigationLoading(row) ? '正在打开…' : taskSourceContext(row).label }}
              </button>
              <span v-else class="task-table-source muted">{{ taskSourceContext(row).state === 'deleted' ? `已删除：${taskSourceContext(row).label}` : taskSourceContext(row).state === 'identity_missing' ? `身份待确认：${taskSourceContext(row).label}` : '未关联' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }">
              <div class="task-row-actions">
                <div v-if="row.status !== 'completed'" class="task-row-actions-primary" role="group" :aria-label="`完成操作：${row.name}`">
                  <el-button
                    type="success"
                    plain
                    :loading="isCompletionLoading(row.id)"
                    :disabled="hasAnyCompletionLoading()"
                    :aria-label="`完成任务：${row.name}`"
                    @click="completeTask(row)"
                  >
                    完成
                  </el-button>
                  <el-button
                    type="primary"
                    link
                    :disabled="hasAnyCompletionLoading()"
                    :aria-label="`完成任务并补充反馈：${row.name}`"
                    @click="openCompletionFeedback(row)"
                  >
                    完成并补充反馈
                  </el-button>
                </div>
                <div v-else class="task-row-actions-primary" role="group" :aria-label="`完成反馈：${row.name}`">
                  <el-button
                    type="primary"
                    link
                    :disabled="hasAnyCompletionLoading()"
                    :aria-label="`补充或更新完成反馈：${row.name}`"
                    @click="openCompletionFeedback(row)"
                  >
                  更新完成反馈
                  </el-button>
                </div>
                <span v-if="row.status !== 'completed'" class="task-action-divider" aria-hidden="true"></span>
                <div class="task-row-actions-secondary" role="group" :aria-label="`其他操作：${row.name}`">
                  <el-button link type="primary" :aria-label="`编辑任务：${row.name}`" @click="openEdit(row)">编辑</el-button>
                  <el-button link type="danger" :aria-label="`删除任务：${row.name}`" @click="removeTask(row)">删除</el-button>
                </div>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑任务' : '新增任务'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="92px" class="dialog-form">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.name" placeholder="例如：完成实验一报告" />
        </el-form-item>
        <el-form-item label="所属课程">
          <el-select v-model="form.course_id" clearable placeholder="选择课程" style="width: 100%">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务类型">
            <el-input v-model="form.task_type" placeholder="例如：作业、实验、考试或报告" />
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker
            v-model="form.due_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择截止时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="预计用时">
          <div class="duration-fields">
            <el-input-number v-model="durationForm.estimated_hours" :min="0" :max="168" controls-position="right" placeholder="小时" />
            <span>小时</span>
            <el-input-number v-model="durationForm.estimated_remainder_minutes" :min="0" :max="59" controls-position="right" placeholder="分钟" />
            <span>分钟</span>
          </div>
          <div class="field-hint">不确定时可以留空；需要补充时，容量判断会明确提示。</div>
        </el-form-item>
        <el-form-item label="剩余用时">
          <div class="duration-fields">
            <el-input-number v-model="durationForm.remaining_hours" :min="0" :max="168" controls-position="right" placeholder="小时" />
            <span>小时</span>
            <el-input-number v-model="durationForm.remaining_remainder_minutes" :min="0" :max="59" controls-position="right" placeholder="分钟" />
            <span>分钟</span>
          </div>
        </el-form-item>
        <el-form-item label="优先级">
          <el-rate v-model="form.priority" :max="5" show-score text-color="#ff9900" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="未开始" value="not_started" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已逾期" value="overdue" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源资料">
          <el-select v-model="form.material_id" clearable placeholder="关联资料" style="width: 100%">
            <el-option v-for="material in materials" :key="material.id" :label="material.original_filename" :value="material.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="补充任务说明（可选）" />
        </el-form-item>
      </el-form>
      <EditConflictCard :visible="Boolean(taskConflict) && dialogVisible" :title="taskConflictTitle" :message="taskConflictMessage" :latest-fields="taskConflict?.latestFields || []" @view-latest="viewLatestTask" @discard="discardTaskDraft" />
      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" :disabled="saving" @click="saveTask">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="completionDialogVisible" :title="completionDialogTitle" width="440px" destroy-on-close>
      <p class="completion-dialog-help">
        {{ completionDialogHelp }}
      </p>
      <el-form label-width="88px" class="dialog-form">
        <el-form-item label="实际用时">
          <div class="duration-fields">
            <el-input-number
              v-model="completionActualMinutes"
              :min="15"
              :max="10080"
              :step="15"
              controls-position="right"
              placeholder="可留空"
            />
            <span>分钟</span>
          </div>
          <div class="field-hint">填写 15 到 10080 分钟的整数，建议按实际投入时间填写。</div>
        </el-form-item>
        <el-form-item label="完成难度">
          <el-rate v-model="completionDifficulty" :max="5" show-score clearable text-color="#ff9900" />
          <div class="field-hint">1 星较轻松，5 星明显超出原先预计。</div>
        </el-form-item>
      </el-form>
      <EditConflictCard :visible="Boolean(taskConflict) && completionDialogVisible" :title="taskConflictTitle" :message="taskConflictMessage" :latest-fields="taskConflict?.latestFields || []" @view-latest="viewLatestTask" @discard="discardTaskDraft" />
      <template #footer>
        <div class="form-actions">
          <el-button :disabled="isCompletionLoading(completionTask?.id)" @click="closeCompletionFeedback">取消</el-button>
          <el-button
            type="primary"
            :loading="isCompletionLoading(completionTask?.id)"
            :disabled="!canSubmitCompletionFeedback || isCompletionLoading(completionTask?.id)"
            @click="submitCompletionFeedback"
          >
            {{ completionSubmitLabel }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElAlert,
  ElCard,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRate,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus'

import { agentApi, coursesApi, exportsApi, materialsApi, tasksApi } from '../api'
import TaskAgenda from '../components/TaskAgenda.vue'
import EditConflictCard from '../components/EditConflictCard.vue'
import { useViewMode } from '../composables/useViewMode'
import { downloadFile } from '../utils/download'
import { formatDateTime, isOverdue, statusLabel, statusType } from '../utils/format'
import { navigationKey, navigationSourceCacheKey, validatedMaterialTarget } from '../utils/materialSourceNavigation'
import { editBaseline, editRequestConfig, isEditConflict, isEntityGone, preconditionMessage } from '../utils/editPrecondition'

const loading = ref(false)
const route = useRoute()
const router = useRouter()
const { isConciseView, isDetailedView, setViewMode } = useViewMode()
const saving = ref(false)
const error = ref('')
const keyword = ref('')
const statusFilter = ref('')
const dialogVisible = ref(false)
const editingId = ref(null)
const editingBaseline = ref(null)
const taskConflict = ref(null)
const taskConflictTitle = computed(() => taskConflict.value?.state === 'missing'
  ? '这条任务已不存在'
  : taskConflict.value?.state === 'replacement'
    ? '这个编号已换成另一条任务'
    : '这份内容刚被其他页面更新了')
const taskConflictMessage = computed(() => taskConflict.value?.state === 'missing'
  ? '本次没有覆盖内容，当前草稿仍保留。可查看最新状态，或放弃草稿后重新选择。'
  : taskConflict.value?.state === 'replacement'
    ? '本次没有覆盖新任务，当前草稿仍保留。请放弃草稿后重新选择任务。'
    : '本次未覆盖新内容，当前草稿仍保留。先查看最新内容，再决定是否放弃这次修改。')
const courses = ref([])
const materials = ref([])
const tasks = ref([])
const taskDataState = ref('pending')
const form = reactive(emptyForm())
const durationForm = reactive(emptyDurationForm())
const completionDialogVisible = ref(false)
const completionTask = ref(null)
const completionActualMinutes = ref(null)
const completionDifficulty = ref(null)
const completionLoading = ref({})
const materialNavigationLoading = ref({})
const completionIdempotencyKeys = new Map()
const hasActiveFilters = computed(() => Boolean(keyword.value.trim() || statusFilter.value))
const taskDataReady = computed(() => taskDataState.value === 'ready')
const hasRouteFilters = computed(() => Boolean(
  routeFilters.value.taskId
  || routeFilters.value.courseId
  || routeFilters.value.materialId
  || routeFilters.value.date
  || routeFilters.value.view,
))
const deepLinkEmpty = computed(() => taskDataReady.value && hasRouteFilters.value && routeScopedTasks.value.length === 0)
const completionIsUpdate = computed(() => completionTask.value?.status === 'completed')
const completionDialogTitle = computed(() => completionIsUpdate.value ? '补充或更新完成反馈' : '完成任务并补充反馈')
const completionDialogHelp = computed(() => completionIsUpdate.value
  ? '请至少更新实际用时或完成难度。提交后会覆盖已保存的对应反馈，并用于校准估时。'
  : '可选填写实际用时和难度，帮助系统逐步校准这门课的估时。留空也可以直接完成。')
const completionSubmitLabel = computed(() => completionIsUpdate.value ? '保存完成反馈' : '完成任务')
const hasCompletionDifficulty = computed(() => {
  const value = Number(completionDifficulty.value)
  return Number.isInteger(value) && value >= 1 && value <= 5
})
const canSubmitCompletionFeedback = computed(() => {
  if (!completionTask.value) return false
  if (!completionIsUpdate.value) return true
  return completionActualMinutes.value !== null && completionActualMinutes.value !== undefined && completionActualMinutes.value !== ''
    || hasCompletionDifficulty.value
})
const taskSummaryStateLabel = computed(() => ({
  pending: '等待任务数据',
  loading: '正在读取任务数据…',
  ready: `已同步 ${tasks.value.length} 项`,
  error: '任务数据暂不可用',
}[taskDataState.value] || '任务数据暂不可用'))
const taskCountStateLabel = computed(() => ({
  pending: '等待数据',
  loading: '读取中…',
  error: '暂不可用',
}[taskDataState.value] || '暂不可用'))
const taskSummary = computed(() => {
  const taskList = Array.isArray(tasks.value) ? tasks.value : []
  const activeTasks = taskList.filter((task) => task && task.status !== 'completed')
  const today = localDateOf(new Date())
  return {
    pending: activeTasks.length,
    dueToday: activeTasks.filter((task) => localDateOf(task?.due_at) === today).length,
    overdue: activeTasks.filter((task) => isOverdue(task)).length,
    completed: taskList.filter((task) => task?.status === 'completed').length,
  }
})
const tableEmptyText = computed(() => {
  if (taskDataState.value === 'pending' || taskDataState.value === 'loading') return '正在读取任务列表…'
  if (taskDataState.value === 'error') return '任务数据暂不可用，请稍后重试'
  if (hasRouteFilters.value) return '当前定位筛选无结果，可清除定位筛选后再试。'
  return hasActiveFilters.value ? '没有符合当前筛选条件的任务' : '还没有任务记录'
})

function positiveRouteId(value) {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : null
}

const routeFilters = computed(() => ({
  taskId: positiveRouteId(route.query.task_id),
  navigationKey: navigationKey(route.query.navigation_key),
  navigationKeyProvided: Object.prototype.hasOwnProperty.call(route.query, 'navigation_key'),
  courseId: positiveRouteId(route.query.course_id),
  materialId: positiveRouteId(route.query.material_id),
  date: typeof route.query.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(route.query.date) ? route.query.date : '',
  view: ['weekly_overdue', 'weekly_estimate_variance', 'capacity_next_7_days'].includes(route.query.view) ? route.query.view : '',
}))

const taskNavigationMismatch = computed(() => {
  const filters = routeFilters.value
  return Boolean(filters.taskId && filters.navigationKeyProvided && taskDataState.value === 'ready'
    && (!filters.navigationKey || !tasks.value.some((task) => task.id === filters.taskId && navigationKey(task.navigation_key) === filters.navigationKey)))
})

const deepLinkLabel = computed(() => {
  const filters = routeFilters.value
  if (filters.taskId && taskNavigationMismatch.value) return `这个来源已失效，未打开同编号的新任务；可清除定位后重新选择。`
  if (filters.taskId) return filters.navigationKey ? `已按来源记录定位任务：任务 #${filters.taskId}` : `已定位任务：任务 #${filters.taskId}`
  if (filters.view === 'weekly_overdue') return '已打开筛选视图：截止日期近 7 天的逾期任务'
  if (filters.view === 'weekly_estimate_variance') return '已打开筛选视图：截止日期近 7 天的估时偏差任务'
  if (filters.view === 'capacity_next_7_days') return '已打开筛选视图：未来 7 天的学习时间安排'
  if (filters.date) return `已定位截止日期：${filters.date}`
  if (filters.courseId) return `已定位课程任务：课程 #${filters.courseId}`
  if (filters.materialId) return `已定位资料关联任务：资料 #${filters.materialId}`
  return ''
})

const routeScopedTasks = computed(() => {
  const filters = routeFilters.value
  return tasks.value.filter((task) => {
    const viewMatch = !filters.view
      || filters.view === 'weekly_overdue' && isOverdue(task) && withinPastDays(task.due_at, 7)
      || filters.view === 'weekly_estimate_variance' && withinPastDays(task.due_at, 7) && Number.isFinite(Number(task.actual_minutes)) && Number.isFinite(Number(task.estimated_minutes)) && Number(task.actual_minutes) !== Number(task.estimated_minutes)
      || filters.view === 'capacity_next_7_days' && withinNextDays(task.due_at, 7)
    const taskMatch = !filters.taskId || (task.id === filters.taskId && (!filters.navigationKeyProvided || Boolean(filters.navigationKey) && navigationKey(task.navigation_key) === filters.navigationKey))
    const courseMatch = !filters.courseId || task.course_id === filters.courseId
    const materialMatch = !filters.materialId || task.material_id === filters.materialId
    const dateMatch = !filters.date || localDateOf(task.due_at) === filters.date
    return viewMatch && taskMatch && courseMatch && materialMatch && dateMatch
  })
})

const filteredTasks = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  return routeScopedTasks.value.filter((task) => {
    const matchStatus = !statusFilter.value
      || (statusFilter.value === 'overdue' ? isOverdue(task) : task.status === statusFilter.value)
    const matchKeyword = !value || [task.name, task.description, task.task_type].filter(Boolean).join(' ').toLowerCase().includes(value)
    return matchStatus && matchKeyword
  })
})

const agendaTasks = computed(() => routeScopedTasks.value.map((task) => ({
  ...task,
  course_name: courseName(task.course_id),
  source_context: taskSourceContext(task),
})))
const completionBusyTaskIds = computed(() => Object.keys(completionLoading.value))
const materialNavigationBusyIds = computed(() => Object.keys(materialNavigationLoading.value))

function localDateOf(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function withinNextDays(value, days) {
  if (!value) return false
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return false
  const now = Date.now()
  return timestamp >= now && timestamp < now + days * 24 * 60 * 60 * 1000
}

function withinPastDays(value, days) {
  if (!value) return false
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return false
  const now = Date.now()
  return timestamp <= now && timestamp >= now - days * 24 * 60 * 60 * 1000
}

function taskRowClassName({ row }) {
  return row.id === routeFilters.value.taskId && (!routeFilters.value.navigationKeyProvided || Boolean(routeFilters.value.navigationKey) && navigationKey(row.navigation_key) === routeFilters.value.navigationKey) ? 'source-focused-row' : ''
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
}

async function removeRouteQuery(keys) {
  const query = { ...route.query }
  keys.forEach((key) => { delete query[key] })
  await router.replace({ path: route.path, query, hash: route.hash })
}

function clearRouteFilters() {
  return removeRouteQuery(['task_id', 'navigation_key', 'course_id', 'material_id', 'date', 'view'])
}

async function showDetailedTaskList() {
  setViewMode('detailed')
  await nextTick()
  const heading = document.getElementById('task-list-heading')
  heading?.focus({ preventScroll: true })
  heading?.scrollIntoView({ behavior: 'auto', block: 'start' })
}

function handleActionQuery(action) {
  if (action !== 'create-task') return
  openCreate()
  removeRouteQuery(['action']).catch((err) => ElMessage.error(err?.message || '无法清除任务操作参数'))
}

function emptyForm() {
  return {
    name: '',
    course_id: null,
    material_id: null,
    task_type: '',
    description: '',
    due_at: '',
    priority: 3,
    status: 'not_started',
  }
}

function emptyDurationForm() {
  return {
    estimated_hours: null,
    estimated_remainder_minutes: null,
    remaining_hours: null,
    remaining_remainder_minutes: null,
  }
}

function resetForm() {
  Object.assign(form, emptyForm())
  Object.assign(durationForm, emptyDurationForm())
  editingId.value = null
  editingBaseline.value = null
}

function courseName(courseId) {
  return courses.value.find((course) => course.id === courseId)?.name || '未归类课程'
}

function taskSourceContext(task) {
  const materialId = positiveRouteId(task?.material_id)
  const materialKey = navigationKey(task?.material_navigation_key)
  const liveLabel = typeof task?.source_material_name === 'string' ? task.source_material_name.trim() : ''
  if (materialId !== null && materialKey) {
    return { state: 'available', material_id: materialId, navigation_key: materialKey, label: liveLabel || '关联资料' }
  }

  const historicalLabel = liveLabel
  if (historicalLabel && materialId !== null && !materialKey) return { state: 'identity_missing', material_id: null, label: historicalLabel }
  if (historicalLabel) return { state: 'deleted', material_id: null, label: historicalLabel }
  return { state: 'missing', material_id: null, label: null }
}

function isMaterialNavigationLoading(task) {
  const context = taskSourceContext(task)
  const key = navigationSourceCacheKey({ source_type: 'material', source_id: context.material_id, navigation_key: context.navigation_key })
  return Boolean(key && materialNavigationLoading.value[key])
}

function setMaterialNavigationLoading(sourceRef, loading) {
  const key = navigationSourceCacheKey(sourceRef)
  if (!key) return
  const next = { ...materialNavigationLoading.value }
  if (loading) next[key] = true
  else delete next[key]
  materialNavigationLoading.value = next
}

async function openMaterialSource(task) {
  const context = taskSourceContext(task)
  if (context.state !== 'available' || context.material_id === null) {
    ElMessage.warning(context.state === 'identity_missing'
      ? '暂不能确认来源，请从资料库查看。'
      : context.state === 'deleted' ? '这份历史来源资料已删除，无法打开。' : '该任务尚未关联可打开的资料。')
    return
  }
  const materialId = context.material_id
  const sourceRef = { source_type: 'material', source_id: String(materialId), navigation_key: context.navigation_key }
  const cacheKey = navigationSourceCacheKey(sourceRef)
  if (materialNavigationLoading.value[cacheKey]) return
  setMaterialNavigationLoading(sourceRef, true)
  try {
    const response = await agentApi.resolveSourceRefs([sourceRef])
    const target = validatedMaterialTarget(response, materialId, context.navigation_key)
    if (!target) {
      const resolved = plainObject(response) && Array.isArray(response.items) ? response.items[0] : null
      ElMessage.warning(resolved?.available === false ? (resolved.message || '该资料当前不可打开。') : '资料入口校验失败，已停止跳转。')
      return
    }
    await router.push(target)
  } catch (err) {
    ElMessage.error(err?.message || '资料入口暂时无法解析，请稍后重试。')
  } finally {
    setMaterialNavigationLoading(sourceRef, false)
  }
}

function numericMinutes(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 ? Math.round(number) : null
}

function durationLabel(value) {
  const minutes = numericMinutes(value)
  if (minutes === null) return '待补充'
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  if (!hours) return `${remainder}分钟`
  if (!remainder) return `${hours}小时`
  return `${hours}小时${remainder}分钟`
}

function hasWorkload(task) {
  return numericMinutes(task.estimated_minutes) !== null || numericMinutes(task.remaining_minutes) !== null
}

function workloadLabel(task) {
  return `剩余 ${durationLabel(task.remaining_minutes)} / 预计 ${durationLabel(task.estimated_minutes)}`
}

function setDurationParts(prefix, value) {
  const minutes = numericMinutes(value)
  if (minutes === null) {
    durationForm[`${prefix}_hours`] = null
    durationForm[`${prefix}_remainder_minutes`] = null
    return
  }
  durationForm[`${prefix}_hours`] = Math.floor(minutes / 60)
  durationForm[`${prefix}_remainder_minutes`] = minutes % 60
}

function durationToMinutes(prefix) {
  const hours = durationForm[`${prefix}_hours`]
  const minutes = durationForm[`${prefix}_remainder_minutes`]
  const hasValue = (hours !== null && hours !== undefined) || (minutes !== null && minutes !== undefined)
  if (!hasValue) return { value: null, invalid: false }
  const hourValue = Number(hours ?? 0)
  const minuteValue = Number(minutes ?? 0)
  if (!Number.isInteger(hourValue) || !Number.isInteger(minuteValue) || hourValue < 0 || minuteValue < 0 || minuteValue > 59) {
    return { value: null, invalid: true }
  }
  return { value: hourValue * 60 + minuteValue, invalid: false }
}

function parseLocalDateTime(value) {
  if (typeof value !== 'string') return null
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$/.exec(value)
  if (!match) return null
  const [, yearText, monthText, dayText, hourText, minuteText, secondText] = match
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const hour = Number(hourText)
  const minute = Number(minuteText)
  const second = Number(secondText)
  const date = new Date(year, month - 1, day, hour, minute, second)
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day ||
    date.getHours() !== hour ||
    date.getMinutes() !== minute ||
    date.getSeconds() !== second
  ) return null
  return date
}

function toUtcIso(value) {
  if (!value) return null
  return parseLocalDateTime(value)?.toISOString() || null
}

function padDatePart(value) {
  return String(value).padStart(2, '0')
}

function toLocalDateTimeInput(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${padDatePart(date.getMonth() + 1)}-${padDatePart(date.getDate())}T${padDatePart(date.getHours())}:${padDatePart(date.getMinutes())}:${padDatePart(date.getSeconds())}`
}

function displayStatus(task) {
  if (isOverdue(task)) return '已逾期'
  return statusLabel(task.status)
}

function displayStatusType(task) {
  if (isOverdue(task)) return 'danger'
  return statusType(task.status)
}

function openCreate() {
  taskConflict.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(task) {
  const baseline = editBaseline(task)
  if (!baseline) {
    ElMessage.warning(preconditionMessage())
    return
  }
  taskConflict.value = null
  Object.assign(form, {
    name: task.name,
    course_id: task.course_id,
    material_id: task.material_id,
    task_type: task.task_type || '',
    description: task.description || '',
    due_at: toLocalDateTimeInput(task.due_at),
    priority: task.priority || 3,
    status: task.status,
  })
  setDurationParts('estimated', task.estimated_minutes)
  setDurationParts('remaining', task.remaining_minutes)
  editingId.value = task.id
  editingBaseline.value = baseline
  dialogVisible.value = true
}

async function loadData() {
  loading.value = true
  taskDataState.value = 'loading'
  error.value = ''
  tasks.value = []
  try {
    const [courseData, materialData, taskData] = await Promise.all([
      coursesApi.list(),
      materialsApi.list(),
      tasksApi.list(),
    ])
    if (!Array.isArray(taskData)) throw new Error('任务列表数据格式无效')
    courses.value = courseData
    materials.value = materialData
    tasks.value = taskData
    taskDataState.value = 'ready'
  } catch (err) {
    error.value = err.message
    taskDataState.value = 'error'
  } finally {
    loading.value = false
  }
}

async function saveTask() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写任务名称')
    return
  }
  const dueAt = toUtcIso(form.due_at)
  if (form.due_at && !dueAt) {
    ElMessage.warning('截止时间格式无效，请重新选择')
    return
  }
  const estimated = durationToMinutes('estimated')
  const remaining = durationToMinutes('remaining')
  if (estimated.invalid || remaining.invalid) {
    ElMessage.warning('预计用时和剩余用时请填写有效的小时和分钟')
    return
  }
  if (estimated.value !== null && estimated.value < 15) {
    ElMessage.warning('预计用时至少需要 15 分钟')
    return
  }
  if (estimated.value > 10080 || remaining.value > 10080) {
    ElMessage.warning('单项用时不能超过 168 小时')
    return
  }
  if (remaining.value !== null && estimated.value === null) {
    ElMessage.warning('填写剩余用时前，请先填写预计用时')
    return
  }
  if (remaining.value !== null && estimated.value !== null && remaining.value > estimated.value) {
    ElMessage.warning('剩余用时不能大于预计用时')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      course_id: form.course_id,
      material_id: form.material_id,
      task_type: form.task_type.trim() || null,
      description: form.description.trim() || null,
      due_at: dueAt,
      estimated_minutes: estimated.value,
      remaining_minutes: remaining.value,
      priority: form.priority,
      status: form.status,
    }
    if (editingId.value) {
      const config = editRequestConfig(editingBaseline.value)
      if (!config) {
        ElMessage.warning(preconditionMessage())
        return
      }
      await tasksApi.update(editingId.value, payload, config)
      ElMessage.success('任务已更新')
    } else {
      await tasksApi.create(payload)
      ElMessage.success('任务已添加')
    }
    dialogVisible.value = false
    await loadData()
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'TASK_NOT_FOUND')) {
      taskConflict.value = { baseline: editingBaseline.value, state: isEntityGone(err, 'TASK_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

function createIdempotencyKey() {
  const browserCrypto = typeof window !== 'undefined' ? window.crypto : null
  if (browserCrypto?.randomUUID) return browserCrypto.randomUUID()
  if (browserCrypto?.getRandomValues) {
    const bytes = new Uint8Array(16)
    browserCrypto.getRandomValues(bytes)
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }
  return `task-complete-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function completionIdempotencyKey(taskId) {
  const key = String(taskId)
  if (!completionIdempotencyKeys.has(key)) completionIdempotencyKeys.set(key, createIdempotencyKey())
  return completionIdempotencyKeys.get(key)
}

function isCompletionLoading(taskId) {
  return Boolean(taskId && completionLoading.value[String(taskId)])
}

function hasAnyCompletionLoading() {
  return Object.keys(completionLoading.value).length > 0
}

function setCompletionLoading(taskId, loading) {
  const next = { ...completionLoading.value }
  const key = String(taskId)
  if (loading) next[key] = true
  else delete next[key]
  completionLoading.value = next
}

function openCompletionFeedback(task) {
  if (!task || hasAnyCompletionLoading()) return
  if (!editBaseline(task)) {
    ElMessage.warning(preconditionMessage())
    return
  }
  taskConflict.value = null
  completionTask.value = task
  completionActualMinutes.value = task.status === 'completed' ? numericMinutes(task.actual_minutes) : null
  completionDifficulty.value = task.status === 'completed' && task.difficulty !== null && task.difficulty !== undefined ? Number(task.difficulty) : null
  completionDialogVisible.value = true
}

function closeCompletionFeedback() {
  if (isCompletionLoading(completionTask.value?.id)) return
  completionDialogVisible.value = false
  completionTask.value = null
  completionActualMinutes.value = null
  completionDifficulty.value = null
}

function optionalActualMinutes(value) {
  if (value === null || value === undefined || value === '') return { value: null, valid: true }
  const number = Number(value)
  return { value: number, valid: Number.isInteger(number) && number >= 15 && number <= 10080 }
}

function completionResultConfirmed(result) {
  const receipt = result?.receipt || result?.action_receipt
  if (receipt && receipt.outcome !== undefined) {
    return String(receipt.outcome).toLowerCase() === 'executed'
  }
  const status = result?.task?.status || result?.status
  // The current compatibility response is TaskRead; once the receipt envelope
  // is present, the branch above becomes the authoritative success check.
  return String(status || '').toLowerCase() === 'completed'
}

async function submitCompletionFeedback() {
  if (!completionTask.value) return
  const actual = optionalActualMinutes(completionActualMinutes.value)
  if (!actual.valid) {
    ElMessage.warning('实际用时请填写 15 到 10080 分钟的整数，或留空。')
    return
  }
  const rawDifficulty = Number(completionDifficulty.value)
  const difficulty = completionDifficulty.value === null
    || completionDifficulty.value === undefined
    || completionDifficulty.value === ''
    || rawDifficulty === 0
    ? null
    : rawDifficulty
  if (difficulty !== null && (!Number.isInteger(difficulty) || difficulty < 1 || difficulty > 5)) {
    ElMessage.warning('完成难度请选择 1 到 5 星，或留空。')
    return
  }
  const task = completionTask.value
  if (task.status === 'completed' && !canSubmitCompletionFeedback.value) {
    ElMessage.warning('已完成任务请至少填写实际用时或完成难度后再提交。')
    return
  }
  const completed = await completeTask(task, {
    actual_minutes: actual.value,
    difficulty,
  })
  if (completed) closeCompletionFeedback()
}

async function completeTask(task, feedback = {}) {
  if (!task?.id || isCompletionLoading(task.id)) return false
  const baseline = editBaseline(task)
  const config = editRequestConfig(baseline)
  if (!config) {
    ElMessage.warning(preconditionMessage())
    return false
  }
  setCompletionLoading(task.id, true)
  try {
    const payload = { idempotency_key: completionIdempotencyKey(task.id) }
    if (feedback.actual_minutes !== null && feedback.actual_minutes !== undefined) payload.actual_minutes = feedback.actual_minutes
    if (feedback.difficulty !== null && feedback.difficulty !== undefined) payload.difficulty = feedback.difficulty
    const result = await agentApi.completeTask(task.id, payload, config)
    if (!completionResultConfirmed(result)) {
      const message = result?.receipt?.message || '任务完成状态尚未确认，请稍后查看任务列表。'
      ElMessage.error(message)
      return false
    }
    const message = result?.receipt?.message || result?.message || '任务已完成，反馈已记录。'
    ElMessage.success(message)
    completionIdempotencyKeys.delete(String(task.id))
    await loadData()
    return true
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'TASK_NOT_FOUND')) {
      taskConflict.value = { baseline, state: isEntityGone(err, 'TASK_NOT_FOUND') ? 'missing' : 'changed' }
      return false
    }
    ElMessage.error(err.message)
    return false
  } finally {
    setCompletionLoading(task.id, false)
  }
}

async function removeTask(task) {
  const baseline = editBaseline(task)
  const config = editRequestConfig(baseline)
  if (!config) {
    ElMessage.warning(preconditionMessage())
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除“${task.name}”吗？`, '删除任务', { type: 'warning' })
    await tasksApi.remove(task.id, config)
    ElMessage.success('任务已删除')
    await loadData()
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'TASK_NOT_FOUND')) {
      taskConflict.value = { baseline, state: isEntityGone(err, 'TASK_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

async function viewLatestTask() {
  const id = taskConflict.value?.baseline?.id
  if (!id) return
  try {
    const latest = await tasksApi.list()
    const task = Array.isArray(latest) ? latest.find((item) => item.id === id) : null
    if (!task) {
      taskConflict.value = { ...taskConflict.value, state: 'missing', latestFields: [{ label: '最新状态', value: '这条任务已不存在，不能继续覆盖。' }] }
      ElMessage.warning('这条任务已不存在；你的修改仍保留。')
      return
    }
    if (editBaseline(task)?.navigation_key !== taskConflict.value?.baseline?.navigation_key) {
      taskConflict.value = { ...taskConflict.value, state: 'replacement', latestFields: [{ label: '最新状态', value: '这个编号现在对应另一条任务，不能继续覆盖。' }] }
      ElMessage.warning('这个编号现在对应另一条任务；你的修改仍保留。')
      return
    }
    taskConflict.value = { ...taskConflict.value, latestFields: [
      { label: '任务名称', value: task.name || '未命名任务' },
      { label: '所属课程', value: courseName(task.course_id) },
      { label: '任务类型', value: task.task_type || '未分类' },
      { label: '截止时间', value: task.due_at ? formatDateTime(task.due_at) : '未设置' },
      { label: '优先级', value: task.priority ? `${task.priority} / 5` : '未设置' },
      { label: '工作量', value: workloadLabel(task) },
      { label: '实际用时', value: task.actual_minutes == null ? '未填写' : `${task.actual_minutes} 分钟` },
      { label: '完成难度', value: task.difficulty == null ? '未填写' : `${task.difficulty} / 5` },
      { label: '来源资料', value: taskSourceContext(task).label || '未关联' },
      { label: '说明', value: task.description || '未填写说明' },
      { label: '当前状态', value: displayStatus(task) },
    ] }
    ElMessage.info('已读取最新内容；你的修改仍保留。')
  } catch (err) { ElMessage.error(err.message) }
}

async function discardTaskDraft() {
  try {
    await ElMessageBox.confirm('这会放弃当前未提交的修改，并重新读取任务。是否继续？', '放弃本次修改', { type: 'warning', confirmButtonText: '放弃并重读', cancelButtonText: '保留修改' })
  } catch { return }
  taskConflict.value = null
  dialogVisible.value = false
  completionDialogVisible.value = false
  completionTask.value = null
  resetForm()
  await loadData()
}

watch(() => route.query.action, handleActionQuery)
onMounted(() => {
  handleActionQuery(route.query.action)
  loadData()
})
</script>

<style scoped>
.tasks-page {
  --tasks-ink: var(--ledger-ink, #1e2a44);
  --tasks-paper: var(--ledger-paper, #fffefb);
  --tasks-indigo: var(--ledger-indigo, #5964ed);
  --tasks-amber: var(--ledger-amber, #c9822e);
  --tasks-amber-text: var(--ledger-amber-text, #946020);
  --tasks-coral: var(--ledger-coral, #c94c4c);
  --tasks-line: var(--ledger-line, #d9e0ea);
  --tasks-muted: var(--ledger-muted, #667085);
  min-width: 0;
}

.tasks-page h1,
.tasks-page h2,
.tasks-page h3 {
  overflow-wrap: anywhere;
}

.mb-18 { margin-bottom: 18px; }
.overdue { color: var(--tasks-coral); font-weight: 600; }
.muted { color: #667085; font-size: 12px; }
.task-load-error,
.task-deep-link {
  display: flex;
  align-items: center;
  gap: 10px;
}
.task-load-error :deep(.el-alert),
.task-deep-link :deep(.el-alert) { flex: 1 1 auto; min-width: 0; }
.task-load-error :deep(.el-alert__content),
.task-deep-link :deep(.el-alert__content) { min-width: 0; }
.task-load-error :deep(.el-alert__title),
.task-deep-link :deep(.el-alert__title) { white-space: normal; overflow-wrap: anywhere; }
.task-load-error :deep(.el-button),
.task-deep-link :deep(.el-button) { flex: 0 0 auto; min-height: 44px; }

.task-page-actions {
  align-items: center;
}

.task-page-actions :deep(.el-button) {
  min-height: 44px;
  max-width: 100%;
  min-width: 44px;
  white-space: normal;
  overflow-wrap: anywhere;
  text-align: center;
}

.task-export-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 12px;
  border-left: 1px solid var(--tasks-line);
}

.task-export-actions :deep(.el-button) {
  margin: 0;
  color: var(--tasks-ink);
  background: var(--tasks-paper);
  border-color: #cbd4e0;
}

.task-export-actions :deep(.el-button:hover) {
  color: var(--tasks-indigo);
  border-color: rgba(89, 100, 237, .55);
}

.task-create-action {
  min-width: 112px;
}

.task-agenda-section {
  margin-bottom: 18px;
}

.task-summary {
  min-width: 0;
  margin-bottom: 18px;
  padding: 14px 16px 16px;
  background: var(--tasks-paper);
  border: 1px solid var(--tasks-line);
  border-left: 3px solid var(--tasks-ink);
  border-radius: 4px;
}

.task-summary-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.task-summary-kicker,
.task-table-kicker {
  margin: 0 0 4px;
  color: var(--tasks-muted);
  font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.task-summary-heading h2 {
  margin: 0;
  color: var(--tasks-ink);
  font-size: 16px;
  letter-spacing: .01em;
}

.task-summary-state {
  flex: 0 0 auto;
  color: var(--tasks-muted);
  font-size: 12px;
  line-height: 1.45;
  text-align: right;
}

.task-summary-state--ready { color: var(--tasks-indigo); }
.task-summary-state--error { color: var(--tasks-coral); }
.task-summary-state--loading { color: var(--tasks-amber-text); }

.task-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
  margin: 12px 0 0;
}

.task-summary-item {
  min-width: 0;
  padding: 10px 12px 9px;
  background: #fbfcfe;
  border: 1px solid #e2e7ee;
  border-top: 2px solid var(--tasks-ink);
  border-radius: 3px;
}

.task-summary-item--action { border-top-color: var(--tasks-indigo); }
.task-summary-item--today { border-top-color: var(--tasks-amber); }
.task-summary-item--overdue { border-top-color: var(--tasks-coral); }

.task-summary-item dt {
  color: #59667d;
  font-size: 12px;
  font-weight: 700;
}

.task-summary-value {
  display: block;
  margin: 4px 0 0;
  color: var(--tasks-ink);
  font-family: Bahnschrift, "Aptos Display", "Microsoft YaHei", sans-serif;
  font-size: 25px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  line-height: 1.1;
}

.task-summary-item--action .task-summary-value { color: var(--tasks-indigo); }
.task-summary-item--today .task-summary-value { color: var(--tasks-amber-text); }
.task-summary-item--overdue .task-summary-value { color: var(--tasks-coral); }
.task-summary-value--pending { color: var(--tasks-muted) !important; }

.task-summary-item p {
  min-height: 16px;
  margin: 6px 0 0;
  color: var(--tasks-muted);
  font-size: 13px;
  line-height: 1.45;
}

.task-table-heading {
  min-width: 0;
}

.task-table-kicker {
  margin-bottom: 3px;
}

.task-table-heading h2 {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.task-count {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 7px;
  color: var(--tasks-indigo);
  border: 1px solid rgba(89, 100, 237, .38);
  border-radius: 3px;
  font-family: Bahnschrift, "Microsoft YaHei", sans-serif;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  line-height: 1.3;
}

.task-count--state {
  color: var(--tasks-muted);
  border-color: #cbd4e0;
  font-family: inherit;
  font-variant-numeric: normal;
  font-weight: 600;
}

.task-table-note {
  margin: 5px 0 0;
  color: var(--tasks-muted);
  font-size: 13px;
  line-height: 1.45;
}

#task-list-heading:focus-visible {
  outline: 3px solid rgba(89, 100, 237, .42);
  outline-offset: 4px;
  border-radius: 3px;
}

.task-toolbar-actions {
  align-items: center;
  min-width: 0;
}

.task-filter-label {
  flex: 0 0 auto;
  color: var(--tasks-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .04em;
}

.task-toolbar-actions :deep(.el-input),
.task-toolbar-actions :deep(.el-select) {
  min-width: 0;
}

.task-toolbar-actions :deep(.el-input__wrapper),
.task-toolbar-actions :deep(.el-select__wrapper) {
  min-height: 44px;
}

.task-toolbar-actions :deep(.el-input__wrapper:focus-within),
.task-toolbar-actions :deep(.el-select__wrapper:focus-within) {
  box-shadow: 0 0 0 2px rgba(89, 100, 237, .28);
}

.task-toolbar-actions :deep(.el-button) {
  min-height: 44px;
}

.tasks-page :deep(.el-table) {
  min-width: 0;
}

.table-wrap {
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
}

.task-row-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  min-height: 44px;
}

.task-row-actions-primary,
.task-row-actions-secondary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  max-width: 100%;
}

.task-row-actions :deep(.el-button) {
  min-height: 44px;
  min-width: 44px;
  padding: 8px 6px;
  overflow-wrap: anywhere;
  text-align: center;
  white-space: normal;
}

.task-row-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.task-action-divider {
  width: 1px;
  height: 20px;
  margin: 0 4px;
  background: var(--tasks-line);
}

.tasks-page :deep(.el-dialog .el-button) {
  min-height: 44px;
}

.tasks-page :deep(.el-dialog .el-input__wrapper),
.tasks-page :deep(.el-dialog .el-select__wrapper),
.tasks-page :deep(.el-dialog .el-textarea__inner) {
  min-height: 44px;
}

.tasks-page :deep(.el-dialog .el-rate) {
  min-height: 44px;
  align-items: center;
}

.duration-fields { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; color: var(--tasks-muted); }
.duration-fields .el-input-number { width: 118px; }
.duration-fields :deep(.el-input__wrapper) { min-height: 44px; }
.field-hint { margin-top: 5px; color: #667085; font-size: 13px; line-height: 1.5; }
.completion-dialog-help { margin: 0 0 18px; color: var(--tasks-muted); font-size: 12px; line-height: 1.7; }
.source-focused-row td { background: #f5f6ff !important; }

.task-table-name,
.task-table-meta,
.task-table-course,
.task-table-source {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}

.task-table-meta { font-size: 12px; }
.task-table-source-action { display: inline-flex; align-items: center; min-width: 44px; min-height: 44px; max-width: 100%; margin: 0; padding: 7px 0; color: var(--tasks-indigo); background: transparent; border: 0; border-radius: 3px; cursor: pointer; font: inherit; line-height: 1.45; white-space: normal; overflow-wrap: anywhere; text-align: left; touch-action: manipulation; }
.task-table-source-action:hover { color: #414dcc; text-decoration: underline; text-underline-offset: 3px; }
.task-table-source-action:focus-visible { outline: 3px solid rgba(89, 100, 237, .42); outline-offset: 2px; }
.task-table-source-action:disabled { cursor: wait; opacity: .58; text-decoration: none; }

@media (max-width: 900px) {
  .task-page-actions {
    align-items: stretch;
  }

  .task-export-actions {
    width: 100%;
    padding-top: 10px;
    padding-left: 0;
    border-top: 1px solid var(--tasks-line);
    border-left: 0;
  }

  .task-create-action {
    width: 100%;
  }
}

@media (max-width: 680px) {
  .task-load-error,
  .task-deep-link {
    align-items: stretch;
    flex-direction: column;
  }

  .task-load-error :deep(.el-button),
  .task-deep-link :deep(.el-button) { width: 100%; }

  .task-summary-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .task-summary-state {
    text-align: left;
  }

  .task-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-toolbar-actions {
    align-items: stretch;
  }

  .task-filter-label {
    width: 100%;
  }

}

@media (max-width: 390px) {
  .task-summary {
    padding-right: 12px;
    padding-left: 12px;
  }

  .task-summary-grid {
    gap: 8px;
  }

  .task-summary-item {
    padding-right: 9px;
    padding-left: 9px;
  }

  .task-summary-value {
    font-size: 23px;
  }

}
</style>
