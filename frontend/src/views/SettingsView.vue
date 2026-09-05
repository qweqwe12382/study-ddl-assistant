<template>
  <div class="settings-page">
    <div class="page-intro">
      <div>
        <h1>设置</h1>
        <p>在这里管理课程、可用学习时间、站内提醒和外部 AI 的使用边界。</p>
      </div>
      <el-button v-if="isDetailedView && coursesState === 'ready'" type="primary" @click="openCreate">新增课程</el-button>
    </div>

    <section class="account-panel" aria-labelledby="account-panel-heading">
      <span class="account-panel-avatar" aria-hidden="true">{{ accountInitial }}</span>
      <div class="account-panel-copy">
        <p>当前账号</p>
        <h2 id="account-panel-heading">{{ authSession.user?.display_name }}</h2>
        <span>{{ authSession.user?.email }}{{ authSession.user?.is_admin ? ' · 实例管理员' : '' }}</span>
      </div>
      <div class="account-panel-boundary">此账号使用独立学习空间；退出后需要重新验证邮箱与密码。</div>
      <el-button plain :loading="loggingOut" :disabled="loggingOut" @click="signOut">退出登录</el-button>
    </section>

    <div v-if="error" class="settings-global-error">
      <el-alert :title="error" type="error" show-icon :closable="false" class="mb-18" />
      <el-button plain class="settings-retry-button" :loading="loading" :disabled="loading" @click="loadCourses">重新读取设置</el-button>
    </div>

    <section id="settings-rule-index" class="rule-book-overview" aria-labelledby="settings-rules-heading">
      <div class="rule-book-heading">
        <div>
          <p class="rule-book-kicker">设置索引 / 快速定位</p>
          <h2 id="settings-rules-heading">当前设置概览</h2>
          <p>状态来自已读取的数据；点击一项即可跳到对应设置。</p>
        </div>
        <span class="rule-book-mark" aria-hidden="true">RULES</span>
      </div>
      <nav class="rule-index" aria-label="设置规则区块">
        <a
          href="#settings-courses"
          class="rule-index-link"
          :class="`rule-index-link--${courseRuleState.tone}`"
          :aria-label="`课程：${courseRuleState.label}，定位到课程管理`"
        >
          <span class="rule-index-label">课程</span>
          <strong>{{ courseRuleState.label }}</strong>
          <span>{{ courseRuleState.detail }}</span>
        </a>
        <a
          href="#settings-capacity"
          class="rule-index-link"
          :class="`rule-index-link--${preferenceRuleState.tone}`"
          :aria-label="`学习容量：${preferenceRuleState.label}，定位到学习容量与偏好`"
        >
          <span class="rule-index-label">学习容量</span>
          <strong>{{ preferenceRuleState.label }}</strong>
          <span>{{ preferenceRuleState.detail }}</span>
        </a>
        <a
          href="#settings-reminders"
          class="rule-index-link"
          :class="`rule-index-link--${reminderRuleState.tone}`"
          :aria-label="`站内提醒：${reminderRuleState.label}，定位到站内提醒偏好`"
        >
          <span class="rule-index-label">站内提醒</span>
          <strong>{{ reminderRuleState.label }}</strong>
          <span>{{ reminderRuleState.detail }}</span>
        </a>
        <a
          href="#settings-external-ai"
          class="rule-index-link"
          :class="`rule-index-link--${llmRuleState.tone}`"
          :aria-label="`外部 AI：${llmRuleState.label}，定位到外部 AI 配置`"
        >
          <span class="rule-index-label">外部 AI</span>
          <strong>{{ llmRuleState.label }}</strong>
          <span>{{ llmRuleState.detail }}</span>
        </a>
      </nav>
    </section>

    <div class="settings-grid" :class="{ 'settings-grid--concise': isConciseView }">
      <el-card
        id="settings-courses"
        class="table-card settings-section"
        shadow="never"
        v-loading="loading"
        :aria-busy="loading"
        aria-labelledby="settings-courses-heading"
        tabindex="-1"
      >
        <div class="table-toolbar">
          <div class="table-heading">
            <h2 id="settings-courses-heading">课程管理</h2>
            <el-tag v-if="coursesState === 'ready'" size="small" effect="plain">{{ courses.length }}</el-tag>
            <span v-else class="table-state" role="status">{{ courseRuleState.label }}</span>
          </div>
          <el-button v-if="isConciseView && coursesState === 'ready' && courses.length" plain class="section-edit-button" @click="openDetailedSection('settings-courses')">编辑课程</el-button>
        </div>
        <el-alert
          v-if="courseError"
          :title="courseError"
          type="error"
          show-icon
          closable
          class="settings-inline-alert"
          @close="courseError = ''"
        />
        <div v-if="isConciseView" class="section-summary course-concise-summary">
          <template v-if="coursesState === 'ready'">
            <p v-if="courses.length">已记录 {{ courses.length }} 门课：{{ courseNamesSummary }}。</p>
            <p v-else>还没有课程。添加课程后，学习计划才能按课程安排。</p>
          </template>
          <p v-else>{{ courseRuleState.detail }}</p>
          <el-button v-if="coursesState === 'ready'" type="primary" plain class="section-summary-action" @click="openCreate">新增课程</el-button>
        </div>
        <div v-else class="table-wrap">
          <el-table :data="courses" :empty-text="courseTableEmptyText">
            <el-table-column prop="name" label="课程名称" min-width="220" class-name="course-name-cell" />
            <el-table-column prop="teacher" label="教师" width="160">
              <template #default="{ row }">{{ row.teacher || '未填写' }}</template>
            </el-table-column>
            <el-table-column prop="semester" label="学期" width="140">
              <template #default="{ row }">{{ row.semester || '未填写' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :aria-label="`编辑课程：${row.name}`" @click="openEdit(row)">编辑</el-button>
                <el-button link type="danger" :aria-label="`删除课程：${row.name}`" @click="removeCourse(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <el-card v-if="isDetailedView" id="settings-system-notes" class="content-card settings-section" shadow="never" aria-labelledby="settings-system-notes-heading">
        <div class="card-heading"><h2 id="settings-system-notes-heading">使用说明</h2><el-tag type="success">M8</el-tag></div>
        <div class="settings-note">
           <p><strong>已启用：</strong>课程、资料、截止任务和可编辑复习计划。</p>
           <p><strong>本地测试：</strong>可以使用下方按钮清空全部业务数据，从头开始测试。</p>
           <p><strong>数据空间：</strong>课程、资料、任务与计划按当前登录账号隔离。</p>
           <p><strong>提醒：</strong>复习计划按本地规则生成，建议根据实际进度手动调整。</p>
        </div>
        <div class="reset-zone">
          <div>
            <h3>测试数据重置</h3>
             <p>清空课程、资料、截止任务、复习计划和上传文件，仅保留数据库结构。</p>
          </div>
          <el-button type="danger" plain :loading="resetting" @click="resetTestData">重置测试数据</el-button>
        </div>
      </el-card>

      <el-card
        id="settings-capacity"
        class="content-card preference-card settings-section"
        shadow="never"
        v-loading="preferenceLoading"
        :aria-busy="preferenceLoading"
        aria-labelledby="settings-capacity-heading"
        tabindex="-1"
      >
        <div class="card-heading">
          <div>
            <h2 id="settings-capacity-heading">学习容量与偏好</h2>
             <p class="settings-help preference-intro">帮助系统判断安排是否来得及，并按课程重要程度调整顺序。</p>
          </div>
          <el-tag type="primary" effect="plain">规划约束</el-tag>
        </div>
        <el-alert v-if="preferenceError" :title="preferenceError" type="warning" show-icon closable class="mb-18" @close="preferenceError = ''" />
        <div v-if="isConciseView" class="section-summary capacity-concise-summary">
          <template v-if="preferenceState === 'ready' && preferenceSnapshot">
            <div class="summary-facts" aria-label="当前学习容量规则">
              <span><strong>{{ preferenceSnapshot.weekly_available_minutes }}</strong> 分钟/周</span>
              <span><strong>{{ preferenceSnapshot.daily_max_minutes }}</strong> 分钟/天</span>
              <span>预留 <strong>{{ preferenceSnapshot.buffer_percent }}%</strong> 缓冲</span>
            </div>
            <p>通常安排在{{ preferredSlotsLabel }}；{{ courseWeightsSummary }}。</p>
          </template>
          <p v-else>{{ preferenceRuleState.detail }}</p>
          <el-button v-if="preferenceState === 'ready' && preferenceSnapshot" plain class="section-edit-button" @click="openDetailedSection('settings-capacity')">编辑学习容量</el-button>
        </div>
        <template v-if="preferenceState === 'ready'">
          <el-form v-if="isDetailedView" :model="preferenceForm" label-width="105px" class="dialog-form preference-form">
          <div class="preference-form-grid">
            <el-form-item label="每周可用时间">
              <div class="number-with-unit">
                <el-input-number v-model="preferenceForm.weekly_available_minutes" :min="300" :max="10080" :step="30" controls-position="right" />
                <span class="unit-label">分钟</span>
              </div>
            </el-form-item>
            <el-form-item label="单日上限">
              <div class="number-with-unit">
                <el-input-number v-model="preferenceForm.daily_max_minutes" :min="30" :max="1440" :step="15" controls-position="right" />
                <span class="unit-label">分钟</span>
              </div>
            </el-form-item>
            <el-form-item label="缓冲比例">
              <div class="number-with-unit">
                <el-input-number v-model="preferenceForm.buffer_percent" :min="0" :max="50" :step="5" controls-position="right" />
                <span class="unit-label">%</span>
              </div>
            </el-form-item>
          </div>
          <el-form-item label="偏好时段">
            <el-checkbox-group v-model="preferenceForm.preferred_slots" aria-label="选择偏好学习时段">
              <el-checkbox value="morning">上午</el-checkbox>
              <el-checkbox value="afternoon">下午</el-checkbox>
              <el-checkbox value="evening">晚上</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <div class="course-weights-section">
            <div class="course-weights-heading">
              <div>
                <h3>课程排序权重</h3>
                <p>权重越高，在其他条件接近时越优先安排；范围为 0.5–2.0。</p>
              </div>
            </div>
            <div v-if="courses.length" class="course-weight-grid">
              <div v-for="course in courses" :key="course.id" class="course-weight-row">
                <span class="course-weight-name">{{ course.name }}</span>
                <div class="number-with-unit">
                  <el-input-number
                    v-model="courseWeights[String(course.id)]"
                    :min="0.5"
                    :max="2"
                    :step="0.1"
                    :precision="1"
                    controls-position="right"
                    :aria-label="`设置${course.name}的课程权重`"
                  />
                  <span class="unit-label">倍</span>
                </div>
              </div>
            </div>
            <div v-else class="course-weight-empty">还没有课程，新增课程后即可设置排序权重。</div>
          </div>
          </el-form>
          <div v-if="isDetailedView" class="preference-actions">
            <el-button plain :loading="preferenceResetting" @click="resetStudyPreferences">恢复默认</el-button>
            <el-button type="primary" :loading="preferenceSaving" @click="saveStudyPreferences">保存容量与偏好</el-button>
          </div>
        </template>
        <div v-else-if="isDetailedView" class="preference-unavailable" role="status">{{ preferenceRuleState.detail }}</div>
      </el-card>

      <el-card
        id="settings-reminders"
        class="content-card reminder-preference-card settings-section"
        shadow="never"
        v-loading="reminderPreferenceLoading"
        :aria-busy="reminderPreferenceLoading"
        aria-labelledby="settings-reminders-heading"
        tabindex="-1"
      >
        <div class="card-heading">
          <div>
            <h2 id="settings-reminders-heading">站内提醒偏好</h2>
            <p class="settings-help reminder-preference-intro">设置普通提醒的类别、最低风险级别和摘要频率；不会改写系统判定的风险事实。</p>
          </div>
          <el-tag type="warning" effect="plain">展示偏好</el-tag>
        </div>
        <el-alert v-if="reminderPreferenceError" :title="reminderPreferenceError" type="warning" show-icon closable class="mb-18" @close="reminderPreferenceError = ''" />
        <div v-if="isConciseView" class="section-summary reminder-concise-summary">
          <template v-if="reminderPreferenceState === 'ready' && reminderPreferenceSnapshot">
            <p>{{ reminderSummary }}</p>
          </template>
          <p v-else>{{ reminderRuleState.detail }}</p>
          <el-button v-if="reminderPreferenceState === 'ready' && reminderPreferenceAvailable && reminderPreferenceSnapshot" plain class="section-edit-button" @click="openDetailedSection('settings-reminders')">编辑提醒</el-button>
        </div>
        <template v-if="reminderPreferenceState === 'ready'">
          <el-form v-if="isDetailedView" :model="reminderPreferenceForm" label-width="105px" class="dialog-form reminder-preference-form">
            <el-form-item label="摘要频率">
              <el-radio-group v-model="reminderPreferenceForm.digest_frequency" aria-label="选择站内提醒摘要频率">
                <el-radio-button value="immediate">有变化时</el-radio-button>
                <el-radio-button value="daily">每日摘要</el-radio-button>
                <el-radio-button value="weekly">每周摘要</el-radio-button>
              </el-radio-group>
              <p class="form-help">保存为账号偏好；当前页面只展示系统筛选出的提醒，不代表通知已经发送。</p>
            </el-form-item>
            <el-form-item label="提醒类别">
              <el-checkbox-group v-model="reminderPreferenceForm.enabled_categories" aria-label="选择站内提醒类别">
                <el-checkbox v-for="option in reminderCategoryOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </el-checkbox>
              </el-checkbox-group>
              <p class="form-help">未勾选的普通类别不会显示；系统仍会保留记录，方便之后追溯。</p>
            </el-form-item>
            <el-form-item label="最低风险级别">
              <el-radio-group v-model="reminderPreferenceForm.minimum_risk_level" aria-label="选择站内提醒最低风险级别">
                <el-radio-button value="low">低及以上</el-radio-button>
                <el-radio-button value="medium">中及以上</el-radio-button>
                <el-radio-button value="high">仅高风险</el-radio-button>
              </el-radio-group>
              <p class="form-help">高风险事实不受此筛选影响，始终保留并展示。</p>
            </el-form-item>
          </el-form>
          <div v-if="isDetailedView" class="preference-actions reminder-preference-actions">
            <el-button type="primary" :loading="reminderPreferenceSaving" @click="saveReminderPreferences">保存提醒偏好</el-button>
          </div>
        </template>
        <div v-else-if="isDetailedView" class="preference-unavailable" role="status">{{ reminderRuleState.detail }}</div>
        <div class="reminder-safety-note">
          <el-tag type="danger" size="small" effect="plain">高风险保护</el-tag>
          <span v-if="reminderPreferenceForm.high_risk_policy === 'always_presented'">高风险提醒始终呈现；这里的偏好只会影响普通提醒。</span>
          <span v-else>高风险提醒保护尚未确认；本页不会把任何提醒改写成低风险。</span>
        </div>
      </el-card>

      <el-card
        id="settings-external-ai"
        class="content-card llm-card settings-section"
        shadow="never"
        v-loading="llmLoading"
        :aria-busy="llmLoading"
        aria-labelledby="settings-external-ai-heading"
        tabindex="-1"
      >
        <div class="card-heading">
          <h2 id="settings-external-ai-heading">外部 AI 配置</h2>
          <el-tag v-if="llmState === 'ready'" :type="llmSettings.api_key_configured ? 'success' : 'info'">{{ llmSettings.api_key_configured ? '已配置' : '未配置' }}</el-tag>
          <span v-else class="section-state" role="status">{{ llmRuleState.label }}</span>
        </div>
        <div class="external-ai-safety-note">
          <el-tag type="warning" size="small" effect="plain">按次授权</el-tag>
          <p>外部 AI 可选使用：只有你在资料处理中明确选择时才会调用；使用外部服务时，资料正文可能发送给该服务。</p>
        </div>
        <p v-if="isDetailedView" class="settings-help">API Key 只保存在后端本地 <code>.env</code>，页面不会显示完整密钥。</p>
        <el-alert v-if="llmError" :title="llmError" type="warning" show-icon closable class="mb-18" @close="llmError = ''" />
        <div v-if="isConciseView" class="llm-concise-summary">
          <p>当前配置状态：{{ llmRuleState.label }}。{{ llmRuleState.detail }}</p>
          <div class="llm-concise-actions">
            <el-button v-if="llmState === 'ready'" plain aria-label="在完整视图中配置外部 AI" @click="openDetailedSection('settings-external-ai')">编辑外部 AI</el-button>
          </div>
        </div>
        <template v-if="isDetailedView">
          <template v-if="llmState === 'ready'">
            <el-form :model="llmForm" label-width="105px" class="dialog-form">
            <el-form-item label="API 地址">
              <el-input v-model="llmForm.base_url" placeholder="可留空，使用默认地址" />
            </el-form-item>
            <el-form-item label="模型名称" required>
              <el-input v-model="llmForm.model" placeholder="例如：gpt-4o-mini" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="llmForm.api_key" type="password" show-password :placeholder="llmSettings.api_key_configured ? '已配置，留空则保持不变' : '粘贴 API Key（只保存到后端）'" />
            </el-form-item>
            <el-form-item label="请求超时">
              <el-input-number v-model="llmForm.timeout_seconds" :min="1" :max="300" controls-position="right" />
              <span class="unit-label">秒</span>
            </el-form-item>
            <el-form-item label="失败重试">
              <el-input-number v-model="llmForm.max_retries" :min="0" :max="5" controls-position="right" />
              <span class="unit-label">次</span>
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="llmForm.clear_api_key">清除已保存的 API Key</el-checkbox>
            </el-form-item>
            </el-form>
            <div class="llm-actions">
              <el-button type="primary" :loading="llmSaving" @click="saveLlmSettings">保存 AI 配置</el-button>
            </div>
          </template>
          <div v-else class="preference-unavailable" role="status">{{ llmRuleState.detail }}</div>
        </template>
      </el-card>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑课程' : '新增课程'" width="480px" destroy-on-close>
      <el-form :model="form" label-width="80px" class="dialog-form">
        <el-form-item label="课程名称" required><el-input v-model="form.name" placeholder="例如：数据结构" /></el-form-item>
        <el-form-item label="任课教师"><el-input v-model="form.teacher" placeholder="可选" /></el-form-item>
        <el-form-item label="学期"><el-input v-model="form.semester" placeholder="例如：2026 秋" /></el-form-item>
        <el-form-item label="主题色"><el-color-picker v-model="form.color" /></el-form-item>
      </el-form>
      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveCourse">保存</el-button>
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
  ElColorPicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElCheckbox,
  ElCheckboxGroup,
  ElMessage,
  ElMessageBox,
  ElRadioButton,
  ElRadioGroup,
  ElTable,
  ElTableColumn,
} from 'element-plus'

