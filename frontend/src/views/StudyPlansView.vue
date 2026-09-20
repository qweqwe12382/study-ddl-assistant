<template>
  <div ref="pageRoot" class="study-plans-page" :class="{ 'is-concise-view': isConciseView, 'is-detailed-view': isDetailedView }">
    <div class="page-intro planner-hero">
      <div class="hero-copy">
        <h1>复习计划</h1>
        <el-button v-if="currentPlan && !planNavigationMismatch" plain @click="togglePlanCreator">{{ creatingPlan ? '收起新计划' : '新建计划' }}</el-button>
        <p>{{ creatingPlan ? '选好复习内容和可用时间，就能生成每日安排。' : '看看近期安排，从下一项开始。' }}</p>
      </div>
      <aside v-if="!creatingPlan" class="hero-status" :class="{ 'is-loading': loading || plansLoading }" aria-live="polite">
        <span class="hero-status-label">当前计划</span>
        <strong>{{ loading || plansLoading ? '正在读取' : planNavigationMismatch ? '来源已失效' : currentPlan ? currentPlan.title : '待建立计划' }}</strong>
        <span class="hero-status-meta">
          {{ planNavigationMismatch ? '清除定位后可重新选择计划' : currentPlan ? `复习至 ${currentPlan.exam_date} · ${currentPlan.material_count || 0} 份资料 · ${currentPlan.task_count || 0} 条任务` : selectedCourse ? selectedCourse.name : loading ? '正在读取课程' : '尚未选择课程' }}
        </span>
        <el-select v-if="courses.length > 1 && !planNavigationMismatch" :model-value="planForm.course_id" class="plan-course-switch" aria-label="切换课程查看计划" :disabled="loading || plansLoading" @update:model-value="browseCourse">
          <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
        </el-select>
      </aside>
    </div>

    <nav class="schedule-switch" aria-label="日程与学习安排">
      <router-link to="/schedule">课表与考试 <small>固定时间</small></router-link>
      <span aria-current="page">复习计划 <small>每天学什么</small></span>
    </nav>

    <details v-if="isDetailedView && !planNavigationMismatch && !creatingPlan" class="plan-export-details"><summary>导出计划与学习记录</summary>
    <div class="page-actions planner-export-actions" aria-label="导出操作">
      <el-button @click="downloadFile(exportsApi.tasksCsvUrl())">导出截止任务 CSV</el-button>
      <el-button @click="downloadFile(exportsApi.tasksCalendarUrl())">导出待办日历</el-button>
      <el-button @click="downloadFile(exportsApi.materialsMarkdownUrl())">导出资料 Markdown</el-button>
      <el-button :disabled="!currentPlan" @click="downloadFile(exportsApi.studyPlanMarkdownUrl(currentPlan.id), `${currentPlan.title || '复习计划'}.md`)">导出计划 Markdown</el-button>
    </div>
    </details>

    <div v-if="error" class="plan-global-error">
      <el-alert :title="error" type="error" show-icon :closable="false" role="alert" />
      <el-button plain class="plan-retry-button" :loading="loading || plansLoading" :disabled="loading || plansLoading" @click="loadData">重新读取计划</el-button>
    </div>
    <EditConflictCard :visible="Boolean(planConflict)" :title="planConflictTitle" :message="planConflictMessage" :latest-fields="planConflict?.latestFields || []" @view-latest="viewLatestPlan" @discard="discardPlanDraft" />
    <el-alert v-if="deepLinkLabel && !planNavigationMismatch && !creatingPlan" :title="deepLinkLabel" type="info" show-icon role="status" :closable="false" class="mb-18" />
    <section v-if="planNavigationMismatch" class="plan-source-expired" role="status" aria-live="polite">
      <strong>原来的计划已失效，未能打开新的同编号计划。</strong>
      <p>清除当前定位后，可以重新选择计划。</p>
      <el-button plain type="primary" @click="clearExpiredPlanLocation">清除当前定位</el-button>
    </section>
    <div v-if="loading || plansLoading" class="sr-only" role="status" aria-live="polite">正在加载复习计划…</div>

    <el-card v-if="!planNavigationMismatch && (creatingPlan || (!loading && !plansLoading && !currentPlan))" class="content-card plan-config" shadow="never" v-loading="loading" :aria-busy="loading">
      <div class="card-heading config-heading">
        <div class="card-heading-copy">
          <h2>新建复习计划</h2>
        </div>
      </div>
      <el-form :model="planForm" label-position="top" class="plan-form" :disabled="generating" @submit.prevent="generatePlan">
        <section class="plan-form-section" aria-labelledby="plan-content-heading">
          <h3 id="plan-content-heading"><span aria-hidden="true">1</span>复习什么</h3>
          <el-form-item label="课程" required class="plan-form-course">
            <CourseSelect :model-value="planForm.course_id" :courses="courses" :disabled="generating" @created="onCourseCreated" @update:model-value="changeCourse" />
          </el-form-item>
          <PlanSourcePicker ref="sourcePicker" :course-id="planForm.course_id" :material-id="positiveRouteId(route.query.course_id) === planForm.course_id ? positiveRouteId(route.query.material_id) : null" :material-key="String(route.query.material_key || '')" :exam-date="planForm.exam_date" :daily-minutes="planForm.daily_minutes" :disabled="generating" @change="sourceSelection = $event" />
        </section>
        <section class="plan-form-section" aria-labelledby="plan-time-heading">
          <h3 id="plan-time-heading"><span aria-hidden="true">2</span>什么时候复习</h3>
          <div class="plan-time-fields">
            <el-form-item label="复习到哪天" required class="plan-form-date">
              <el-date-picker v-model="planForm.exam_date" type="date" value-format="YYYY-MM-DD" placeholder="选择复习截止日期" :disabled-date="disabledBeforeToday" style="width: 100%" @change="examDateEdited = true" />
              <div class="plan-date-presets" role="group" aria-label="快捷复习期限">
                <button v-for="days in [7, 14]" :key="days" type="button" :disabled="generating" @click="setReviewDays(days)">先安排{{ days === 7 ? '一' : '两' }}周</button>
                <button v-if="knownExamDate" type="button" :disabled="generating" @click="planForm.exam_date = knownExamDate; examDateEdited = false">使用考试日期</button>
              </div>
              <p class="plan-date-hint" role="status">{{ !examDateEdited && knownExamDate && planForm.exam_date === knownExamDate ? '已带入这门课最近的考试日期，可修改。' : !examDateEdited && !routeExamDate() ? '暂按两周安排复习，可选期限或修改日期。' : '按所选日期安排复习。' }}</p>
            </el-form-item>
            <el-form-item label="每天可用时间" required class="plan-form-capacity">
              <div class="minutes-field">
                <el-input-number v-model="planForm.daily_minutes" :min="15" :max="1440" :step="15" style="width: 100%" />
                <span class="form-suffix">分钟</span>
              </div>
            </el-form-item>
          </div>
          <div class="duration-presets" aria-label="每天复习时间快捷选择">
            <button v-for="minutes in [30, 60, 90]" :key="minutes" type="button" :aria-pressed="planForm.daily_minutes === minutes" :disabled="generating" @click="planForm.daily_minutes = minutes">{{ minutes }} 分钟</button>
          </div>
          <p class="submit-hint capacity-note">从今天开始安排。请填写扣除上课等安排后可用的时间；这个上限只用于本计划，多份计划的用时需自行合计。</p>
        </section>
        <details class="plan-extra-options">
          <summary>更多设置<span>{{ planForm.title.trim() || '计划名称可自动填写' }}</span></summary>
          <el-form-item label="计划名称" class="plan-form-title">
            <el-input v-model="planForm.title" :maxlength="200" placeholder="留空则使用课程名生成" style="width: 100%" />
          </el-form-item>
          <router-link class="plan-import-link" :to="{ path: '/materials', query: { action: 'upload', intent: 'plan', ...(planForm.course_id ? { course_id: planForm.course_id } : {}), ...(planForm.exam_date ? { exam_date: planForm.exam_date } : {}), ...(planForm.daily_minutes ? { daily_minutes: planForm.daily_minutes } : {}) } }">已有计划文件？作为参考导入</router-link>
        </details>
        <div v-if="generationError" class="plan-generation-error" role="alert">
          <p>{{ generationError }}</p>
          <el-button v-if="sourceRefreshRequired" plain :disabled="generating" @click="refreshPlanSources">刷新所选内容</el-button>
        </div>
        <el-form-item class="plan-form-submit">
          <el-button native-type="submit" type="primary" :loading="generating" :disabled="loading || plansLoading || !planForm.course_id || generating || !sourcesReady || !planForm.exam_date">生成并保存计划</el-button>
          <span class="submit-hint">{{ sourcesReady ? '仅安排已选内容，生成后可修改。' : '先选好复习内容，再生成计划。' }}</span>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="!creatingPlan">
    <details v-if="isDetailedView && !planNavigationMismatch" class="plan-calibration-details"><summary>预计用时依据与重置</summary>
    <el-card class="content-card calibration-card" shadow="never" v-loading="calibrationLoading">
      <div class="card-heading calibration-heading">
        <div class="card-heading-copy">
          <h2>预计用时依据</h2>
          <p class="calibration-intro">系统会参考已完成任务的实际用时，逐步修正这门课的预计工作量。</p>
        </div>
        <div class="calibration-actions">
          <span class="selected-course-note">{{ loading ? '课程读取中' : selectedCourse ? `当前课程：${selectedCourse.name}` : '尚未选择课程' }}</span>
          <el-button
            plain
            type="warning"
            :loading="calibrationResetting"
            :disabled="!planForm.course_id || calibrationResetting || calibrationLoading"
            @click="resetCalibration"
          >
           重置这门课的估时依据
          </el-button>
        </div>
      </div>
      <el-alert v-if="calibrationError" :title="calibrationError" type="warning" show-icon closable class="calibration-message" @close="calibrationError = ''" />
      <div v-if="loading || calibrationLoading" class="calibration-loading" role="status">正在读取课程估时依据…</div>
      <template v-else-if="calibration.available">
        <div class="calibration-metrics">
          <div class="calibration-metric">
            <span>有效反馈</span>
            <strong>{{ calibration.sample_count === null ? '待积累' : `${calibration.sample_count} / ${calibration.minimum_sample_count === null ? '—' : calibration.minimum_sample_count} 次` }}</strong>
          </div>
          <div class="calibration-metric">
            <span>校准状态</span>
            <strong>{{ calibration.eligible ? '已形成依据' : '样本积累中' }}</strong>
          </div>
          <div class="calibration-metric">
            <span>建议系数</span>
            <strong>{{ calibration.factor === null ? '暂未形成' : `${calibration.factor} 倍` }}</strong>
          </div>
          <div class="calibration-metric">
            <span>完成难度均值</span>
            <strong>{{ calibration.difficulty_average === null ? '待积累' : `${calibration.difficulty_average} / 5` }}</strong>
          </div>
        </div>
        <div class="calibration-basis">
          <span class="calibration-basis-label">依据说明</span>
          <span>
            {{ calibration.basis || '根据已完成任务反馈计算，样本不足时保留原有估时。' }}
            <template v-if="calibration.median_ratio !== null">当前反馈中位比值 {{ calibration.median_ratio }} 倍。</template>
            <template v-if="calibration.ratio_bounds">单条反馈按 {{ calibration.ratio_bounds.minimum }}–{{ calibration.ratio_bounds.maximum }} 倍范围裁剪。</template>
          </span>
        </div>
      </template>
      <div v-else-if="calibrationError" class="calibration-empty calibration-error-state" role="status">
        当前课程估时依据暂时无法读取；计划生成仍会保留原始估时，请稍后重试。
      </div>
      <div v-else class="calibration-empty" role="status">
        {{ planForm.course_id ? '暂时没有可用的完成反馈；完成任务并选择“完成并反馈”后，这里会逐步形成校准依据。' : '先选择课程，查看该课程的估时校准依据。' }}
      </div>
    </el-card>

    </details>

    <section v-if="!planNavigationMismatch && currentPlan && unscheduledItems.length" class="unscheduled-snapshot" aria-labelledby="unscheduled-snapshot-heading">
      <div class="unscheduled-snapshot-heading">
        <div>
          <p class="step-label">生成时快照</p>
          <h2 id="unscheduled-snapshot-heading">未排入 {{ unscheduledTotalMinutes }} 分钟</h2>
        </div>
        <span>按生成当时的每日上限、截止时间和主题数量计算</span>
      </div>
      <ul class="unscheduled-list">
        <li v-for="item in unscheduledItems" :key="`${item.source_type}:${item.source_id}`">
          <div>
            <strong>{{ item.label }}</strong>
            <span>已排 {{ item.scheduled_minutes }} 分钟 · 未排 {{ item.unscheduled_minutes }} 分钟 · {{ unscheduledReasonLabel(item.reason) }}</span>
          </div>
          <el-button
            v-if="canOpenUnscheduledSource(item)"
            link
            type="primary"
            :loading="unscheduledNavigationLoading === unscheduledSourceKey(item)"
            :disabled="Boolean(unscheduledNavigationLoading)"
            @click="openUnscheduledSource(item)"
          >查看{{ item.source_type === 'task' ? '任务' : '资料' }}</el-button>
        </li>
      </ul>
    </section>

    <section v-if="!planNavigationMismatch && isConciseView && currentPlan" class="concise-plan-shell" aria-labelledby="concise-plan-heading">
      <div class="concise-plan-toolbar">
        <div>
          <h2 id="concise-plan-heading" tabindex="-1">近期安排</h2>
        </div>
        <div class="toolbar-actions concise-plan-actions">
          <el-select v-if="plans.length" v-model="selectedPlanId" placeholder="选择已有计划" aria-label="选择已有复习计划" style="width: 240px" @change="selectPlan">
            <el-option v-for="plan in plans" :key="plan.id" :label="planOptionLabel(plan)" :value="plan.id" />
          </el-select>
          <el-button plain aria-label="切换到完整视图管理复习计划" @click="openDetailedPlan">完整管理</el-button>
        </div>
      </div>
      <StudyWeekBoard
        ref="weekBoardRef"
        :plan="currentPlan"
        :items="visiblePlanItems"
        :loading="plansLoading"
        :saving="saving"
        :focused-item-id="focusedPlanItemId"
        :delayed-only="routeFilters.view === 'weekly_plan_delays'"
        @complete="completePlanItem"
        @open-details="openPlanItemDetails"
      />
      <div v-if="planRiskWarnings.length" class="plan-warnings concise-plan-warnings" aria-label="计划原始提示">
        <el-alert v-for="warning in planRiskWarnings" :key="warning" :title="warning" type="warning" show-icon :closable="false" />
      </div>
    </section>

    <el-card v-else-if="!planNavigationMismatch && isDetailedView" class="table-card plan-card" shadow="never" v-loading="plansLoading" :aria-busy="plansLoading">
      <div class="table-toolbar">
        <div class="table-heading">
          <h2 id="detailed-plan-heading" tabindex="-1">编辑并保存计划 <el-tag v-if="currentPlan" size="small" effect="plain">{{ currentPlan.items?.length || 0 }} 项</el-tag></h2>
          <div v-if="currentPlan && isDetailedView" class="plan-meta">
            {{ currentPlan.title }} · 复习至 {{ currentPlan.exam_date }} · 每日上限 {{ currentPlan.daily_minutes }} 分钟 ·
            已完成 {{ completedItemCount }}/{{ currentPlan.items?.length || 0 }} 项
          </div>
          <p v-else-if="isDetailedView" class="table-heading-note">{{ plansLoading ? '已有计划读取中…' : '生成计划后，可在这里逐日调整并保存。' }}</p>
        </div>
        <div class="toolbar-actions">
          <el-select v-if="plans.length" v-model="selectedPlanId" placeholder="选择已有计划" aria-label="选择已有复习计划" style="width: 240px" @change="selectPlan">
            <el-option v-for="plan in plans" :key="plan.id" :label="planOptionLabel(plan)" :value="plan.id" />
          </el-select>
          <el-button v-if="currentPlan" plain type="warning" aria-label="归档当前复习计划" @click="archivePlan">归档</el-button>
          <el-button v-if="currentPlan" type="primary" :loading="saving" :disabled="saving" aria-label="保存当前复习计划修改" @click="savePlan">保存修改</el-button>
        </div>
      </div>

      <div v-if="currentPlan" class="plan-summary">
        <div class="summary-item"><span>计划总时长</span><strong>{{ totalMinutes }} 分钟</strong></div>
        <div class="summary-item"><span>已完成时长</span><strong>{{ completedMinutes }} 分钟</strong></div>
        <div class="summary-progress">
          <div class="summary-progress-label"><span>完成进度</span><strong>{{ progressPercent }}%</strong></div>
          <el-progress :percentage="progressPercent" :show-text="false" :stroke-width="8" />
        </div>
      </div>

      <div v-if="isDetailedView && currentPlan?.warnings?.length" class="plan-warnings plan-warnings-detailed" aria-label="计划风险与依据说明">
        <el-alert v-for="warning in currentPlan.warnings" :key="warning" :title="warning" type="warning" show-icon :closable="false" />
      </div>

      <div v-if="currentPlan" class="table-wrap plan-table-wrap">
        <p class="plan-table-scroll-hint">明细字段较多，窄屏可在表格内横向滑动查看。</p>
        <el-table :data="visiblePlanItems" row-key="id" aria-label="复习计划明细" :empty-text="routeFilters.view === 'weekly_plan_delays' ? '当前计划没有延期明细' : '当前计划没有明细'" :row-class-name="planItemRowClassName">
          <el-table-column label="日期" width="145">
            <template #default="{ row }">
              <el-date-picker v-model="row.date" type="date" value-format="YYYY-MM-DD" size="small" :aria-label="`“${row.title || '未命名复习项'}”的日期`" :disabled-date="disabledAfterExam" />
            </template>
          </el-table-column>
          <el-table-column label="阶段 / 主题" min-width="260">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.phase }}</el-tag>
              <el-input v-model="row.title" size="small" class="item-title-input" :aria-label="`计划项标题：${row.title || '未命名复习项'}`" />
            </template>
          </el-table-column>
          <el-table-column label="复习内容" min-width="370">
            <template #default="{ row }"><el-input v-model="row.content" type="textarea" :rows="2" size="small" :aria-label="`“${row.title || '未命名复习项'}”的复习内容`" /></template>
          </el-table-column>
          <el-table-column label="时长" width="125">
            <template #default="{ row }">
              <el-input-number v-model="row.minutes" :min="1" :max="1440" size="small" controls-position="right" :aria-label="`“${row.title || '未命名复习项'}”的预计分钟数`" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="125">
            <template #default="{ row }">
              <el-select v-model="row.status" size="small" :aria-label="`“${row.title || '未命名复习项'}”的完成状态`">
                <el-option label="未开始" value="not_started" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="已完成" value="completed" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="isDetailedView" label="来源" min-width="150">
            <template #default="{ row }"><span class="row-meta">{{ sourceLabel(row) }}</span></template>
          </el-table-column>
        </el-table>
      </div>
      <div v-else class="empty-state plan-empty">
        <p class="plan-empty-message">{{ planEmptyMessage }}</p>
        <el-button plain type="primary" @click="togglePlanCreator">新建计划</el-button>
      </div>
    </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElAlert,
  ElCard,
  ElDatePicker,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElProgress,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus'

import { academicCalendarApi, agentApi, coursesApi, exportsApi, studyPlansApi } from '../api'
import EditConflictCard from '../components/EditConflictCard.vue'
import CourseSelect from '../components/CourseSelect.vue'
import { useViewMode } from '../composables/useViewMode'
import { downloadFile } from '../utils/download'
import { toDateInputValue } from '../utils/format'
import { navigationKey, positiveMaterialId, validatedSourceNavigationTarget } from '../utils/materialSourceNavigation'
import { editBaseline, editRequestConfig, isEditConflict, isEntityGone, preconditionMessage } from '../utils/editPrecondition'
import { nextCourseExamDate } from '../utils/dailyWorkflow'

const PlanSourcePicker = defineAsyncComponent(() => import('../components/PlanSourcePicker.vue'))
const creatingPlan = ref(false)
const sourceSelection = ref(null)
const sourcePicker = ref(null)
const generationError = ref('')
const sourceRefreshRequired = ref(false)
const sourcesReady = computed(() => sourceSelection.value?.ready && sourceSelection.value.courseId === planForm.course_id && (sourceSelection.value.material_sources.length + sourceSelection.value.task_sources.length > 0))
const StudyWeekBoard = defineAsyncComponent(() => import('../components/StudyWeekBoard.vue'))
const loading = ref(false)
const plansLoading = ref(false)
const generating = ref(false)
const saving = ref(false)
const error = ref('')
const courses = ref([])
const knownExams = ref([])
const examDateEdited = ref(false)
const knownExamDate = computed(() => nextCourseExamDate(knownExams.value, planForm.course_id))
const plans = ref([])
const currentPlan = ref(null)
const planBaseline = ref(null)
const planConflict = ref(null)
const planConflictTitle = computed(() => planConflict.value?.state === 'missing'
  ? '这份计划已不存在'
  : planConflict.value?.state === 'replacement'
    ? '这个编号已换成另一份计划'
    : '这份内容刚被其他页面更新了')