import { agentApi, coursesApi, resetApi, settingsApi, studyPreferencesApi } from '../api'
import { authSession, logout } from '../auth/session'
import { useViewMode } from '../composables/useViewMode'

const { isConciseView, isDetailedView, setViewMode } = useViewMode()
const route = useRoute()
const router = useRouter()
const loggingOut = ref(false)
const accountInitial = computed(() => authSession.user?.display_name?.trim()?.slice(0, 1)?.toUpperCase() || '学')

const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const error = ref('')
const dialogVisible = ref(false)
const editingId = ref(null)
const courses = ref([])
const coursesState = ref('pending')
const courseError = ref('')
const form = reactive(emptyForm())
const llmLoading = ref(false)
const llmSaving = ref(false)
const llmState = ref('pending')
const llmError = ref('')
const preferenceLoading = ref(false)
const preferenceSaving = ref(false)
const preferenceResetting = ref(false)
const preferenceState = ref('pending')
const preferenceError = ref('')
const reminderPreferenceLoading = ref(false)
const reminderPreferenceSaving = ref(false)
const reminderPreferenceError = ref('')
const reminderPreferenceState = ref('pending')
const reminderPreferenceAvailable = ref(false)
const preferenceSnapshot = ref(null)
const reminderPreferenceSnapshot = ref(null)
const loadRequestId = ref(0)
const llmSettings = reactive({
  base_url: '',
  model: '',
  api_key_configured: false,
  timeout_seconds: 30,
  max_retries: 2,
})
const llmForm = reactive({
  base_url: '',
  model: '',
  api_key: '',
  timeout_seconds: 30,
  max_retries: 2,
  clear_api_key: false,
})
const preferenceForm = reactive({
  weekly_available_minutes: 600,
  daily_max_minutes: 120,
  buffer_percent: 20,
  preferred_slots: ['evening'],
})
const courseWeights = ref({})
const reminderPreferenceForm = reactive({
  enabled_categories: [],
  minimum_risk_level: 'low',
  digest_frequency: 'immediate',
  high_risk_policy: null,
})
const reminderCategoryOptions = [
  { value: 'deadlines', label: '截止与逾期' },
  { value: 'plans', label: '计划偏差' },
  { value: 'materials', label: '资料待确认' },
  { value: 'estimation', label: '估时偏差' },
  { value: 'capacity', label: '学习容量' },
]