const planConflictMessage = computed(() => planConflict.value?.state === 'missing'
  ? '本次没有覆盖内容，当前草稿仍保留。可查看最新状态，或放弃草稿后重新选择。'
  : planConflict.value?.state === 'replacement'
    ? '本次没有覆盖新计划，当前草稿仍保留。请放弃草稿后重新选择计划。'
    : '本次未覆盖新内容，当前草稿仍保留。先查看最新内容，再决定是否放弃这次修改。')
const selectedPlanId = ref(null)
const calibrationLoading = ref(false)
const calibrationResetting = ref(false)
const calibrationError = ref('')
const plansError = ref('')
const routePlanNotFound = ref(false)
const routePlanError = ref('')
const pageRoot = ref(null)
const weekBoardRef = ref(null)
const detailFocusItemId = ref('')
const unscheduledNavigationLoading = ref('')
const persistedPlanItems = ref([])
const calibration = ref(normalizeCalibration({}))
const calibrationResetKeys = new Map()
const route = useRoute()
creatingPlan.value = wantsPlanCreator()
const router = useRouter()
const { isConciseView, isDetailedView, setViewMode } = useViewMode()
let plansRequestId = 0
let calibrationRequestId = 0

const planForm = reactive({
  course_id: null,
  exam_date: routeExamDate() || defaultExamDate(),
  daily_minutes: routeDailyMinutes() || 60,
  title: '',
})

const progressPercent = computed(() => {
  if (!currentPlan.value?.items?.length) return 0
  return Math.round((completedItemCount.value / currentPlan.value.items.length) * 100)
})
const completedItemCount = computed(() => currentPlan.value?.items?.filter((item) => item.status === 'completed').length || 0)
const totalMinutes = computed(() => currentPlan.value?.items?.reduce((total, item) => total + (item.minutes || 0), 0) || 0)
const completedMinutes = computed(() => currentPlan.value?.items?.reduce((total, item) => total + (item.status === 'completed' ? item.minutes || 0 : 0), 0) || 0)
const unscheduledItems = computed(() => (Array.isArray(currentPlan.value?.unscheduled_items) ? currentPlan.value.unscheduled_items : [])
  .filter((item) => ['task', 'material'].includes(item?.source_type)
    && positiveMaterialId(item?.source_id) !== null
    && Number.isInteger(item?.scheduled_minutes) && item.scheduled_minutes >= 0
    && Number.isInteger(item?.unscheduled_minutes) && item.unscheduled_minutes > 0))
const unscheduledTotalMinutes = computed(() => unscheduledItems.value.reduce((total, item) => total + item.unscheduled_minutes, 0))
const selectedCourse = computed(() => courses.value.find((course) => course.id === planForm.course_id) || null)
const planRiskWarnings = computed(() => (Array.isArray(currentPlan.value?.warnings) ? currentPlan.value.warnings : [])
  .filter((warning) => !String(warning || '').includes('已按该课程完成反馈校准系数')))

const planEmptyMessage = computed(() => {
  if (loading.value || plansLoading.value) return '正在读取复习计划…'
  if (routePlanNotFound.value && routeFilters.value.planId) return '未找到链接中的复习计划；请从当前课程列表选择或生成新计划。'
  if (routePlanError.value || plansError.value) return '复习计划读取失败，请点击“重新读取计划”再试。'
  if (error.value) return '课程列表暂时无法读取，请点击“重新读取计划”再试。'
  if (!courses.value.length) return '还没有课程，先添加课程，再生成一份复习计划。'
  return '请选择课程并生成一份复习计划。'
})

function positiveRouteId(value) {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : null
}

function isPlanNotFoundError(error) {
  const status = error?.status ?? error?.response?.status
  const message = String(error?.message || error || '')
  return status === 404 || /STUDY_PLAN_NOT_FOUND|复习计划不存在/.test(message)
}

const routeFilters = computed(() => ({
  planId: positiveRouteId(route.query.plan_id || route.query.study_plan_id),
  navigationKey: navigationKey(route.query.navigation_key),
  navigationKeyProvided: Object.prototype.hasOwnProperty.call(route.query, 'navigation_key'),
  courseId: positiveRouteId(route.query.course_id),
  itemId: typeof route.query.item_id === 'string' && route.query.item_id.trim() ? route.query.item_id.trim().slice(0, 80) : '',
  view: route.query.view === 'weekly_plan_delays' ? 'weekly_plan_delays' : '',
}))

const planNavigationMismatch = computed(() => {
  const filters = routeFilters.value
  if (!filters.planId || !filters.navigationKeyProvided || loading.value || plansLoading.value) return false
  const plan = currentPlan.value
  if (!filters.navigationKey || !plan || plan.id !== filters.planId) return true
  if (filters.itemId) return !plan.items?.some((item) => item.id === filters.itemId && navigationKey(item.navigation_key) === filters.navigationKey)
  return navigationKey(plan.navigation_key) !== filters.navigationKey
})

const focusedPlanItemId = computed(() => planNavigationMismatch.value ? '' : routeFilters.value.itemId || detailFocusItemId.value)

function chinaLocalDateKey(value = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

function shiftDateKey(value, dayDelta) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return ''
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() + dayDelta)
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`
}

function isWeeklyDelayedItem(item) {
  const today = chinaLocalDateKey()
  const windowStart = shiftDateKey(today, -6)
  return item?.status !== 'completed'
    && typeof item?.date === 'string'
    && item.date >= windowStart
    && item.date < today
}

function weeklyDelayedItemCount(plan) {
  return (Array.isArray(plan?.items) ? plan.items : []).filter(isWeeklyDelayedItem).length
}

function planOptionLabel(plan) {
  const base = `${plan.title} · ${plan.exam_date || '复习期限待定'}`
  if (routeFilters.value.view !== 'weekly_plan_delays') return base
  const course = courses.value.find((item) => item.id === plan.course_id)
  return `${base}${course ? ` · ${course.name}` : ''} · ${weeklyDelayedItemCount(plan)} 项延期`
}

const deepLinkLabel = computed(() => {
  const filters = routeFilters.value
  if (filters.planId) {
    if (loading.value || plansLoading.value) return `正在定位复习计划 #${filters.planId}…`
    if (routePlanNotFound.value) return `未找到链接中的复习计划 #${filters.planId}`
    if (routePlanError.value || plansError.value) return `无法读取链接中的复习计划 #${filters.planId}`
    if (!currentPlan.value) return `未找到链接中的复习计划 #${filters.planId}`
    if (planNavigationMismatch.value) return '这个来源已失效，未打开同编号的新计划；可清除定位后重新选择。'
    if (currentPlan.value.id !== filters.planId) return `已切换当前计划；原始深链计划 #${filters.planId} 未选中`
    if (filters.itemId) {
      const hasItem = Array.isArray(currentPlan.value.items) && currentPlan.value.items.some((item) => item.id === filters.itemId)
      return hasItem
        ? `已${filters.navigationKey ? '按来源记录' : ''}定位复习计划 #${filters.planId} 的计划项：${filters.itemId}`
        : `已打开复习计划 #${filters.planId}，但未找到计划项：${filters.itemId}`
    }
    return filters.navigationKey ? `已按来源记录定位复习计划：计划 #${filters.planId}` : `已定位复习计划：计划 #${filters.planId}`
  }
  if (filters.view === 'weekly_plan_delays') {
    const currentDelayCount = loading.value || plansLoading.value
      ? '读取中'
      : currentPlan.value
        ? `${visiblePlanItems.value.length} 项`
        : '暂无计划'
    const totalDelayCount = loading.value || plansLoading.value
      ? '读取中'
      : `${plans.value.reduce((total, plan) => total + weeklyDelayedItemCount(plan), 0)} 项`
    return `已打开近七个中国本地日期内的延期复习计划项：全部计划共 ${totalDelayCount}，当前计划 ${currentDelayCount}`
  }
  if (filters.courseId) return `已定位课程计划：课程 #${filters.courseId}`
  return ''
})

const visiblePlanItems = computed(() => {
  const items = currentPlan.value?.items || []
  if (routeFilters.value.view !== 'weekly_plan_delays') return items
  return items.filter(isWeeklyDelayedItem)
})

function planItemRowClassName({ row }) {
  return row.id === focusedPlanItemId.value ? 'source-focused-row' : ''
}