const courseRuleState = computed(() => {
  if (coursesState.value === 'pending') {
    return { label: '等待数据', detail: '还没有读取课程清单；课程数量尚未确定。', tone: 'pending' }
  }
  if (coursesState.value === 'loading') {
    return { label: '读取中', detail: '正在读取课程清单；课程数量尚未确定。', tone: 'loading' }
  }
  if (coursesState.value === 'error') {
    return { label: '读取失败', detail: courseError.value || '课程清单暂时不可用，请稍后重试。', tone: 'error' }
  }
  const count = courses.value.length
  return {
    label: count ? `${count} 门课程` : '暂无课程',
    detail: count ? '课程清单已读取，可以编辑课程。' : '课程清单已读取，目前还没有课程。',
    tone: 'ready',
  }
})

const preferenceRuleState = computed(() => {
  if (preferenceState.value === 'pending') {
    return { label: '等待数据', detail: '还没有读取学习容量和偏好。', tone: 'pending' }
  }
  if (preferenceState.value === 'loading') {
    return { label: '读取中', detail: '正在读取学习容量和偏好；当前值尚未确认。', tone: 'loading' }
  }
  if (preferenceState.value === 'error' || !preferenceSnapshot.value) {
    return { label: '读取失败', detail: preferenceError.value || '学习容量和偏好暂时不可用，请稍后重试。', tone: 'error' }
  }
  const snapshot = preferenceSnapshot.value
  const slots = snapshot.preferred_slots.length
    ? snapshot.preferred_slots.map((slot) => ({ morning: '上午', afternoon: '下午', evening: '晚上' }[slot])).join('、')
    : '未设置时段'
  return {
    label: '已加载',
    detail: `${snapshot.weekly_available_minutes} 分钟/周 · ${snapshot.daily_max_minutes} 分钟/日 · 缓冲 ${snapshot.buffer_percent}% · ${slots}`,
    tone: 'ready',
  }
})

const reminderRuleState = computed(() => {
  if (reminderPreferenceState.value === 'pending') {
    return { label: '等待数据', detail: '还没有读取站内提醒偏好。', tone: 'pending' }
  }
  if (reminderPreferenceState.value === 'loading') {
    return { label: '读取中', detail: '正在读取站内提醒偏好；当前值尚未确认。', tone: 'loading' }
  }
  if (reminderPreferenceState.value === 'unavailable') {
    return { label: '暂不可用', detail: reminderPreferenceError.value || '暂时没有可识别的提醒偏好设置。', tone: 'unavailable' }
  }
  if (reminderPreferenceState.value === 'error' || !reminderPreferenceSnapshot.value) {
    return { label: '读取失败', detail: reminderPreferenceError.value || '站内提醒偏好暂时不可用，请稍后重试。', tone: 'error' }
  }
  const snapshot = reminderPreferenceSnapshot.value
  const riskLabel = { low: '低及以上', medium: '中及以上', high: '仅高风险' }[snapshot.minimum_risk_level]
  const frequencyLabel = { immediate: '有变化时', daily: '每日摘要', weekly: '每周摘要' }[snapshot.digest_frequency]
  const categoryCount = snapshot.enabled_categories.length
  const categories = categoryCount ? `已启用 ${categoryCount} 类普通提醒` : '未启用普通提醒类别'
  return { label: '已加载', detail: `${frequencyLabel} · ${riskLabel} · ${categories}`, tone: 'ready' }
})

const llmRuleState = computed(() => {
  if (llmState.value === 'pending') {
    return { label: '等待数据', detail: '还没有读取外部 AI 配置；密钥状态尚未确定。', tone: 'pending' }
  }
  if (llmState.value === 'loading') {
    return { label: '读取中', detail: '正在读取外部 AI 配置；密钥状态尚未确定。', tone: 'loading' }
  }
  if (llmState.value === 'error') {
    return { label: '读取失败', detail: llmError.value || '外部 AI 配置暂时不可用，请稍后重试。', tone: 'error' }
  }
  const configured = llmSettings.api_key_configured
  return {
    label: configured ? '已配置' : '未配置',
    detail: configured ? '已读取 API Key 配置状态；密钥不会在页面显示。' : '已读取配置；当前未设置 API Key。',
    tone: 'ready',
  }
})

const courseNamesSummary = computed(() => {
  const names = courses.value.map((course) => course.name).filter(Boolean)
  if (names.length <= 3) return names.join('、')
  return `${names.slice(0, 3).join('、')}等 ${names.length} 门`
})

const preferredSlotsLabel = computed(() => {
  const labels = { morning: '上午', afternoon: '下午', evening: '晚上' }
  const slots = preferenceSnapshot.value?.preferred_slots || []
  return slots.map((slot) => labels[slot]).filter(Boolean).join('、') || '尚未设置的时段'
})

const courseWeightsSummary = computed(() => {
  if (!courses.value.length) return '新增课程后可设置优先顺序'
  return `${courses.value.length} 门课程都可在完整页面调整优先顺序`
})

const reminderSummary = computed(() => {
  const snapshot = reminderPreferenceSnapshot.value
  if (!snapshot) return reminderRuleState.value.detail
  const frequency = { immediate: '有变化时', daily: '每天一次', weekly: '每周一次' }[snapshot.digest_frequency]
  const risk = { low: '低风险及以上', medium: '中风险及以上', high: '只看高风险' }[snapshot.minimum_risk_level]
  const categories = snapshot.enabled_categories.length
  return `普通提醒：${frequency}汇总，显示${risk}，已选 ${categories} 类。`
})

const courseTableEmptyText = computed(() => {
  if (coursesState.value === 'pending' || coursesState.value === 'loading') return '正在读取课程列表…'
  if (coursesState.value === 'error') return courseError.value || '课程列表暂不可用，请稍后重试'
  return '还没有课程记录，点击“新增课程”开始记录'
})

function emptyForm() {
  return { name: '', teacher: '', semester: '', color: '#5964ed' }
}

function resetForm() {
  Object.assign(form, emptyForm())
  editingId.value = null
}

async function openDetailedSection(sectionId) {
  setViewMode('detailed')
  await nextTick()
  const target = document.getElementById(sectionId)
  if (!target) return
  target.focus({ preventScroll: true })
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  target.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' })
}

function firstDefined(source, keys, fallback = undefined) {
  if (!source || typeof source !== 'object') return fallback
  const key = keys.find((candidate) => source[candidate] !== undefined && source[candidate] !== null)
  return key ? source[key] : fallback
}

function isRecord(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function safeErrorMessage(value, fallback) {
  const raw = typeof value === 'string' ? value : value?.message
  if (!raw) return fallback
  return String(raw)
    .replace(/(api[_-]?key|token|secret|authorization)\s*[:=]\s*["']?[^"'，,；;\s]+["']?/gi, '$1 已省略')
    .replace(/\bsk-[A-Za-z0-9_-]{8,}\b/g, '密钥已省略')
}

function finiteNumber(value, fallback) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function integerValue(value, fallback) {
  const number = finiteNumber(value, fallback)
  return Math.round(number)
}

function normalizePreferredSlots(value) {
  if (Array.isArray(value)) return value.filter((slot) => ['morning', 'afternoon', 'evening'].includes(slot))
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) return normalizePreferredSlots(parsed)
    } catch (_err) {
      return value.split(',').map((slot) => slot.trim()).filter((slot) => ['morning', 'afternoon', 'evening'].includes(slot))
    }
  }
  return []
}

function bufferAsPercent(value) {
  const number = finiteNumber(value, NaN)
  if (!Number.isFinite(number)) return NaN
  return Math.round((number <= 1 ? number * 100 : number) * 100) / 100
}

function preferencePayload(value) {
  if (value?.preferences && typeof value.preferences === 'object') return value.preferences
  if (value?.data && typeof value.data === 'object' && !Array.isArray(value.data)) return value.data
  return value || {}
}

function normalizeCourseWeights(value) {
  const source = value && typeof value === 'object' && !Array.isArray(value) ? value : {}
  const next = {}
  courses.value.forEach((course) => {
    const key = String(course.id)
    const raw = finiteNumber(source[key], 1)
    next[key] = Math.min(2, Math.max(0.5, Math.round(raw * 10) / 10))
  })
  return next
}

function normalizeStudyPreferences(value) {
  const data = preferencePayload(value)
  if (!isRecord(data)) return { ok: false, status: 'error', error: '学习容量服务返回了无法识别的数据格式。' }

  const weekly = firstDefined(data, ['weekly_available_minutes', 'weekly_minutes', 'available_minutes_per_week'])
  const daily = firstDefined(data, ['daily_limit_minutes', 'daily_max_minutes', 'daily_capacity_minutes', 'daily_minutes'])
  const buffer = firstDefined(data, ['buffer_ratio', 'buffer_rate', 'buffer_percent'])
  const slots = firstDefined(data, ['preferred_time_slots', 'preferred_slots', 'preferred_periods'])
  const weights = data.course_weights
  if (weekly === undefined || daily === undefined || buffer === undefined || slots === undefined || weights === undefined) {
    return { ok: false, status: 'error', error: '学习容量服务返回的数据缺少必要字段。' }
  }

  const weeklyValue = integerValue(weekly, NaN)
  const dailyValue = integerValue(daily, NaN)
  const bufferValue = bufferAsPercent(buffer)
  if (!Number.isInteger(weeklyValue) || weeklyValue < 300 || weeklyValue > 10080) {
    return { ok: false, status: 'error', error: '学习容量服务返回了无效的每周可用时间。' }
  }
  if (!Number.isInteger(dailyValue) || dailyValue < 30 || dailyValue > 1440) {
    return { ok: false, status: 'error', error: '学习容量服务返回了无效的单日上限。' }
  }
  if (!Number.isFinite(bufferValue) || bufferValue < 0 || bufferValue > 50) {
    return { ok: false, status: 'error', error: '学习容量服务返回了无效的缓冲比例。' }
  }
  if (!(Array.isArray(slots) || typeof slots === 'string')) {
    return { ok: false, status: 'error', error: '学习容量服务返回了无效的偏好时段。' }
  }
  const preferredSlots = normalizePreferredSlots(slots)
  if (!preferredSlots.length) {
    return { ok: false, status: 'error', error: '学习容量服务返回的偏好时段为空。' }
  }
  if (!isRecord(weights)) {
    return { ok: false, status: 'error', error: '学习容量服务返回了无效的课程权重。' }
  }
  for (const weight of Object.values(weights)) {
    const number = finiteNumber(weight, NaN)
    if (!Number.isFinite(number) || number < 0.5 || number > 2) {
      return { ok: false, status: 'error', error: '学习容量服务返回了无效的课程权重。' }
    }
  }
  return {
    ok: true,
    status: 'ready',
    value: {
      weekly_available_minutes: weeklyValue,
      daily_max_minutes: dailyValue,
      buffer_percent: bufferValue,
      preferred_slots: preferredSlots,
      course_weights: weights,
    },
  }
}