function defaultExamDate() {
  const value = new Date()
  value.setDate(value.getDate() + 14)
  return toDateInputValue(value)
}

function setReviewDays(days) {
  planForm.exam_date = shiftDateKey(chinaLocalDateKey(), days)
  examDateEdited.value = true
}

function useSuggestedExamDate() {
  if (!creatingPlan.value || examDateEdited.value) return
  const sameCourse = !positiveRouteId(route.query.course_id) || positiveRouteId(route.query.course_id) === planForm.course_id
  planForm.exam_date = (sameCourse && routeExamDate()) || knownExamDate.value || defaultExamDate()
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
  return `calibration-reset-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function calibrationResetKey(courseId) {
  const key = String(courseId)
  if (!calibrationResetKeys.has(key)) calibrationResetKeys.set(key, createIdempotencyKey())
  return calibrationResetKeys.get(key)
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function firstDefined(source, keys, fallback = null) {
  if (!source || typeof source !== 'object') return fallback
  const key = keys.find((candidate) => source[candidate] !== undefined && source[candidate] !== null)
  return key ? source[key] : fallback
}

function minutesLabel(value) {
  const minutes = numberOrNull(value)
  if (minutes === null) return '待积累'
  const rounded = Math.max(0, Math.round(minutes))
  const hours = Math.floor(rounded / 60)
  const remainder = rounded % 60
  if (!hours) return `${remainder}分钟`
  if (!remainder) return `${hours}小时`
  return `${hours}小时${remainder}分钟`
}

function adjustmentLabel(reference, actual, ratio) {
  const value = numberOrNull(ratio)
    ?? (reference !== null && reference > 0 && actual !== null ? actual / reference - 1 : null)
  if (value === null) return ''
  const percent = Math.round(value * 100)
  if (percent === 0) return '基本一致'
  return percent > 0 ? `增加 ${percent}%` : `减少 ${Math.abs(percent)}%`
}

function calibrationBasis(data, sampleCount, reference, actual) {
  const raw = firstDefined(data, ['basis', 'calculation_basis', 'explanation', 'reason', 'source'])
  if (typeof raw === 'string' && raw.trim()) return raw.trim()
  if (Array.isArray(raw)) return raw.filter(Boolean).join('；')
  const parts = []
  if (sampleCount !== null) parts.push(`已纳入 ${Math.round(sampleCount)} 次完成反馈`)
  if (reference !== null) parts.push(`原参考 ${minutesLabel(reference)}`)
  if (actual !== null) parts.push(`实际中位 ${minutesLabel(actual)}`)
  return parts.join('；')
}

function normalizeCalibration(response) {
  const raw = response?.calibration || response?.data || response || {}
  const data = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}
  const metrics = data.metrics && typeof data.metrics === 'object' ? data.metrics : data
  const sampleValue = firstDefined(metrics, ['sample_count', 'feedback_count', 'completed_count', 'observation_count', 'samples'])
  const sampleCount = Array.isArray(sampleValue) ? sampleValue.length : numberOrNull(sampleValue)
  const reference = numberOrNull(firstDefined(metrics, ['reference_minutes', 'calibrated_minutes', 'estimated_minutes', 'baseline_minutes', 'course_estimated_minutes']))
  const actual = numberOrNull(firstDefined(metrics, ['actual_median_minutes', 'median_actual_minutes', 'actual_minutes_median', 'median_minutes', 'actual_minutes']))
  const ratio = numberOrNull(firstDefined(metrics, ['adjustment_ratio', 'calibration_ratio', 'delta_ratio']))
  const explicitAvailability = data.available ?? data.has_data
  const available = explicitAvailability === undefined
    ? sampleCount !== null || reference !== null || actual !== null
    : Boolean(explicitAvailability)
  return {
    available,
    sample_count: sampleCount,
    minimum_sample_count: numberOrNull(firstDefined(metrics, ['minimum_sample_count', 'min_sample_count'])),
    eligible: Boolean(firstDefined(metrics, ['eligible', 'is_eligible'], false)),
    factor: numberOrNull(firstDefined(metrics, ['factor', 'calibration_factor'])),
    median_ratio: numberOrNull(firstDefined(metrics, ['median_ratio', 'actual_estimated_ratio'])),
    difficulty_average: numberOrNull(firstDefined(metrics, ['difficulty_average', 'average_difficulty'])),
    ratio_bounds: metrics.ratio_bounds && typeof metrics.ratio_bounds === 'object' ? metrics.ratio_bounds : null,
    reference_minutes: reference,
    actual_median_minutes: actual,
    adjustment_label: adjustmentLabel(reference, actual, ratio),
    basis: calibrationBasis(metrics, sampleCount, reference, actual),
    updated_at: firstDefined(metrics, ['updated_at', 'last_updated_at', 'calibrated_at']),
  }
}

function syncFormFromPlan(plan) {
  if (!plan) return
  planConflict.value = null
  planBaseline.value = editBaseline(plan)
  if (!creatingPlan.value) {
    planForm.course_id = plan.course_id
    planForm.exam_date = plan.exam_date || defaultExamDate()
    planForm.daily_minutes = plan.daily_minutes || 60
    planForm.title = plan.title || ''
  }
  persistedPlanItems.value = clonePlanItems(plan.items)
}

function clonePlanItems(items) {
  return (Array.isArray(items) ? items : []).map((item) => ({
    ...item,
    knowledge_points: [...(item.knowledge_points || [])],
    source_material_ids: [...(item.source_material_ids || [])],
    source_task_ids: [...(item.source_task_ids || [])],
  }))
}

async function loadPlans(courseId = planForm.course_id, { respectRoutePlan = true } = {}) {
  const requestId = ++plansRequestId
  const loadAllPlans = routeFilters.value.view === 'weekly_plan_delays'
  const requestIsCurrent = () => requestId === plansRequestId && (loadAllPlans || courseId === planForm.course_id)
  plansError.value = ''
  routePlanNotFound.value = false
  if (!courseId && !loadAllPlans) {
    plans.value = []
    currentPlan.value = null
    selectedPlanId.value = null
    plansLoading.value = false
    return
  }
  plansLoading.value = true
  plans.value = []
  currentPlan.value = null
  selectedPlanId.value = null
  try {
    const requestedPlanId = respectRoutePlan ? routeFilters.value.planId : null
    const listedPlans = await studyPlansApi.list(loadAllPlans ? null : courseId)
    if (!Array.isArray(listedPlans)) throw new Error('复习计划数据格式无效')
    if (!requestIsCurrent()) return
    let requestedPlanError = ''
    let requestedPlanNotFound = false
    if (requestedPlanId && !listedPlans.some((plan) => plan.id === requestedPlanId)) {
      try {
        const requestedPlan = await studyPlansApi.get(requestedPlanId)
        if (!requestIsCurrent()) return
        if (requestedPlan) {
          plans.value = [requestedPlan, ...listedPlans]
        } else {
          requestedPlanNotFound = true
          plans.value = listedPlans
        }
      } catch (err) {
        if (!requestIsCurrent()) return
        if (isPlanNotFoundError(err)) requestedPlanNotFound = true
        else requestedPlanError = err.message
        plans.value = listedPlans
      }
    } else {
      plans.value = listedPlans
    }
    if (!requestIsCurrent()) return
    const selected = requestedPlanId
      ? plans.value.find((plan) => plan.id === requestedPlanId) || null
      : loadAllPlans
        ? plans.value.find((plan) => weeklyDelayedItemCount(plan) > 0) || plans.value[0] || null
        : plans.value.find((plan) => plan.id === selectedPlanId.value) || plans.value[0] || null
    currentPlan.value = selected
    selectedPlanId.value = selected?.id || null
    syncFormFromPlan(selected)
    if (requestedPlanId && !selected) {
      if (requestedPlanNotFound) {
        routePlanNotFound.value = true
      } else if (requestedPlanError) {
        routePlanError.value = requestedPlanError
        plansError.value = requestedPlanError
        if (!error.value) error.value = `无法打开指定的复习计划：${requestedPlanError}`
      }
    }
  } catch (err) {
    if (!requestIsCurrent()) return
    plans.value = []
    currentPlan.value = null
    selectedPlanId.value = null
    plansError.value = err.message
    error.value = err.message
  } finally {
    if (requestId === plansRequestId) plansLoading.value = false
  }
}

async function loadCalibration(courseId = planForm.course_id) {
  const requestId = ++calibrationRequestId
  calibrationError.value = ''
  if (!courseId) {
    calibration.value = normalizeCalibration({})
    calibrationLoading.value = false
    return
  }
  calibrationLoading.value = true
  try {
    const response = await agentApi.calibration(courseId)
    if (requestId !== calibrationRequestId || courseId !== planForm.course_id) return
    calibration.value = normalizeCalibration(response)
  } catch (err) {
    if (requestId !== calibrationRequestId || courseId !== planForm.course_id) return
    calibration.value = normalizeCalibration({})
    calibrationError.value = `${err.message}；暂时使用原有估时。`
  } finally {
    if (requestId === calibrationRequestId) calibrationLoading.value = false
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  plansError.value = ''
  routePlanNotFound.value = false
  routePlanError.value = ''
  plansRequestId += 1
  calibrationRequestId += 1
  courses.value = []
  plans.value = []
  currentPlan.value = null
  selectedPlanId.value = null
  planForm.course_id = null
  calibration.value = normalizeCalibration({})
  try {
    const [listedCourses, calendar] = await Promise.all([
      coursesApi.list(), academicCalendarApi.overview().catch(() => null),
    ])
    knownExams.value = calendar?.exams || []
    if (!Array.isArray(listedCourses)) throw new Error('课程数据格式无效')
    courses.value = listedCourses
    let targetPlan = null
    let routePlanNotFoundOnLoad = false
    let routePlanLoadError = ''
    if (routeFilters.value.planId) {
      try {
        targetPlan = await studyPlansApi.get(routeFilters.value.planId)
      } catch (err) {
        if (isPlanNotFoundError(err)) routePlanNotFoundOnLoad = true
        else {
          routePlanLoadError = err.message
          error.value = `无法打开指定的复习计划：${err.message}`
        }
      }
    }
    if (targetPlan) {
      planForm.course_id = targetPlan.course_id
      selectedPlanId.value = targetPlan.id
    } else if (routeFilters.value.courseId && courses.value.some((course) => course.id === routeFilters.value.courseId)) {
      planForm.course_id = routeFilters.value.courseId
    } else if (routeFilters.value.courseId && positiveRouteId(route.query.material_id)) {
      throw new Error('这份资料原来的课程已不存在，请回到资料页重新选择课程。')
    } else if (!planForm.course_id && courses.value.length) {
      planForm.course_id = courses.value[0].id
    }
    if (targetPlan && targetPlan.course_id === null) {
      plans.value = [targetPlan]
      currentPlan.value = targetPlan
      selectedPlanId.value = targetPlan.id
      syncFormFromPlan(targetPlan)
      calibration.value = normalizeCalibration({})
    } else {
      await Promise.all([
        loadPlans(planForm.course_id, { respectRoutePlan: Boolean(routeFilters.value.planId && !routePlanNotFoundOnLoad && !routePlanLoadError) }),
        loadCalibration(),
      ])
    }
    if (routePlanNotFoundOnLoad) {
      routePlanNotFound.value = true
      currentPlan.value = null
      selectedPlanId.value = null
    }
    if (routePlanLoadError) {
      routePlanError.value = routePlanLoadError
      plansError.value = routePlanLoadError
      currentPlan.value = null
      selectedPlanId.value = null
      error.value = `无法打开指定的复习计划：${routePlanLoadError}`
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
    if (!currentPlan.value && !error.value && !planNavigationMismatch.value) creatingPlan.value = true
  }
}

function wantsPlanCreator() {
  return route.query.action === 'create' || ['1', 'true'].includes(String(route.query.create || ''))
}

function routeExamDate() {
  const value = String(route.query.exam_date || '')
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return ''
  const date = new Date(`${value}T12:00:00`)
  return !Number.isNaN(date.getTime()) && toDateInputValue(date) === value ? value : ''
}

function routeDailyMinutes() {
  const minutes = Number(route.query.daily_minutes)
  return Number.isInteger(minutes) && minutes >= 15 && minutes <= 1440 ? minutes : null
}

async function togglePlanCreator() {
  creatingPlan.value = !creatingPlan.value
  if (creatingPlan.value) {
    planForm.title = ''
    examDateEdited.value = false
    planForm.exam_date = routeExamDate() || knownExamDate.value || defaultExamDate()
    await router.replace({ path: '/study-plans', query: { action: 'create', ...(planForm.course_id ? { course_id: planForm.course_id } : {}) } })
  } else {
    syncFormFromPlan(currentPlan.value)
    if (currentPlan.value) await router.replace({ path: '/study-plans', query: planLocation(currentPlan.value) })
  }
}

function planLocation(plan) {
  return { plan_id: plan.id, navigation_key: plan.navigation_key, ...(plan.course_id ? { course_id: plan.course_id } : {}), ...(routeFilters.value.view ? { view: routeFilters.value.view } : {}) }
}

function onCourseCreated(course) {
  if (!courses.value.some(item => item.id === course.id)) courses.value.push(course)
}

function changeCourse(courseId) {
  if (generating.value || planForm.course_id === courseId) return
  planForm.course_id = courseId
  onCourseChange()
}

async function browseCourse(courseId) {
  if (courseId === planForm.course_id) return
  await router.replace({ path: '/study-plans', query: { course_id: courseId } })
}

async function refreshPlanSources() {
  await sourcePicker.value?.refreshSources()
  generationError.value = ''
  sourceRefreshRequired.value = false
}

function onCourseChange() {
  examDateEdited.value = false
  useSuggestedExamDate()
  generationError.value = ''
  sourceRefreshRequired.value = false
  planConflict.value = null
  error.value = ''
  plansError.value = ''
  routePlanNotFound.value = false
  routePlanError.value = ''
  selectedPlanId.value = null
  currentPlan.value = null
  loadPlans(planForm.course_id, { respectRoutePlan: false })
  loadCalibration(planForm.course_id)
}

async function selectPlan(planId) {
  if (planNavigationMismatch.value) return
  currentPlan.value = plans.value.find((plan) => plan.id === planId) || null
  error.value = ''
  plansError.value = ''
  routePlanNotFound.value = false
  routePlanError.value = ''
  detailFocusItemId.value = ''
  syncFormFromPlan(currentPlan.value)
  loadCalibration(currentPlan.value?.course_id)
  if (currentPlan.value) await router.replace({ path: '/study-plans', query: planLocation(currentPlan.value) })
}

async function clearExpiredPlanLocation() {
  const query = { ...route.query }
  ;['plan_id', 'study_plan_id', 'item_id', 'navigation_key'].forEach((key) => { delete query[key] })
  await router.replace({ path: route.path, query, hash: route.hash })
}

function planSourceOperationAllowed() {
  if (!planNavigationMismatch.value) return true
  ElMessage.warning('这个来源已失效，请先清除定位后重新选择计划。')
  return false
}

async function focusCurrentPlanItem() {
  const itemId = focusedPlanItemId.value
  if (!itemId || loading.value || plansLoading.value || !currentPlan.value) return false
  await nextTick()
  await new Promise((resolve) => window.requestAnimationFrame(resolve))
  await new Promise((resolve) => window.setTimeout(resolve, 120))
  if (isConciseView.value) return weekBoardRef.value?.focusItem?.(itemId) || false
  const row = pageRoot.value?.querySelector('.source-focused-row')
  if (!row) return false
  row.setAttribute('tabindex', '-1')
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  row.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center', inline: 'nearest' })
  row.focus({ preventScroll: true })
  return true
}

async function openDetailedPlan() {
  if (!planSourceOperationAllowed()) return
  detailFocusItemId.value = ''
  setViewMode('detailed')
  loadCalibration(currentPlan.value?.course_id)
  await nextTick()
  const heading = pageRoot.value?.querySelector('#detailed-plan-heading')
  heading?.scrollIntoView({ behavior: 'auto', block: 'start' })
  heading?.focus({ preventScroll: true })
}

async function openPlanItemDetails(item) {
  if (!planSourceOperationAllowed()) return
  if (!item?.id) return
  detailFocusItemId.value = item.id
  setViewMode('detailed')
  await focusCurrentPlanItem()
}

async function generatePlan() {
  if (generating.value || loading.value || plansLoading.value || !planSourceOperationAllowed()) return
  if (!planForm.course_id || !planForm.exam_date) {
    ElMessage.warning('请选择课程和复习截止日期')
    return
  }
  if (!sourcesReady.value) {
    ElMessage.warning('请选择本次复习范围')
    return
  }
  if (planForm.exam_date < chinaLocalDateKey()) {
    ElMessage.warning('复习截止日期不能早于今天，请重新选择')
    return
  }
  if (!Number.isInteger(planForm.daily_minutes) || planForm.daily_minutes < 15 || planForm.daily_minutes > 1440) {
    ElMessage.warning('每天可用时间请填写 15 到 1440 分钟')
    return
  }
  generating.value = true
  generationError.value = ''
  sourceRefreshRequired.value = false
  try {
    const generated = await studyPlansApi.generate({
      course_id: planForm.course_id,
      exam_date: planForm.exam_date,
      daily_minutes: planForm.daily_minutes,
      title: planForm.title.trim() || null,
      material_sources: sourceSelection.value.material_sources,
      task_sources: sourceSelection.value.task_sources,
    })
    plans.value = [generated, ...plans.value]
    currentPlan.value = generated
    selectedPlanId.value = generated.id
    error.value = ''
    plansError.value = ''
    routePlanNotFound.value = false
    routePlanError.value = ''
    creatingPlan.value = false
    syncFormFromPlan(generated)
    detailFocusItemId.value = ''
    await router.replace({ path: '/study-plans', query: planLocation(generated) })
    ElMessage.success('复习计划已生成并保存')
  } catch (err) {
    generationError.value = err.message
    sourceRefreshRequired.value = ['PLAN_SOURCE_CHANGED', 'PLAN_SOURCE_UNAVAILABLE', 'EDIT_CONFLICT'].includes(err.code)
    ElMessage.error(err.message)
  } finally {
    generating.value = false
  }
}

function disabledBeforeToday(value) {
  return toDateInputValue(value) < chinaLocalDateKey()
}

function disabledAfterExam(value) {
  if (!currentPlan.value?.exam_date) return false
  const exam = new Date(`${currentPlan.value.exam_date}T23:59:59`)
  return value.getTime() > exam.getTime()
}

function sourceLabel(item) {
  const labels = []
  const sourceLabelFor = (kind, refs, legacyIds) => {
    const recordedRefs = (Array.isArray(refs) ? refs : [])
      .filter((ref) => positiveRouteId(ref?.source_id) && navigationKey(ref?.navigation_key))
    const recorded = recordedRefs.map((ref) => `#${ref.source_id}（已记录来源）`)
    if (recorded.length) labels.push(`${kind} ${recorded.join('、')}`)
    const verifiedIds = new Set(recordedRefs.map((ref) => String(ref.source_id)))
    const historical = (Array.isArray(legacyIds) ? legacyIds : [])
      .filter((id) => !verifiedIds.has(String(id)))
      .map((id) => `#${id}（历史未验证）`)
    if (historical.length) labels.push(`${kind} ${historical.join('、')}`)
  }
  sourceLabelFor('资料', item.source_material_refs, item.source_material_ids)
  sourceLabelFor('任务', item.source_task_refs, item.source_task_ids)
  return labels.join('、') || '课程范围'
}