function applyStudyPreferences(value) {
  const result = normalizeStudyPreferences(value)
  if (!result.ok) return result
  const data = result.value
  preferenceForm.weekly_available_minutes = data.weekly_available_minutes
  preferenceForm.daily_max_minutes = data.daily_max_minutes
  preferenceForm.buffer_percent = data.buffer_percent
  preferenceForm.preferred_slots = [...data.preferred_slots]
  courseWeights.value = normalizeCourseWeights(data.course_weights)
  preferenceSnapshot.value = {
    weekly_available_minutes: data.weekly_available_minutes,
    daily_max_minutes: data.daily_max_minutes,
    buffer_percent: data.buffer_percent,
    preferred_slots: [...data.preferred_slots],
  }
  return result
}

function reminderPreferencePayload(value) {
  if (value?.reminder_preferences && typeof value.reminder_preferences === 'object') return value.reminder_preferences
  if (value?.preferences && typeof value.preferences === 'object') return value.preferences
  if (value?.data && typeof value.data === 'object' && !Array.isArray(value.data)) return value.data
  return value || {}
}

function normalizeReminderPreferences(value) {
  const data = reminderPreferencePayload(value)
  const requiredKeys = ['enabled_categories', 'minimum_risk_level', 'digest_frequency', 'high_risk_policy']
  if (!isRecord(data) || !requiredKeys.some((key) => Object.prototype.hasOwnProperty.call(data, key))) {
    return { ok: false, status: 'unavailable', error: '提醒设置格式无法识别，本区块暂不可编辑。' }
  }
  if (!requiredKeys.every((key) => Object.prototype.hasOwnProperty.call(data, key))) {
    return { ok: false, status: 'unavailable', error: '提醒设置内容不完整，本区块暂不可编辑。' }
  }
  if (!Array.isArray(data.enabled_categories)) {
    return { ok: false, status: 'error', error: '提醒偏好服务返回了无效的提醒类别。' }
  }
  const categories = data.enabled_categories.filter((category) => reminderCategoryOptions.some((option) => option.value === category))
  if (categories.length !== data.enabled_categories.length || new Set(categories).size !== categories.length) {
    return { ok: false, status: 'error', error: '提醒偏好服务返回了无法识别的提醒类别。' }
  }
  if (!['low', 'medium', 'high'].includes(data.minimum_risk_level)) {
    return { ok: false, status: 'error', error: '提醒偏好服务返回了无效的最低风险级别。' }
  }
  if (!['immediate', 'daily', 'weekly'].includes(data.digest_frequency)) {
    return { ok: false, status: 'error', error: '提醒偏好服务返回了无效的摘要频率。' }
  }
  if (data.high_risk_policy !== 'always_presented') {
    return { ok: false, status: 'error', error: '提醒偏好服务未确认高风险提醒保护策略。' }
  }
  return {
    ok: true,
    status: 'ready',
    value: {
      enabled_categories: [...categories],
      minimum_risk_level: data.minimum_risk_level,
      digest_frequency: data.digest_frequency,
      high_risk_policy: data.high_risk_policy,
    },
  }
}

function applyReminderPreferences(value) {
  const result = normalizeReminderPreferences(value)
  if (!result.ok) {
    reminderPreferenceAvailable.value = false
    reminderPreferenceSnapshot.value = null
    Object.assign(reminderPreferenceForm, {
      enabled_categories: [],
      minimum_risk_level: 'low',
      digest_frequency: 'immediate',
      high_risk_policy: null,
    })
    return result
  }
  const data = result.value
  reminderPreferenceForm.enabled_categories = [...data.enabled_categories]
  reminderPreferenceForm.minimum_risk_level = data.minimum_risk_level
  reminderPreferenceForm.digest_frequency = data.digest_frequency
  reminderPreferenceForm.high_risk_policy = data.high_risk_policy
  reminderPreferenceSnapshot.value = { ...data, enabled_categories: [...data.enabled_categories] }
  reminderPreferenceAvailable.value = true
  return result
}