function unscheduledReasonLabel(reason) {
  return ({
    deadline_passed: '截止时间已过',
    daily_capacity: '每日时间不足',
    daily_focus_limit: '每日主题已满',
    daily_capacity_and_focus_limit: '时间与主题数量均受限',
  })[reason] || '未能排入'
}

function unscheduledSourceKey(item) {
  return `${item?.source_type || ''}:${item?.source_id || ''}:${item?.navigation_key || ''}`
}

function canOpenUnscheduledSource(item) {
  return ['task', 'material'].includes(item?.source_type)
    && positiveMaterialId(item?.source_id) !== null
    && Boolean(navigationKey(item?.navigation_key))
}

async function openUnscheduledSource(item) {
  if (!canOpenUnscheduledSource(item) || unscheduledNavigationLoading.value) return
  const sourceRef = {
    source_type: item.source_type,
    source_id: String(item.source_id),
    navigation_key: item.navigation_key,
  }
  unscheduledNavigationLoading.value = unscheduledSourceKey(item)
  try {
    const resolved = await agentApi.resolveSourceRefs([sourceRef])
    const target = validatedSourceNavigationTarget(resolved, sourceRef)
    if (!target) {
      ElMessage.warning('该来源已删除或身份已变化，请从对应列表重新查找。')
      return
    }
    await router.push(target)
  } catch (err) {
    ElMessage.error(err?.message || '来源入口暂时无法解析，请稍后重试。')
  } finally {
    unscheduledNavigationLoading.value = ''
  }
}

async function persistPlan(items, successMessage, { includePlanFields = true } = {}) {
  if (!planSourceOperationAllowed() || !currentPlan.value || saving.value) return null
  const config = editRequestConfig(planBaseline.value)
  if (!config) {
    ElMessage.warning(preconditionMessage())
    return null
  }
  saving.value = true
  try {
    const payload = { items }
    if (includePlanFields) {
      payload.title = planForm.title.trim() || null
      payload.exam_date = planForm.exam_date
      payload.daily_minutes = planForm.daily_minutes
    }
    const saved = await studyPlansApi.update(currentPlan.value.id, payload, config)
    currentPlan.value = saved
    const index = plans.value.findIndex((plan) => plan.id === saved.id)
    if (index >= 0) plans.value[index] = saved
    syncFormFromPlan(saved)
    ElMessage.success(successMessage)
    return saved
  } finally {
    saving.value = false
  }
}

async function savePlan() {
  if (!planSourceOperationAllowed() || !currentPlan.value) return
  try {
    await persistPlan(currentPlan.value.items, '计划修改已保存')
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'STUDY_PLAN_NOT_FOUND')) {
      planConflict.value = { baseline: planBaseline.value, state: isEntityGone(err, 'STUDY_PLAN_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    ElMessage.error(err.message)
  }
}

async function completePlanItem(item) {
  if (!planSourceOperationAllowed() || !currentPlan.value || !item?.id || item.status === 'completed' || saving.value) return
  const itemExists = currentPlan.value.items?.some((candidate) => candidate.id === item.id)
  if (!itemExists) {
    ElMessage.error('未找到这条复习项，请重新读取计划。')
    return
  }
  const baseItems = persistedPlanItems.value.length ? clonePlanItems(persistedPlanItems.value) : clonePlanItems(currentPlan.value.items)
  const nextItems = baseItems.map((candidate) => (
    candidate.id === item.id ? { ...candidate, status: 'completed' } : candidate
  ))
  try {
    await persistPlan(nextItems, `已完成：${item.title || '复习项'}`, { includePlanFields: false })
    await nextTick()
    await new Promise((resolve) => window.requestAnimationFrame(resolve))
    await new Promise((resolve) => window.setTimeout(resolve, 120))
    const nextButton = pageRoot.value?.querySelector('.complete-button')
    const fallbackHeading = pageRoot.value?.querySelector('#concise-plan-heading')
    const focusTarget = nextButton || fallbackHeading
    focusTarget?.focus({ preventScroll: true })
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'STUDY_PLAN_NOT_FOUND')) {
      planConflict.value = { baseline: planBaseline.value, state: isEntityGone(err, 'STUDY_PLAN_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    ElMessage.error(`${err.message}；页面未更改完成状态。`)
  }
}

async function archivePlan() {
  if (!planSourceOperationAllowed() || !currentPlan.value) return
  const config = editRequestConfig(planBaseline.value)
  if (!config) {
    ElMessage.warning(preconditionMessage())
    return
  }
  const archivedPlanId = currentPlan.value.id
  try {
    await ElMessageBox.confirm(`确定归档“${currentPlan.value.title}”吗？归档后不会出现在当前计划列表中。`, '归档计划', { type: 'warning' })
    await studyPlansApi.archive(currentPlan.value.id, config)
    ElMessage.success('计划已归档')
    selectedPlanId.value = null
    await loadPlans(planForm.course_id, { respectRoutePlan: false })
    if (routeFilters.value.planId === archivedPlanId) {
      routePlanNotFound.value = true
      routePlanError.value = ''
    }
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'STUDY_PLAN_NOT_FOUND')) {
      planConflict.value = { baseline: planBaseline.value, state: isEntityGone(err, 'STUDY_PLAN_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

async function viewLatestPlan() {
  const id = planConflict.value?.baseline?.id
  if (!id) return
  try {
    const latest = await studyPlansApi.get(id)
    if (!latest) {
      planConflict.value = { ...planConflict.value, state: 'missing', latestFields: [{ label: '最新状态', value: '这份计划已不存在，不能继续覆盖。' }] }
      ElMessage.warning('这份计划已不存在；你的计划修改仍保留。')
      return
    }
    if (editBaseline(latest)?.navigation_key !== planConflict.value?.baseline?.navigation_key) {
      planConflict.value = { ...planConflict.value, state: 'replacement', latestFields: [{ label: '最新状态', value: '这个编号现在对应另一份计划，不能继续覆盖。' }] }
      ElMessage.warning('这个编号现在对应另一份计划；你的计划修改仍保留。')
      return
    }
    planConflict.value = { ...planConflict.value, latestFields: [
      { label: '计划名称', value: latest.title || '未命名计划' },
      { label: '复习至', value: latest.exam_date || '未填写' },
      { label: '每日学习时间', value: latest.daily_minutes ? `${latest.daily_minutes} 分钟` : '未填写' },
      { label: '学习安排', value: (latest.items || []).map((item) => `${item.date || '未安排日期'} · ${item.title || '未命名学习项'} · ${item.status === 'completed' ? '已完成' : item.status === 'in_progress' ? '进行中' : '未开始'} · ${item.minutes ?? '未填写'} 分钟\n${item.content || '未填写内容'}`).join('\n\n') || '暂无学习项' },
    ] }
    ElMessage.info('已读取最新内容；你的计划修改仍保留。')
  } catch (err) {
    if (isEntityGone(err, 'STUDY_PLAN_NOT_FOUND')) {
      planConflict.value = { ...planConflict.value, state: 'missing', latestFields: [{ label: '最新状态', value: '这份计划已不存在，不能继续覆盖。' }] }
      ElMessage.warning('这份计划已不存在；你的计划修改仍保留。')
      return
    }
    ElMessage.error(err.message)
  }
}

async function discardPlanDraft() {
  try {
    await ElMessageBox.confirm('这会放弃当前未保存的计划修改，并重新读取计划。是否继续？', '放弃本次修改', { type: 'warning', confirmButtonText: '放弃并重读', cancelButtonText: '保留修改' })
  } catch { return }
  planConflict.value = null
  await loadData()
}

async function resetCalibration() {
  if (!planForm.course_id || calibrationResetting.value) return
  const course = courses.value.find((item) => item.id === planForm.course_id)
  try {
    await ElMessageBox.confirm(
      `确定重置“${course?.name || '当前课程'}”的估时校准吗？重置后会保留任务记录，但系统将重新积累反馈。`,
      '重置课程估时依据',
      { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' },
    )
    calibrationResetting.value = true
    await agentApi.resetCalibration(planForm.course_id, { idempotency_key: calibrationResetKey(planForm.course_id) })
    ElMessage.success('本课程的估时校准依据已重置。')
    await loadCalibration(planForm.course_id)
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  } finally {
    calibrationResetting.value = false
  }
}

watch([knownExamDate, creatingPlan], useSuggestedExamDate)

watch(
  () => [routeFilters.value.planId, routeFilters.value.courseId],
  ([planId, courseId], [previousPlanId, previousCourseId]) => {
    // Opening the creator for the current course needs no page reload; preserve
    // the user's input if they start typing while the URL is being updated.
    if (!planId && wantsPlanCreator() && courseId === planForm.course_id) return
    if (planId !== previousPlanId || courseId !== previousCourseId) loadData()
  },
)

watch(
  () => [isConciseView.value, currentPlan.value?.id, focusedPlanItemId.value, routeFilters.value.view, loading.value, plansLoading.value],
  () => { focusCurrentPlanItem() },
  { flush: 'post' },
)

watch(
  () => [route.query.action, route.query.create, route.query.exam_date, route.query.daily_minutes, route.query.material_id, route.query.material_key],
  () => {
    if (!wantsPlanCreator()) return
    creatingPlan.value = true
    examDateEdited.value = false
    planForm.title = ''
    planForm.exam_date = routeExamDate() || knownExamDate.value || defaultExamDate()
    planForm.daily_minutes = routeDailyMinutes() || 60
  },
)

onMounted(loadData)
</script>

<style scoped>
.plan-date-presets { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 5px; }
.plan-date-presets button { min-height: 44px; padding: 6px 0; color: var(--ledger-link); background: transparent; border: 0; font: inherit; font-size: 12px; cursor: pointer; }
.plan-date-hint { margin: 0; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; }
.schedule-switch { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: -4px 0 22px; border-bottom: 1px solid var(--ledger-line); }
.schedule-switch > * { display: flex; align-items: center; gap: 8px; padding: 12px 2px; color: var(--ledger-muted); font-size: 14px; text-decoration: none; }
.schedule-switch > span { border-bottom: 2px solid var(--ledger-link); color: var(--ledger-link); font-weight: 600; }
.schedule-switch small { font-weight: 400; font-size: 12px; color: var(--ledger-muted); }
.schedule-switch a:focus-visible { outline: 2px solid var(--ledger-link); outline-offset: 3px; }
.study-plans-page { max-width: 100%; min-width: 0; }
.plan-source-expired { display: grid; gap: 8px; margin-bottom: 18px; padding: 16px; color: #7a4218; background: #fff8ed; border: 1px solid #efd0ab; border-left: 3px solid var(--ledger-amber); border-radius: 6px; }
.plan-source-expired strong { font-size: 14px; line-height: 1.5; }
.plan-source-expired p { margin: 0; color: #76583d; font-size: 13px; line-height: 1.6; }
.plan-source-expired .el-button { justify-self: start; }
.mb-18 { margin-bottom: 18px; }
.hero-copy { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 8px 20px; }
.hero-copy > p { grid-column: 1 / -1; }
.plan-form :deep(.el-input__wrapper) { min-height: 42px; box-sizing: border-box; }
.plan-form-sources { grid-column: 1 / -1; }
.plan-config, .calibration-card, .plan-card { margin-bottom: 22px; }
.plan-global-error { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 18px; }
.plan-global-error .el-alert { min-width: 0; flex: 1 1 auto; }
.plan-retry-button { min-height: 44px; flex: 0 0 auto; }
.concise-plan-shell { min-width: 0; margin-bottom: 22px; }
.concise-plan-toolbar { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 12px; }
.concise-plan-toolbar h2 { margin: 5px 0 0; color: var(--ledger-ink); font-family: inherit; font-size: 18px; }
.concise-plan-actions { display: flex; min-width: 300px; flex: 0 1 380px; flex-wrap: wrap; gap: 8px; }
.concise-plan-actions > .el-select { width: 260px !important; flex: 1 1 260px; }
.concise-plan-warnings { padding: 12px 0 0; }
.unscheduled-snapshot { margin-bottom: 16px; padding: 15px 17px; background: #fff9ee; border: 1px solid #ead6ae; border-left: 3px solid var(--ledger-amber); border-radius: 4px; }
.unscheduled-snapshot-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; }
.unscheduled-snapshot-heading h2 { margin: 5px 0 0; color: var(--ledger-ink); font-size: 16px; }
.unscheduled-snapshot-heading > span { max-width: 48ch; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; text-align: right; }
.unscheduled-list { display: grid; gap: 7px; margin: 13px 0 0; padding: 0; list-style: none; }
.unscheduled-list li { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; padding-top: 7px; border-top: 1px solid #eadfc9; }
.unscheduled-list li > div { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.unscheduled-list strong, .unscheduled-list span { overflow-wrap: anywhere; }
.unscheduled-list strong { color: var(--ledger-ink); font-size: 13px; }
.unscheduled-list span { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; }

.planner-hero { align-items: stretch; gap: 22px; margin-bottom: 12px; }
.hero-copy { min-width: 0; flex: 1 1 auto; }
.step-label {
  margin: 0;
  color: var(--ledger-indigo);
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1.4;
  text-transform: none;
}
.hero-copy h1 { margin-top: 0; }
.hero-copy > p:last-child { max-width: 66ch; }
.hero-status {
  display: flex;
  min-width: 230px;
  max-width: 300px;
  flex: 0 1 300px;
  flex-direction: column;
  justify-content: center;
  padding: 15px 17px;
  background: var(--ledger-paper);
  border: 1px solid var(--ledger-line);
  border-radius: 10px;
}
.hero-status.is-loading { border-left-color: var(--ledger-amber); }
.hero-status-label { color: var(--ledger-muted); font-size: 12px; letter-spacing: 0; line-height: 1.45; }
.hero-status strong {
  display: block;
  min-width: 0;
  margin-top: 7px;
  overflow-wrap: anywhere;
  color: var(--ledger-ink);
  font-family: inherit;
  font-size: 16px;
  line-height: 1.4;
  white-space: normal;
}
.hero-status-meta { display: block; min-width: 0; margin-top: 5px; overflow-wrap: anywhere; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; white-space: normal; }
.planner-export-actions { justify-content: flex-end; margin-bottom: 22px; }
.planner-export-actions .el-button { min-height: 44px; margin-left: 0; }

.config-heading, .calibration-heading { align-items: flex-start; gap: 18px; }
.card-heading-copy { min-width: 0; }
.card-heading-copy h2 { margin: 5px 0 0; }
.card-heading-copy > p { margin: 7px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.config-heading > .el-tag { flex: 0 0 auto; margin-top: 1px; }
.plan-form :deep(.el-form-item) { min-width: 0; margin: 0; }
.plan-form :deep(.el-form-item__content) { min-width: 0; }
.plan-form-title { grid-column: 1 / -1; }
.plan-form-submit { grid-column: 1 / -1; }
.plan-form-submit :deep(.el-form-item__content) { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; min-height: 44px; }
.plan-form-submit .el-button { min-height: 44px; }
.submit-hint { color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.minutes-field { display: flex; align-items: center; gap: 8px; min-width: 0; width: 100%; }
.minutes-field :deep(.el-input-number) { min-width: 0; flex: 1 1 auto; }
.form-suffix { flex: 0 0 auto; color: var(--ledger-muted); font-size: 12px; }
.plan-form-course :deep(.el-select__wrapper),
.toolbar-actions :deep(.el-select__wrapper) { height: auto; min-height: 44px; }
.plan-form-course :deep(.el-select__selection),
.toolbar-actions :deep(.el-select__selection) { min-width: 0; }
.plan-form-course :deep(.el-select__selected-item),
.toolbar-actions :deep(.el-select__selected-item) { max-width: 100%; height: auto; overflow: visible; line-height: 1.5; text-overflow: clip; white-space: normal; overflow-wrap: anywhere; }

.calibration-intro { margin-top: 7px !important; }
.calibration-actions { display: flex; min-width: 220px; flex: 0 1 290px; flex-direction: column; align-items: flex-end; gap: 8px; }
.selected-course-note { min-width: 0; max-width: 290px; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; text-align: right; white-space: normal; }
.calibration-actions .el-button { min-height: 44px; }
.calibration-message { margin-bottom: 14px; }
.calibration-loading, .calibration-empty { padding: 17px 0 1px; color: var(--ledger-muted); font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.calibration-loading { color: var(--ledger-amber-text); }
.calibration-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.calibration-metric { min-width: 0; min-height: 74px; padding: 12px 13px; background: #f5f8f7; border: 1px solid var(--ledger-line); border-left: 3px solid #c8ddd1; border-radius: 3px; }
.calibration-metric:nth-child(2) { border-left-color: #e1bd7b; }
.calibration-metric:nth-child(3) { border-left-color: #d79b9b; }
.calibration-metric span { display: block; color: var(--ledger-muted); font-size: 12px; line-height: 1.45; }
.calibration-metric strong { display: block; min-width: 0; margin-top: 7px; overflow-wrap: anywhere; color: var(--ledger-ink); font-size: 15px; line-height: 1.35; white-space: normal; }
.calibration-basis { display: flex; gap: 8px; margin-top: 14px; padding-top: 12px; color: var(--ledger-muted); border-top: 1px solid var(--ledger-line); font-size: 13px; line-height: 1.7; }
.calibration-basis-label { flex: 0 0 auto; color: var(--ledger-ink); font-weight: 700; }
.calibration-basis > span:last-child { min-width: 0; overflow-wrap: anywhere; white-space: normal; }

.table-heading { min-width: 0; flex: 1 1 auto; }
.table-heading h2 { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 5px; }
.table-heading-note { margin: 7px 0 0; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.plan-meta { min-width: 0; margin-top: 7px; color: var(--ledger-muted); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.toolbar-actions { align-items: center; justify-content: flex-end; }
.toolbar-actions .el-button { min-height: 44px; }
.study-plans-page :deep(.source-focused-row td) { background: #f1f7f3 !important; }
.study-plans-page :deep(.source-focused-row) { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 28%, transparent); outline-offset: -3px; }
.plan-summary { display: grid; grid-template-columns: 180px 180px minmax(260px, 1fr); gap: 22px; align-items: center; padding: 16px 22px; background: #f1f7f3; border-bottom: 1px solid var(--ledger-line); }
.summary-item { display: flex; min-width: 0; flex-direction: column; gap: 6px; padding-right: 18px; color: var(--ledger-muted); border-right: 1px solid var(--ledger-line); font-size: 12px; }
.summary-item strong { color: var(--ledger-ink); font-family: inherit; font-size: 17px; }
.summary-progress-label { display: flex; justify-content: space-between; margin-bottom: 7px; color: var(--ledger-muted); font-size: 12px; }
.summary-progress-label strong { color: var(--ledger-indigo); }
.summary-progress :deep(.el-progress-bar__outer), .summary-progress :deep(.el-progress-bar__inner) { border-radius: 2px; }
.summary-progress :deep(.el-progress-bar__outer) { background: #e5ede8; }
.summary-progress :deep(.el-progress-bar__inner) { background: var(--ledger-indigo); }
.plan-warnings { display: grid; gap: 8px; padding: 16px 22px 0; }
.plan-warnings-concise { padding-top: 12px; }
.plan-warnings-concise :deep(.el-alert) { align-items: flex-start; }
.plan-warnings :deep(.el-alert__title) { overflow-wrap: anywhere; white-space: normal; }
.plan-table-wrap { width: 100%; min-width: 0; overflow-x: auto; overflow-y: hidden; padding: 12px 10px 12px; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; }
.plan-table-scroll-hint { display: none; margin: 0 4px 10px; color: var(--ledger-muted); font-size: 12px; line-height: 1.55; }
.plan-table-wrap :deep(.el-table) { min-width: 1150px; }
.is-concise-view .plan-table-wrap :deep(.el-table) { min-width: 1025px; }
.plan-table-wrap :deep(.el-table td.el-table__cell) { vertical-align: top; }
.plan-table-wrap :deep(.el-table th.el-table__cell) { height: 42px; }
.item-title-input { margin-top: 8px; }
.plan-empty { padding: 70px 0; }
.plan-empty-message { margin: 0; color: var(--ledger-muted); line-height: 1.7; }
.plan-empty-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  margin-top: 16px;
  padding: 8px 18px;
  color: #ffffff;
  background: var(--ledger-indigo);
  border-radius: 4px;
  font-size: 13px;
  text-decoration: none;
}
.plan-empty-cta:hover { background: var(--ledger-link); }
.plan-empty-cta:focus-visible { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 42%, transparent); outline-offset: 3px; }

.plan-form :deep(.el-input__wrapper:focus-within),
.plan-form :deep(.el-textarea__inner:focus),
.plan-form :deep(.el-select .el-input.is-focus .el-input__wrapper),
.plan-table-wrap :deep(.el-input__wrapper:focus-within),
.plan-table-wrap :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--ledger-indigo) 25%, transparent), 0 0 0 1px var(--ledger-indigo) inset !important;
}
.study-plans-page :deep(.el-button:focus-visible) { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 42%, transparent); outline-offset: 3px; }
#concise-plan-heading:focus-visible, #detailed-plan-heading:focus-visible { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 42%, transparent); outline-offset: 3px; }

@media (max-width: 1200px) {
  .plan-summary { grid-template-columns: 150px 150px minmax(220px, 1fr); }
  .calibration-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 900px) {
  .hero-status { width: 100%; max-width: none; min-height: 88px; flex: 0 0 auto; }
  .plan-table-scroll-hint { display: block; }
  .plan-form :deep(.el-input__wrapper),
  .plan-form :deep(.el-textarea__inner),
  .plan-form :deep(.el-select__wrapper),
  .toolbar-actions :deep(.el-input__wrapper),
  .toolbar-actions :deep(.el-select__wrapper),
  .plan-table-wrap :deep(.el-input__wrapper),
  .plan-table-wrap :deep(.el-select__wrapper),
  .plan-table-wrap :deep(.el-textarea__inner) { min-height: 44px; }
  .plan-form :deep(.el-input-number .el-input__wrapper) { min-height: 46px; }
  .plan-form :deep(.el-input-number__increase),
  .plan-form :deep(.el-input-number__decrease) { width: 44px; }
  .plan-table-wrap :deep(.el-input-number__increase),
  .plan-table-wrap :deep(.el-input-number__decrease) { display: none; }
  .plan-table-wrap :deep(.el-input-number .el-input__wrapper) { padding-right: 11px; padding-left: 11px; }
}

@media (max-width: 720px) {
  .plan-global-error { flex-direction: column; }
  .plan-retry-button { width: 100%; }
}

@media (max-width: 900px) and (max-height: 480px) and (orientation: landscape) {
  .planner-hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(230px, .65fr); align-items: stretch; gap: 12px; }
  .hero-status { width: auto; min-height: 0; padding: 12px 14px; }
  .hero-copy > p:last-child { margin-top: 5px; line-height: 1.5; }
}

@media (max-width: 560px) {
  .planner-hero { gap: 14px; margin-bottom: 12px; }
  .hero-status { width: 100%; max-width: none; min-height: 88px; flex: 0 0 auto; }
  .planner-export-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; width: 100%; }
  .planner-export-actions .el-button { min-width: 0; padding-right: 8px; padding-left: 8px; white-space: normal; }
  .concise-plan-toolbar { align-items: flex-start; flex-direction: column; }
  .concise-plan-actions { width: 100%; min-width: 0; flex: 1 1 auto; }
  .concise-plan-actions > .el-select { width: 100% !important; flex: 1 1 100%; }
  .concise-plan-actions .el-button { width: 100%; }
  .config-heading, .calibration-heading { flex-direction: column; gap: 13px; }
  .config-heading > .el-tag { align-self: flex-start; }
  .plan-form :deep(.el-form-item) { width: 100%; margin-bottom: 15px; }
  .plan-form :deep(.el-form-item:last-child) { margin-bottom: 0; }
  .plan-form :deep(.el-form-item__label) { width: 94px !important; }
  .plan-form :deep(.el-form-item__content) { min-width: 0; }
  .plan-form :deep(.el-select), .plan-form :deep(.el-input), .plan-form :deep(.el-date-editor) { width: 100% !important; }
  .plan-form :deep(.el-input__wrapper),
  .plan-form :deep(.el-select__wrapper),
  .plan-form :deep(.el-textarea__inner) { min-height: 44px; }
  .plan-form :deep(.el-input-number) { max-width: 100%; }
  .plan-form-title, .plan-form-submit { grid-column: auto; }
  .plan-form-submit :deep(.el-form-item__content) { align-items: flex-start; flex-direction: column; gap: 7px; }
  .plan-form-submit .el-button { width: 100%; }
  .plan-empty-cta { width: 100%; }
  .calibration-actions { width: 100%; min-width: 0; align-items: flex-start; }
  .selected-course-note { max-width: 100%; text-align: left; }
  .calibration-actions .el-button { align-self: flex-start; }
  .calibration-metrics { grid-template-columns: minmax(0, 1fr); }
  .calibration-basis { align-items: flex-start; flex-direction: column; gap: 2px; }
  .table-toolbar { gap: 13px; }
  .table-heading h2 { gap: 6px; }
  .toolbar-actions { width: 100%; }
  .toolbar-actions > .el-select { width: 100% !important; flex: 1 1 100%; }
  .toolbar-actions :deep(.el-input__wrapper),
  .toolbar-actions :deep(.el-select__wrapper) { min-height: 44px; }
  .toolbar-actions .el-button { min-width: 0; flex: 1 1 calc(50% - 5px); }
  .plan-summary { grid-template-columns: 1fr; gap: 14px; padding: 15px 16px; }
  .summary-item { padding-right: 0; border-right: 0; }
  .plan-warnings { padding-right: 16px; padding-left: 16px; }
  .plan-table-wrap { padding: 10px 8px 10px; }
  .plan-table-wrap :deep(.el-input--small .el-input__wrapper),
  .plan-table-wrap :deep(.el-input-number--small .el-input__wrapper),
  .plan-table-wrap :deep(.el-select--small .el-input__wrapper),
  .plan-table-wrap :deep(.el-select__wrapper) { min-height: 44px; }
  .plan-table-wrap :deep(.el-input-number__increase),
  .plan-table-wrap :deep(.el-input-number__decrease) { display: none; }
  .plan-table-wrap :deep(.el-input-number .el-input__wrapper) { padding-right: 11px; padding-left: 11px; }
  .plan-table-wrap :deep(.el-textarea__inner) { min-height: 68px; }
}

@media (max-width: 390px) {
  .planner-export-actions .el-button { font-size: 12px; }
}

.plan-form { display: flex; flex-direction: column; gap: 22px; }
.plan-course-switch { margin-top: 10px; }
.plan-export-details { margin-bottom: 14px; }
.plan-export-details > summary { cursor: pointer; color: var(--ledger-muted); font-size: 13px; line-height: 1.7; }
.plan-export-details .planner-export-actions { margin: 10px 0 0; }
.plan-generation-error { width: 100%; color: #a12f25; }
.plan-generation-error p { margin: 0 0 8px; font-size: 13px; line-height: 1.65; }
.plan-form-section { width: 100%; min-width: 0; }
.plan-form-section h3 { display: flex; align-items: center; gap: 9px; margin: 0 0 14px; font-size: 15px; color: var(--ledger-ink); }
.plan-form-section h3 > span { display: grid; place-items: center; width: 23px; height: 23px; border-radius: 50%; background: #edf5ef; color: var(--ledger-indigo); font-size: 12px; }
.plan-form-section .plan-form-course { max-width: 560px; margin-bottom: 14px; }
.plan-time-fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; max-width: 600px; }
.duration-presets { display: flex; gap: 7px; margin-top: 10px; }
.duration-presets button { min-height: 44px; padding: 4px 12px; font: inherit; font-size: 13px; color: var(--ledger-muted); background: var(--ledger-paper); border: 1px solid var(--ledger-line); border-radius: 5px; cursor: pointer; }
.duration-presets button[aria-pressed="true"] { color: var(--ledger-indigo); background: #edf5ef; border-color: #a9cbb7; }
.duration-presets button:disabled { cursor: default; }
.capacity-note { max-width: 75ch; margin: 10px 0 0; }
.plan-extra-options { width: 100%; border-top: 1px solid var(--ledger-line); padding-top: 12px; }
.plan-extra-options summary, .plan-calibration-details > summary { cursor: pointer; min-height: 32px; color: var(--ledger-muted); font-size: 13px; line-height: 1.6; }
.plan-extra-options summary span { margin-left: 12px; font-size: 12px; }
.plan-extra-options .plan-form-title { max-width: 560px; margin-top: 10px; }
.plan-calibration-details { margin-bottom: 16px; }
.plan-import-link { flex-shrink: 0; color: var(--ledger-link); font-size: 13px; line-height: 1.7; }
.plan-form-submit { width: 100%; }
.plan-extra-options summary:focus-visible, .plan-calibration-details > summary:focus-visible, .duration-presets button:focus-visible, .plan-import-link:focus-visible { outline: 2px solid var(--ledger-indigo); outline-offset: 3px; }
@media (max-width: 560px) {
  .plan-form { display: flex; gap: 18px; }
  .plan-time-fields { grid-template-columns: 1fr; gap: 14px; }
  .plan-form :deep(.el-form-item__label) { width: auto !important; }
  .plan-form :deep(.el-form-item) { margin-bottom: 0; }
  .plan-form-section .plan-form-course { margin-bottom: 14px; }
  .plan-extra-options summary span { display: block; margin-left: 0; }
}
</style>