function normalizeLlmSettings(value) {
  if (!isRecord(value) || typeof value.api_key_configured !== 'boolean') {
    return { ok: false, error: '外部 AI 配置服务返回了无法识别的数据格式。' }
  }
  const timeout = finiteNumber(value.timeout_seconds, NaN)
  const retries = finiteNumber(value.max_retries, NaN)
  if (!Number.isFinite(timeout) || timeout < 1 || timeout > 300) {
    return { ok: false, error: '外部 AI 配置服务返回了无效的请求超时。' }
  }
  if (!Number.isInteger(retries) || retries < 0 || retries > 5) {
    return { ok: false, error: '外部 AI 配置服务返回了无效的失败重试次数。' }
  }
  if (value.base_url !== null && value.base_url !== undefined && typeof value.base_url !== 'string') {
    return { ok: false, error: '外部 AI 配置服务返回了无效的 API 地址。' }
  }
  if (value.model !== null && value.model !== undefined && typeof value.model !== 'string') {
    return { ok: false, error: '外部 AI 配置服务返回了无效的模型名称。' }
  }
  return {
    ok: true,
    value: {
      base_url: value.base_url || '',
      model: value.model || '',
      api_key_configured: value.api_key_configured,
      timeout_seconds: timeout,
      max_retries: retries,
    },
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(course) {
  Object.assign(form, {
    name: course.name,
    teacher: course.teacher || '',
    semester: course.semester || '',
    color: course.color || '#5964ed',
  })
  editingId.value = course.id
  dialogVisible.value = true
}

async function loadCourses() {
  const requestId = ++loadRequestId.value
  const isCurrentRequest = () => requestId === loadRequestId.value
  loading.value = true
  llmLoading.value = true
  preferenceLoading.value = true
  reminderPreferenceLoading.value = true
  error.value = ''
  courseError.value = ''
  llmError.value = ''
  preferenceError.value = ''
  reminderPreferenceError.value = ''
  coursesState.value = 'loading'
  llmState.value = 'loading'
  preferenceState.value = 'loading'
  reminderPreferenceState.value = 'loading'
  reminderPreferenceAvailable.value = false
  preferenceSnapshot.value = null
  reminderPreferenceSnapshot.value = null
  courses.value = []
  try {
    const [courseResult, llmResult, preferenceResult, reminderPreferenceResult] = await Promise.allSettled([
      coursesApi.list(),
      settingsApi.getLlm(),
      studyPreferencesApi.get(),
      agentApi.reminderPreferences(),
    ])
    if (!isCurrentRequest()) return

    if (courseResult.status === 'fulfilled' && Array.isArray(courseResult.value)) {
      courses.value = courseResult.value
      courseWeights.value = normalizeCourseWeights(courseWeights.value)
      coursesState.value = 'ready'
    } else {
      coursesState.value = 'error'
      courseError.value = courseResult.status === 'rejected'
        ? safeErrorMessage(courseResult.reason, '课程读取失败，请稍后重试。')
        : '课程服务返回了无法识别的数据格式。'
      courses.value = []
      courseWeights.value = {}
    }

    if (llmResult.status === 'fulfilled') {
      const applied = applyLlmSettings(llmResult.value)
      if (applied.ok) {
        llmState.value = 'ready'
      } else {
        llmState.value = 'error'
        llmError.value = applied.error
      }
    } else {
      llmState.value = 'error'
      llmError.value = safeErrorMessage(llmResult.reason, '外部 AI 配置读取失败，请稍后重试。')
    }

    if (preferenceResult.status === 'fulfilled') {
      const applied = applyStudyPreferences(preferenceResult.value)
      if (applied.ok) {
        preferenceState.value = 'ready'
      } else {
        preferenceState.value = 'error'
        preferenceError.value = applied.error
      }
    } else {
      preferenceState.value = 'error'
      preferenceError.value = safeErrorMessage(preferenceResult.reason, '学习容量读取失败，请稍后重试。')
    }

    if (reminderPreferenceResult.status === 'fulfilled') {
      const applied = applyReminderPreferences(reminderPreferenceResult.value)
      reminderPreferenceState.value = applied.ok ? 'ready' : applied.status
      if (!applied.ok) reminderPreferenceError.value = applied.error
    } else {
      reminderPreferenceState.value = 'error'
      reminderPreferenceError.value = safeErrorMessage(reminderPreferenceResult.reason, '站内提醒偏好读取失败，请稍后重试。')
      reminderPreferenceAvailable.value = false
    }

    const failedResourceCount = [courseError.value, llmError.value, preferenceError.value, reminderPreferenceError.value]
      .filter(Boolean)
      .length
    error.value = failedResourceCount
      ? '部分设置读取失败，请查看对应区块提示。'
      : ''
  } finally {
    if (!isCurrentRequest()) return
    loading.value = false
    llmLoading.value = false
    preferenceLoading.value = false
    reminderPreferenceLoading.value = false
  }
}

async function saveReminderPreferences() {
  if (reminderPreferenceState.value !== 'ready' || !reminderPreferenceAvailable.value) return
  reminderPreferenceSaving.value = true
  reminderPreferenceError.value = ''
  try {
    const result = await agentApi.updateReminderPreferences({
      enabled_categories: [...reminderPreferenceForm.enabled_categories],
      minimum_risk_level: reminderPreferenceForm.minimum_risk_level,
      digest_frequency: reminderPreferenceForm.digest_frequency,
    })
    const applied = applyReminderPreferences(result)
    if (!applied.ok) {
      reminderPreferenceState.value = applied.status
      reminderPreferenceError.value = applied.error
      ElMessage.error(applied.error)
      return
    }
    reminderPreferenceState.value = 'ready'
    ElMessage.success('提醒偏好已保存；高风险提醒仍会保留')
  } catch (err) {
    const message = safeErrorMessage(err, '提醒偏好保存失败，请稍后重试。')
    reminderPreferenceError.value = message
    ElMessage.error(message)
  } finally {
    reminderPreferenceSaving.value = false
  }
}

async function saveStudyPreferences() {
  if (preferenceState.value !== 'ready') return
  const weekly = integerValue(preferenceForm.weekly_available_minutes, 0)
  const daily = integerValue(preferenceForm.daily_max_minutes, 0)
  const bufferPercent = finiteNumber(preferenceForm.buffer_percent, NaN)
  if (!Number.isFinite(weekly) || weekly < 300 || weekly > 10080) {
    ElMessage.warning('每周可用时间应为 300 到 10080 分钟')
    return
  }
  if (!Number.isFinite(daily) || daily < 30 || daily > 1440) {
    ElMessage.warning('单日上限应为 30 到 1440 分钟')
    return
  }
  if (!Number.isFinite(bufferPercent) || bufferPercent < 0 || bufferPercent > 50) {
    ElMessage.warning('缓冲比例应为 0% 到 50%')
    return
  }
  if (!preferenceForm.preferred_slots.length) {
    ElMessage.warning('至少选择一个偏好时段')
    return
  }
  const courseWeightsPayload = {}
  for (const course of courses.value) {
    const key = String(course.id)
    const value = finiteNumber(courseWeights.value[key], 1)
    if (!Number.isFinite(value) || value < 0.5 || value > 2) {
      ElMessage.warning(`${course.name}的课程权重应为 0.5 到 2.0`)
      return
    }
    courseWeightsPayload[key] = Math.round(value * 10) / 10
  }
  const payload = {
    weekly_available_minutes: weekly,
    daily_limit_minutes: daily,
    buffer_ratio: bufferPercent / 100,
    preferred_time_slots: [...preferenceForm.preferred_slots],
    course_weights: courseWeightsPayload,
  }
  preferenceSaving.value = true
  preferenceError.value = ''
  try {
    const result = await studyPreferencesApi.update(payload)
    const applied = applyStudyPreferences(result)
    if (!applied.ok) {
      preferenceState.value = 'error'
      preferenceError.value = applied.error
      ElMessage.error(applied.error)
      return
    }
    preferenceState.value = 'ready'
    ElMessage.success('学习容量和偏好已保存')
  } catch (err) {
    const message = safeErrorMessage(err, '学习容量与偏好保存失败，请稍后重试。')
    preferenceError.value = message
    ElMessage.error(message)
  } finally {
    preferenceSaving.value = false
  }
}

async function resetStudyPreferences() {
  if (preferenceState.value !== 'ready') return
  preferenceResetting.value = true
  preferenceError.value = ''
  try {
    const result = await studyPreferencesApi.reset()
    const applied = applyStudyPreferences(result)
    if (!applied.ok) {
      preferenceState.value = 'error'
      preferenceError.value = applied.error
      ElMessage.error(applied.error)
      return
    }
    preferenceState.value = 'ready'
    ElMessage.success('学习容量和偏好已恢复默认')
  } catch (err) {
    const message = safeErrorMessage(err, '学习容量与偏好重置失败，请稍后重试。')
    preferenceError.value = message
    ElMessage.error(message)
  } finally {
    preferenceResetting.value = false
  }
}

function applyLlmSettings(value) {
  const result = normalizeLlmSettings(value)
  if (!result.ok) return result
  const data = result.value
  Object.assign(llmSettings, data)
  Object.assign(llmForm, {
    base_url: data.base_url,
    model: data.model,
    api_key: '',
    timeout_seconds: data.timeout_seconds,
    max_retries: data.max_retries,
    clear_api_key: false,
  })
  return result
}

async function saveLlmSettings() {
  if (llmState.value !== 'ready') return
  if (!llmForm.model.trim()) {
    ElMessage.warning('请填写模型名称')
    return
  }
  llmSaving.value = true
  try {
    const payload = {
      base_url: llmForm.base_url.trim(),
      model: llmForm.model.trim(),
      timeout_seconds: llmForm.timeout_seconds,
      max_retries: llmForm.max_retries,
      clear_api_key: llmForm.clear_api_key,
    }
    if (llmForm.api_key.trim()) payload.api_key = llmForm.api_key.trim()
    const result = await settingsApi.updateLlm(payload)
    const applied = applyLlmSettings(result)
    if (!applied.ok) {
      llmState.value = 'error'
      llmError.value = applied.error
      ElMessage.error(applied.error)
      return
    }
    llmState.value = 'ready'
    ElMessage.success('AI 配置已保存，现在可以在资料处理中选择外部 AI')
  } catch (err) {
    const message = safeErrorMessage(err, '外部 AI 配置保存失败，请稍后重试。')
    llmError.value = message
    ElMessage.error(message)
  } finally {
    llmSaving.value = false
  }
}

async function saveCourse() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写课程名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      teacher: form.teacher.trim() || null,
      semester: form.semester.trim() || null,
      color: form.color || null,
    }
    if (editingId.value) {
      await coursesApi.update(editingId.value, payload)
      ElMessage.success('课程已更新')
    } else {
      await coursesApi.create(payload)
      ElMessage.success('课程已添加')
    }
    dialogVisible.value = false
    await loadCourses()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function removeCourse(course) {
  try {
    await ElMessageBox.confirm(`删除课程可能同时删除关联资料和任务，确定删除“${course.name}”吗？`, '删除课程', { type: 'warning' })
    await coursesApi.remove(course.id)
    ElMessage.success('课程已删除')
    await loadCourses()
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

async function resetTestData() {
  try {
    await ElMessageBox.confirm(
      '这会删除全部课程、资料、截止任务、复习计划和上传文件，且不可恢复。确定继续吗？',
      '重置全部测试数据',
      {
        type: 'warning',
        confirmButtonText: '确认重置',
        cancelButtonText: '取消',
        distinguishCancelAndClose: true,
      },
    )
    resetting.value = true
    const result = await resetApi.all()
    await loadCourses()
    ElMessage.success(`已重置：${result.deleted_files} 个上传文件和全部业务数据`)
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  } finally {
    resetting.value = false
  }
}

let createCourseActionInFlight = false

async function consumeCreateCourseAction() {
  if (createCourseActionInFlight || coursesState.value !== 'ready' || route.query.action !== 'create-course') return
  createCourseActionInFlight = true
  try {
    openCreate()
    const query = { ...route.query }
    delete query.action
    await router.replace({ path: route.path, query, hash: route.hash })
  } catch {
    // Keep the dialog open if only the URL cleanup fails; the course form remains usable.
  } finally {
    createCourseActionInFlight = false
  }
}

async function signOut() {
  try {
    await ElMessageBox.confirm('退出后需要重新登录才能继续查看学习空间。', '退出登录', {
      confirmButtonText: '退出登录',
      cancelButtonText: '留在这里',
    })
    loggingOut.value = true
    await logout()
    await router.replace('/')
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err?.message || '退出登录失败')
  } finally {
    loggingOut.value = false
  }
}

watch([() => route.query.action, coursesState], () => {
  void consumeCreateCourseAction()
}, { immediate: true })

onMounted(loadCourses)
</script>

<style scoped>
.mb-18 { margin-bottom: 18px; }
.settings-page { min-width: 0; }
.account-panel { display: grid; grid-template-columns: auto minmax(180px, .7fr) minmax(260px, 1fr) auto; align-items: center; gap: 16px; margin-bottom: 18px; padding: 16px 18px; border: 1px solid #d8e0ed; border-radius: 10px; background: #fffefb; }
.account-panel-avatar { width: 43px; height: 43px; display: grid; place-items: center; border-radius: 13px; color: #fff; background: #3157e6; font-weight: 850; }
.account-panel-copy { min-width: 0; }
.account-panel-copy p { margin: 0 0 3px; color: #7b8599; font-size: 10px; font-weight: 750; letter-spacing: .08em; }
.account-panel-copy h2 { margin: 0; font-size: 15px; }
.account-panel-copy span { display: block; margin-top: 3px; overflow: hidden; color: #667085; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.account-panel-boundary { color: #667085; font-size: 12px; line-height: 1.6; }
.settings-global-error { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 18px; }
.settings-global-error .el-alert { min-width: 0; flex: 1 1 auto; margin-bottom: 0; }
.settings-global-error :deep(.el-alert__title) { overflow-wrap: anywhere; white-space: normal; }
.settings-retry-button { min-height: 44px; flex: 0 0 auto; }
.rule-book-overview {
  margin-bottom: 18px;
  padding: 20px;
  color: var(--ledger-paper, #fffefb);
  background: var(--ledger-ink, #1e2a44);
  border: 1px solid var(--ledger-ink, #1e2a44);
  border-radius: 6px;
  box-shadow: 0 5px 16px rgba(30, 42, 68, .12);
}
.rule-book-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.rule-book-heading > div { min-width: 0; }
.rule-book-kicker {
  margin: 0;
  color: #aeb9cf;
  font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .11em;
}
.rule-book-heading h2 { margin: 7px 0 0; color: #fffefb; font-family: "Aptos Display", "Microsoft YaHei", sans-serif; font-size: 19px; }
.rule-book-heading p:not(.rule-book-kicker) { max-width: 62ch; margin: 7px 0 0; color: #c1cadb; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.rule-book-mark { flex: 0 0 auto; color: #72809b; font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif; font-size: 12px; font-weight: 700; letter-spacing: .14em; }
.rule-index { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }
.rule-index-link {
  display: flex;
  min-width: 0;
  min-height: 102px;
  flex-direction: column;
  gap: 4px;
  padding: 13px 14px;
  color: #52617a;
  background: #fffefb;
  border: 1px solid #d9e0ea;
  border-left: 3px solid #aeb9cf;
  border-radius: 4px;
  transition: border-color .16s ease, background-color .16s ease, transform .16s ease;
}
.rule-index-link:hover { background: #f5f7fc; border-color: #b9c3d3; border-left-color: var(--ledger-indigo, #5964ed); transform: translateY(-1px); }
.rule-index-link:focus-visible { outline: 3px solid rgba(174, 182, 255, .9); outline-offset: 3px; }
.rule-index-label { color: #667085; font-size: 12px; line-height: 1.45; }
.rule-index-link strong { min-width: 0; overflow-wrap: anywhere; color: var(--ledger-ink, #1e2a44); font-size: 14px; line-height: 1.35; white-space: normal; }
.rule-index-link > span:last-child { min-width: 0; overflow-wrap: anywhere; color: #667085; font-size: 13px; line-height: 1.55; white-space: normal; }
.rule-index-link--loading { border-left-color: var(--ledger-indigo, #5964ed); }
.rule-index-link--ready { border-left-color: #357862; }
.rule-index-link--error { border-left-color: var(--ledger-coral, #c94c4c); }
.rule-index-link--unavailable { border-left-color: var(--ledger-amber, #c9822e); }
.settings-section { scroll-margin-block-start: 96px; }
.settings-section:target { outline: 3px solid rgba(89, 100, 237, .24); outline-offset: 4px; }
.settings-section:focus-visible { outline: 3px solid rgba(89, 100, 237, .72); outline-offset: 4px; }
.settings-inline-alert { margin: 14px 20px 0; }
.table-card :deep(.el-table__empty-text) { color: #667085; }
.settings-page :deep(.course-name-cell .cell) {
  min-width: 0;
  overflow: visible;
  overflow-wrap: anywhere;
  text-overflow: clip;
  white-space: normal;
  word-break: break-word;
  line-height: 1.5;
}
.settings-note { min-width: 0; overflow-wrap: anywhere; }
.settings-grid--concise { grid-template-columns: minmax(0, 1fr); }
.table-toolbar { gap: 12px; }
.table-heading { min-width: 0; }
.table-state, .section-state { min-width: 0; overflow-wrap: anywhere; color: var(--ledger-muted); font-size: 12px; line-height: 1.5; white-space: normal; }
.section-edit-button,
.section-summary-action,
.llm-concise-actions .el-button { min-height: 44px; }
.section-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
  margin-top: 2px;
  padding: 14px 16px;
  color: #475467;
  background: #f8faff;
  border: 1px solid #e2e8f4;
  border-radius: 8px;
}
.section-summary p { min-width: 0; margin: 0; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.section-summary > .el-button { flex: 0 0 auto; }
.summary-facts { display: flex; flex: 1 1 auto; flex-wrap: wrap; gap: 8px; min-width: 0; }
.summary-facts span { padding: 5px 8px; color: #50607a; background: #fffefb; border: 1px solid #e2e8f4; border-radius: 999px; font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; }
.summary-facts strong { color: var(--ledger-ink, #1e2a44); }
.capacity-concise-summary { flex-wrap: wrap; }
.capacity-concise-summary p { flex-basis: 100%; }
.course-concise-summary { margin: 14px 20px 20px; }
.reminder-concise-summary { margin-bottom: 12px; }
.reset-zone {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #f3c7c7;
  border-radius: 10px;
  background: #fff8f8;
}
.reset-zone h3 { margin: 0 0 6px; color: #b42318; font-size: 15px; }
.reset-zone p { margin: 0; color: #7a4b4b; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.preference-card { grid-column: 1 / -1; }
.preference-intro { margin: 6px 0 0; }
.preference-form { padding-top: 0; }
.preference-form-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.preference-form-grid .el-form-item { margin-bottom: 18px; }
.number-with-unit { display: flex; align-items: center; gap: 8px; }
.number-with-unit .el-input-number { width: 170px; }
.course-weights-section { margin-top: 4px; padding-top: 18px; border-top: 1px solid #f0f2f6; }
.course-weights-heading h3 { margin: 0; color: #344054; font-size: 14px; }
.course-weights-heading p { margin: 5px 0 0; color: #667085; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.course-weight-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.course-weight-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; padding: 10px 12px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 9px; }
.course-weight-name { min-width: 0; color: #475467; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; white-space: normal; }
.course-weight-row .number-with-unit { flex-shrink: 0; }
.course-weight-row .number-with-unit .el-input-number { width: 120px; }
.course-weight-empty { margin-top: 14px; padding: 14px 4px 2px; color: #667085; font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.preference-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 2px; }
.reminder-preference-card { grid-column: 1 / -1; }
.reminder-preference-intro { margin: 6px 0 0; }
.reminder-preference-form { padding-top: 0; }
.reminder-preference-form .el-form-item { margin-bottom: 18px; }
.reminder-preference-form .el-checkbox-group { display: flex; flex-wrap: wrap; gap: 8px 18px; }
.form-help { margin: 6px 0 0; color: #667085; font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.reminder-safety-note { display: flex; align-items: flex-start; gap: 9px; min-width: 0; margin-top: 2px; padding: 11px 12px; color: #7a5d2e; background: #fffaf0; border: 1px solid #f5ead1; border-radius: 9px; font-size: 13px; line-height: 1.65; }
.reminder-safety-note > span { min-width: 0; overflow-wrap: anywhere; white-space: normal; }
.reminder-preference-actions { margin-top: 16px; }
.preference-unavailable { padding: 14px 4px 2px; color: #667085; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.llm-card { grid-column: 1 / -1; }
.settings-help { margin: 0 0 18px; color: #667085; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.external-ai-safety-note {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  margin: 2px 0 14px;
  padding: 11px 12px;
  color: #7a5d2e;
  background: #fffaf0;
  border: 1px solid #f5ead1;
  border-radius: 9px;
}
.external-ai-safety-note p { min-width: 0; margin: 0; font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.llm-concise-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-top: 2px;
  padding: 14px 16px;
  color: #475467;
  background: #f7f8ff;
  border: 1px solid #e2e5fa;
  border-radius: 8px;
}
.llm-concise-summary p { min-width: 0; margin: 0; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.llm-concise-actions { flex: 0 0 auto; }
.llm-concise-actions .el-button { min-height: 44px; }
.unit-label { margin-left: 8px; color: #667085; font-size: 13px; }
.llm-actions { display: flex; justify-content: flex-end; margin-top: 2px; }
:global(html) { scroll-padding-top: 96px; }
@media (prefers-reduced-motion: reduce) {
  :global(html) { scroll-behavior: auto; }
  .rule-index-link { transition: none; }
  .rule-index-link:hover { transform: none; }
}
@media (max-width: 900px) {
  .rule-index { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .settings-page :deep(.el-input__wrapper),
  .settings-page :deep(.el-select__wrapper),
  .settings-page :deep(.el-textarea__inner),
  .settings-page :deep(.el-checkbox),
  .settings-page :deep(.el-radio-button__inner) { min-height: 44px; }
  .settings-page :deep(.el-input-number__increase),
  .settings-page :deep(.el-input-number__decrease) { display: none; }
  .settings-page :deep(.el-input-number .el-input__wrapper) { padding-right: 11px; padding-left: 11px; }
  .settings-page :deep(.el-input-number .el-input__inner) { text-align: left; }
}
@media (max-width: 720px) {
  .account-panel { grid-template-columns: auto minmax(0, 1fr); }
  .account-panel-boundary { grid-column: 1 / -1; }
  .account-panel > .el-button { grid-column: 1 / -1; width: 100%; min-height: 44px; }
  .settings-global-error { flex-direction: column; }
  .settings-retry-button { width: 100%; }
  .reset-zone { align-items: flex-start; flex-direction: column; }
  .preference-form-grid { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .course-weight-grid { grid-template-columns: minmax(0, 1fr); }
  .preference-actions { justify-content: flex-start; flex-wrap: wrap; }
  .reminder-safety-note { align-items: flex-start; }
  .llm-card { grid-column: auto; }
  .section-summary { flex-wrap: wrap; }
}
@media (max-width: 560px) {
  .rule-book-overview { padding: 16px; }
  .rule-book-mark { display: none; }
  .rule-index { grid-template-columns: minmax(0, 1fr); margin-top: 15px; }
  .rule-index-link { min-height: 0; }
  .settings-inline-alert { margin-right: 16px; margin-left: 16px; }
  .preference-card :deep(.el-form-item__label),
  .reminder-preference-card :deep(.el-form-item__label),
  .llm-card :deep(.el-form-item__label) {
    width: 100% !important;
    padding: 0 0 6px;
    line-height: 1.4;
    text-align: left;
  }
  .preference-card :deep(.el-form-item__content),
  .reminder-preference-card :deep(.el-form-item__content),
  .llm-card :deep(.el-form-item__content) {
    min-width: 0;
    margin-left: 0 !important;
  }
  .settings-page :deep(.el-input__wrapper),
  .settings-page :deep(.el-select__wrapper),
  .settings-page :deep(.el-textarea__inner) { min-height: 44px; }
  .settings-page :deep(.el-checkbox) { min-height: 44px; }
  .settings-page :deep(.el-radio-button__inner) { min-height: 44px; }
  .page-intro > .el-button,
  .table-card .el-button,
  .section-edit-button,
  .section-summary-action,
  .reset-zone .el-button,
  .preference-actions .el-button,
  .llm-actions .el-button { min-height: 44px; }
  .number-with-unit { min-width: 0; flex-wrap: wrap; }
  .number-with-unit .el-input-number { width: min(100%, 220px); }
  .course-weight-row { align-items: flex-start; flex-direction: column; }
  .course-weight-name { width: 100%; white-space: normal; }
  .course-weight-row .number-with-unit,
  .course-weight-row .number-with-unit .el-input-number { width: 100%; }
  .reminder-preference-form :deep(.el-radio-group) { display: flex; flex-wrap: wrap; gap: 6px; }
  .reminder-preference-form :deep(.el-radio-button) { margin: 0; }
  .reminder-preference-form :deep(.el-radio-button__inner) { min-height: 44px; padding: 10px 12px; }
  .llm-concise-summary { flex-direction: column; padding: 12px; }
  .llm-concise-actions,
  .llm-concise-actions .el-button { width: 100%; }
  .section-summary { padding: 12px; }
  .section-summary > .el-button { width: 100%; }
  .summary-facts { gap: 6px; }
  .external-ai-safety-note { flex-direction: column; gap: 6px; }
}
@media (max-width: 390px) {
  .rule-book-heading h2 { font-size: 17px; }
  .rule-index-link { padding: 12px; }
  .reminder-safety-note { flex-direction: column; gap: 6px; }
}
</style>
