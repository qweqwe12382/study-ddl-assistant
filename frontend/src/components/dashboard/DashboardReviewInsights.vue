<template>
  <section class="briefing-section activity-section" aria-labelledby="activity-title">
    <div class="briefing-section-heading">
      <div>
        <h3 id="activity-title">学习处理记录</h3>
        <span>只读时间线；记录来自系统，页面不会执行或改写</span>
      </div>
      <el-tag size="small" effect="plain">只读</el-tag>
    </div>
    <div class="activity-live-status" role="status" aria-live="polite" aria-atomic="true">
      {{ activityStatusMessage }}
    </div>
    <div v-if="data.activityError" class="activity-load-error" role="alert" aria-live="assertive">
      {{ activityErrorMessage }}
    </div>
    <div v-if="data.activityLoading && !data.activityLoaded" class="briefing-inline-empty activity-loading-state">
      正在加载学习处理记录…
    </div>
    <div v-else-if="data.activityError && !data.activityLoaded" class="briefing-inline-empty activity-load-failed">
      当前未显示处理记录；请稍后刷新学习建议后重试。
    </div>
    <div v-else-if="!data.activityLoaded" class="briefing-inline-empty activity-not-loaded">
      处理记录尚未加载；请先刷新学习建议后重试。
    </div>
    <template v-else-if="data.activity.available">
      <ol v-if="data.activity.items.length" class="activity-timeline" aria-label="学习处理记录">
        <li v-for="item in data.activity.items" :key="item.ui_key" class="activity-item">
          <span class="activity-marker" aria-hidden="true"></span>
          <div class="activity-body">
            <div class="activity-item-heading">
              <strong>{{ item.title || '学习处理' }}</strong>
              <el-tag size="small" effect="plain" :type="activityStatusType(item.status)">
                {{ activityStatusLabel(item.status) }}
              </el-tag>
            </div>
            <p v-if="item.description">{{ item.description }}</p>
            <div class="activity-meta">
              <time v-if="activityOccurredAt(item)" :datetime="activityOccurredAt(item)">{{ formatDateTime(item.occurred_at) }}</time>
              <span v-else>时间待补充</span>
              <span>{{ activityEventLabel(item.event_type) }}</span>
            </div>
            <div v-if="sources.activitySourceRef(item)" class="evidence-source-list compact" role="group" aria-label="活动来源入口">
              <span class="evidence-source-label">来源</span>
              <button
                v-if="sources.activitySourceCanNavigate(item)"
                type="button"
                class="evidence-source-button"
                :disabled="sources.isSourceNavigationLoading(sources.activitySourceRef(item))"
                :aria-label="sources.activitySourceButtonAriaLabel(item)"
                @click="sources.navigateSourceRef(sources.activitySourceRef(item))"
              >
                {{ sources.activitySourceButtonLabel(item) }}
              </button>
              <span v-else class="evidence-source-unavailable">{{ sources.activitySourceUnavailableLabel(item) }}</span>
            </div>
            <div v-else class="evidence-source-unavailable">{{ sources.activitySourceUnavailableLabel(item) }}</div>
          </div>
        </li>
      </ol>
      <div v-else class="briefing-inline-empty">暂无可展示的学习处理记录。</div>
    </template>
    <div v-else class="briefing-inline-empty">活动记录服务暂不可用；当前页面不会用其他数据替代活动时间线。</div>
  </section>

  <section class="briefing-section weekly-review-section">
    <div class="briefing-section-heading">
      <div>
        <h3>周度复盘</h3>
        <span>{{ data.weeklyReview.period_label }} · 只展示近 7 天已记录的数据</span>
      </div>
      <el-tag v-if="data.weeklyReview.evaluated_at" size="small" effect="plain">{{ formatDateTime(data.weeklyReview.evaluated_at) }}</el-tag>
    </div>
    <template v-if="data.weeklyReview.available">
      <div class="weekly-review-grid">
        <div
          v-for="metric in data.weeklyReview.metrics"
          :key="metric.key"
          class="weekly-review-metric"
          :class="{ 'metric-missing': metric.status === 'unknown' || metric.value === null }"
        >
          <span>{{ metric.label }}</span>
          <strong>{{ weeklyMetricValue(metric) }}</strong>
          <small>{{ metric.detail }}<template v-if="metric.status === 'partial'"> · 样本不完整</template></small>
        </div>
      </div>
      <div v-if="data.weeklyReview.missing_fields.length" class="weekly-missing-note">
        <strong>数据缺失：</strong>{{ data.weeklyReview.missing_fields.join('、') }}。缺失部分没有用估算值替代。
      </div>
      <div v-if="data.weeklyReview.notes.length" class="weekly-review-notes">
        <span>口径说明</span>{{ data.weeklyReview.notes.join('；') }}
      </div>
      <div class="weekly-next-actions">
        <div class="briefing-subheading">
          <strong>下周行动</strong>
          <span>最多 3 项，原因、来源、风险和执行方式均来自当前数据</span>
        </div>
        <div v-if="data.weeklyReview.next_actions.length" class="weekly-next-action-list">
          <article v-for="action in data.weeklyReview.next_actions" :key="action.ui_key" class="weekly-next-action-card">
            <div class="weekly-next-action-main">
              <div class="weekly-next-action-heading">
                <h4>{{ action.title || action.task_name || '下周学习行动' }}</h4>
                <el-tag :type="actions.riskType(action.risk_level)" size="small" effect="plain">{{ actions.riskLabel(action.risk_level) }}风险</el-tag>
              </div>
              <p>{{ action.reason || '系统还没有返回行动原因。' }}</p>
              <div class="weekly-next-action-meta">
                <span>来源：{{ actions.actionSourceLabel(action) }}</span>
                <span>处理方式：{{ actions.executionModeLabel(action.execution_mode) }}</span>
              </div>
              <EvidenceSourceList
                v-if="sources.actionSourceRefs(action).length"
                :items="sources.evidenceSourceItems(sources.actionSourceRefs(action), `下周行动${action.title || action.task_name || ''}`)"
                label="查看来源"
                compact
                @open="sources.navigateSourceRef"
              />
              <div v-else class="evidence-source-unavailable">暂时没有可查看的来源</div>
            </div>
            <div class="weekly-next-action-control">
              <el-button
                v-if="actions.isNavigableAction(action)"
                size="small"
                plain
                :disabled="actions.hasAgentActionLoading()"
                :aria-label="`查看${action.title || action.task_name || '下周行动'}来源`"
                @click="actions.navigateAction(action)"
              >
                查看来源
              </el-button>
              <el-button
                v-else-if="actions.isExecutableAction(action) && action.action_type === 'set_task_estimate'"
                size="small"
                plain
                :disabled="actions.hasAgentActionLoading()"
                :aria-label="`为${action.title || action.task_name || '下周行动'}补充预计用时`"
                @click="actions.openEstimateAction(action)"
              >
                补充估时
              </el-button>
              <el-button
                v-else-if="actions.isExecutableAction(action)"
                type="primary"
                size="small"
                :loading="actions.isActionLoading(actions.actionActionKey(action), 'execute')"
                :disabled="actions.isAnyActionLoading(actions.actionActionKey(action))"
                :aria-label="`${actions.actionButtonLabel(action)}：${action.title || action.task_name || '下周行动'}`"
                @click="actions.executeAction(action)"
              >
                {{ actions.actionButtonLabel(action) }}
              </el-button>
              <span v-else class="muted-action">{{ actions.actionUnavailableLabel(action) }}</span>
            </div>
          </article>
        </div>
          <div v-else class="briefing-inline-empty">当前没有已生成的下周行动；不会根据缺失数据猜测安排。</div>
      </div>
    </template>
    <div v-else class="briefing-inline-empty">当前还没有周度复盘数据，完成、逾期、计划偏差和估时偏差均不作推断。</div>
    <div class="weekly-history-block">
      <div class="briefing-subheading">
        <strong>复盘历史</strong>
        <span>只展示已保存的历史快照，不把当前数据当作历史</span>
      </div>
      <div v-if="data.weeklyHistory.snapshots.length" class="weekly-history-list">
        <article v-for="snapshot in data.weeklyHistory.snapshots" :key="snapshot.ui_key" class="weekly-history-card">
          <div class="weekly-history-heading">
            <div class="weekly-history-period">
              <strong>{{ snapshot.period_label }}</strong>
              <span>{{ snapshot.window_label }}</span>
            </div>
            <div class="weekly-history-tags">
              <el-tag :type="historySnapshotStatusType(snapshot.snapshot_status)" size="small" effect="plain">
                {{ historySnapshotStatusLabel(snapshot.snapshot_status) }}
              </el-tag>
              <el-tag :type="historySourceStatusType(snapshot.source_status)" size="small" effect="plain">
                {{ historySourceStatusLabel(snapshot.source_status) }}
              </el-tag>
            </div>
          </div>
          <div class="weekly-history-meta">
            <span v-if="snapshot.evaluated_at">生成于 {{ formatDateTime(snapshot.evaluated_at) }}</span>
            <span>规则：{{ snapshot.ruleset_label }}</span>
            <span>复盘口径：{{ snapshot.basis_label }}</span>
            <span>存储边界：{{ snapshot.storage_basis_label }}</span>
            <span>来源：{{ snapshot.source_label }}</span>
          </div>
          <div class="weekly-history-metrics">
            <div v-for="metric in snapshot.metrics" :key="metric.key" class="weekly-history-metric" :class="{ 'metric-missing': metric.status === 'unknown' || metric.value === null }">
              <span>{{ metric.label }}</span>
              <strong>{{ historyMetricValue(metric) }}</strong>
              <small>{{ historyMetricStatusLabel(metric.status) }} · {{ metric.detail }}</small>
            </div>
          </div>
          <p v-if="snapshot.summary_label" class="weekly-history-summary">{{ snapshot.summary_label }}</p>
          <EvidenceSourceList
            v-if="snapshot.source_refs.length"
            class="history-evidence-list"
            :items="sources.evidenceSourceItems(snapshot.source_refs, `复盘快照${snapshot.period_label || ''}`)"
            label="查看来源"
            :initial-limit="6"
            compact
            @open="sources.navigateSourceRef"
          />
          <div v-else class="evidence-source-unavailable">该历史快照没有可点击的来源入口。</div>
        </article>
      </div>
      <div v-else class="briefing-inline-empty">
        {{ data.weeklyHistory.available ? '当前还没有可展示的历史记录。' : '历史复盘尚未开启；当前页不把实时复盘当作历史。' }}
      </div>
    </div>
  </section>

  <section class="briefing-section rhythm-history-section" aria-labelledby="rhythm-history-title">
    <div class="briefing-section-heading">
      <div>
        <h3 id="rhythm-history-title">学习节奏历史比较</h3>
        <span>只比较已关闭的历史摘要，不把当前趋势当作历史</span>
      </div>
      <el-tag size="small" effect="plain" :type="rhythmHistoryStatusType(data.rhythmHistory.comparison.status)">
        {{ rhythmHistoryStatusLabel(data.rhythmHistory) }}
      </el-tag>
    </div>
    <div v-if="data.rhythmHistory.available_windows.length" class="rhythm-history-windows">
      <article v-for="(window, index) in data.rhythmHistory.available_windows.slice(0, 2)" :key="window.snapshot_id" class="rhythm-history-window">
        <div class="rhythm-history-window-heading">
          <strong>窗口 {{ index === 0 ? 'A（较新）' : 'B（较旧）' }}</strong>
          <span>{{ rhythmHistoryWindowLabel(window) }}</span>
        </div>
        <div class="rhythm-history-window-meta">
          <span>规则：{{ window.ruleset_version || '待补充' }}</span>
          <span>摘要：{{ window.rhythm_summary_version || '旧快照，无摘要' }}</span>
          <span>样本：{{ rhythmHistoryWindowSample(window) }}</span>
        </div>
      </article>
    </div>
    <div v-if="data.rhythmHistory.comparison.comparable" class="rhythm-history-change-list">
      <article v-for="change in data.rhythmHistory.comparison.changes" :key="change.code" class="rhythm-history-change">
        <div>
          <strong>{{ rhythmSignalLabel(change.code) }}</strong>
          <small>A：{{ rhythmSignalValue(change.newer_value, change.newer_status) }} · B：{{ rhythmSignalValue(change.older_value, change.older_status) }}</small>
        </div>
        <el-tag size="small" effect="plain">{{ rhythmDeltaLabel(change.delta) }}</el-tag>
      </article>
    </div>
    <div v-else class="briefing-inline-empty">{{ rhythmHistoryFallbackText(data.rhythmHistory) }}</div>
    <div v-if="data.rhythmHistory.comparison.reason_codes.length || data.rhythmHistory.comparison.limitations.length" class="rhythm-history-limits">
       <strong>当前限制：</strong>{{ rhythmHistoryReasonLabel(data.rhythmHistory) }}<template v-if="data.rhythmHistory.comparison.limitations.length"> · {{ data.rhythmHistory.comparison.limitations[0] }}</template>
    </div>
  </section>

  <section class="briefing-section learning-trends-section" aria-labelledby="learning-trends-title">
    <div class="briefing-section-heading">
      <div>
        <h3 id="learning-trends-title">学习节奏趋势</h3>
        <span>{{ data.learningTrends.window_label }} · 只展示已记录的数据</span>
      </div>
      <el-tag size="small" effect="plain" :type="trendStatusType(data.learningTrends.status)">{{ trendStatusLabel(data.learningTrends.status) }}</el-tag>
    </div>
    <template v-if="data.learningTrends.available">
      <div class="learning-trends-meta">
        <span>样本：{{ data.learningTrends.sample_count === null ? '待补充' : `${data.learningTrends.sample_count} 条` }}</span>
        <span>已知：{{ data.learningTrends.known_count === null ? '待补充' : data.learningTrends.known_count }}</span>
        <span>缺失：{{ data.learningTrends.unknown_count === null ? '待补充' : data.learningTrends.unknown_count }}</span>
        <span>最低样本：{{ data.learningTrends.minimum_sample_count === null ? '待补充' : data.learningTrends.minimum_sample_count }} · {{ data.learningTrends.timezone }}</span>
        <span v-if="data.learningTrends.evaluated_at">评估于 {{ formatDateTime(data.learningTrends.evaluated_at) }}</span>
      </div>
      <div v-if="data.learningTrends.signals.length" class="learning-trend-signal-list">
        <article v-for="signal in data.learningTrends.signals" :key="signal.ui_key" class="learning-trend-signal">
          <div class="learning-trend-signal-main">
            <div class="learning-trend-signal-heading">
              <strong>{{ signal.label }}</strong>
              <el-tag size="small" effect="plain" :type="trendStatusType(signal.status)">{{ trendStatusLabel(signal.status) }}</el-tag>
            </div>
            <p>{{ signal.summary || '当前还没有趋势解读。' }}</p>
            <small>{{ signal.sample_count === null ? '样本待补充' : `样本 ${signal.sample_count} 条` }} · {{ signal.evidence_label }}</small>
            <EvidenceSourceList
              v-if="sources.actionSourceRefs(signal).length"
              :items="sources.evidenceSourceItems(sources.actionSourceRefs(signal), `学习趋势${signal.label || ''}`)"
              label="查看来源"
              compact
              @open="sources.navigateSourceRef"
            />
          </div>
        </article>
      </div>
      <div v-else class="briefing-inline-empty">当前窗口没有足够的实际完成记录，趋势不作推断。</div>
      <div v-if="data.learningTrends.adjustment_candidates.length" class="learning-trend-candidates">
         <div class="briefing-subheading"><strong>可考虑的调整</strong><span>仅供你确认；不会自动修改课程或计划</span></div>
        <article v-for="candidate in data.learningTrends.adjustment_candidates" :key="candidate.ui_key" class="learning-trend-candidate">
          <div><strong>{{ candidate.title || '学习节奏调整建议' }}</strong><p>{{ candidate.reason || '当前还没有说明这项建议的原因。' }}</p></div>
          <el-tag size="small" effect="plain">确认</el-tag>
        </article>
      </div>
      <div v-if="data.learningTrends.limitations.length" class="learning-trends-limitations"><strong>限制：</strong>{{ data.learningTrends.limitations.join('；') }}</div>
    </template>
    <div v-else class="briefing-inline-empty">学习节奏趋势暂不可用；当前没有可验证的数据。</div>
  </section>

  <section class="briefing-section reminders-section">
    <div class="briefing-section-heading">
      <div>
        <h3>站内提醒</h3>
        <span>按高、中、低风险分级；高风险事实始终保留，其余按提醒偏好展示</span>
      </div>
    </div>
    <div v-if="data.reminders.length" class="reminder-list">
      <article v-for="reminder in data.visibleReminders" :key="reminder.ui_key" class="reminder-card" :class="`reminder-${reminder.severity}`">
        <div class="reminder-main">
          <div class="reminder-heading">
            <h4>{{ reminder.title || '学习提醒' }}</h4>
            <el-tag :type="reminderSeverityType(reminder.severity)" size="small" effect="plain">
              {{ actions.reminderSeverityLabel(reminder.severity) }}
            </el-tag>
          </div>
          <p>{{ reminder.reason || reminder.explanation || '当前还没有说明这条提醒的原因。' }}</p>
          <div class="reminder-meta">
            <span>来源：{{ actions.actionSourceLabel(reminder) }}</span>
            <span>处理：可导航或忽略</span>
          </div>
          <EvidenceSourceList
            v-if="sources.actionSourceRefs(reminder).length"
            :items="sources.evidenceSourceItems(sources.actionSourceRefs(reminder), `站内提醒${reminder.title || ''}`)"
            label="查看来源"
            compact
            @open="sources.navigateSourceRef"
          />
          <div v-else class="evidence-source-unavailable">暂时没有可查看的来源</div>
        </div>
        <div class="reminder-control">
          <el-button
            v-if="actions.isNavigableReminder(reminder)"
            size="small"
            plain
            :disabled="actions.hasAgentActionLoading()"
            :aria-label="`查看${reminder.title || '学习提醒'}来源`"
            @click="actions.navigateReminder(reminder)"
          >
            查看
          </el-button>
          <el-button
            v-else-if="actions.isExecutableAction(reminder)"
            type="primary"
            size="small"
            :loading="actions.isActionLoading(actions.actionActionKey(reminder), 'execute')"
            :disabled="actions.isAnyActionLoading(actions.actionActionKey(reminder))"
            :aria-label="`${actions.actionButtonLabel(reminder)}：${reminder.title || '学习提醒'}`"
            @click="actions.executeAction(reminder)"
          >
            {{ actions.actionButtonLabel(reminder) }}
          </el-button>
          <span v-else-if="!actions.isDismissibleReminder(reminder)" class="muted-action">{{ actions.actionUnavailableLabel(reminder) }}</span>
          <el-button
            v-if="actions.isDismissibleReminder(reminder)"
            size="small"
            :loading="actions.isActionLoading(actions.reminderActionKey(reminder), 'dismiss')"
            :disabled="actions.isAnyActionLoading(actions.reminderActionKey(reminder))"
            :aria-label="`忽略${reminder.title || '学习提醒'}`"
            @click="actions.dismissReminder(reminder)"
          >
            忽略
          </el-button>
        </div>
      </article>
    </div>
    <p v-if="data.isConciseView && data.reminders.length > data.visibleReminders.length" class="concise-list-note">
      另有 {{ data.reminders.length - data.visibleReminders.length }} 条普通提醒，可在完整视图查看；高风险提醒始终全部显示。
    </p>
    <div v-else class="briefing-inline-empty">暂无站内提醒；系统未返回的提醒不会在页面中补造。</div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { formatDateTime } from '../../utils/format'
import EvidenceSourceList from '../EvidenceSourceList.vue'

// Data and callbacks stay owned by the dashboard so refreshes, action locks
// and validated source navigation are shared with the rest of the page.
const props = defineProps({
  data: { type: Object, required: true },
  actions: { type: Object, required: true },
  sources: { type: Object, required: true },
})

const activityStatusMessage = computed(() => {
  if (props.data.activityLoading) {
    return props.data.activityLoaded
       ? '正在刷新学习处理记录，页面暂时保留上次成功加载的记录。'
       : '正在加载学习处理记录。'
  }
  if (props.data.activityError) {
    return props.data.activityLoaded
      ? `活动记录刷新失败，仍显示上次成功加载的 ${props.data.activity.items.length} 条记录。`
       : '处理记录加载失败，当前未显示处理数据。'
  }
   if (!props.data.activityLoaded) return '处理记录尚未加载。'
   if (!props.data.activity.available) return '处理记录暂不可用，未使用其他数据替代。'
   return `已加载 ${props.data.activity.items.length} 条学习处理记录。`
})

const activityErrorMessage = computed(() => {
  const detail = safeText(props.data.activityError, '服务暂时不可用，请稍后重试。')
  return props.data.activityLoaded
     ? `处理记录刷新失败：${detail} 当前仍显示上次成功加载的记录。`
     : `处理记录加载失败：${detail} 当前未显示处理记录。`
})

function safeText(value, fallback = '') {
  return typeof value === 'string' ? value.trim() : fallback
}

function weeklyMetricValue(metric) {
  if (!metric || metric.status === 'unknown') return '暂无数据'
  if (metric.value === null || metric.value === undefined) return '待补充'
  const value = Math.round(Number(metric.value))
  const prefix = metric.allow_negative && value > 0 ? '+' : ''
  return `${prefix}${value}${metric.unit || '项'}`
}

function reminderSeverityType(level) {
  return { high: 'danger', medium: 'warning', low: 'info' }[String(level || '').toLowerCase()] || 'info'
}

function historySourceStatusLabel(status) {
  return { complete: '来源完整', partial: '部分来源', unknown: '来源状态待补充' }[String(status || '').toLowerCase()] || '来源状态待补充'
}

function historySourceStatusType(status) {
  return { complete: 'success', partial: 'warning', unknown: 'info' }[String(status || '').toLowerCase()] || 'info'
}

function historySnapshotStatusLabel(status) {
  return { current: '当前窗口', closed: '已封存窗口', unknown: '快照状态待补充' }[String(status || '').toLowerCase()] || '快照状态待补充'
}

function historySnapshotStatusType(status) {
  return { current: 'primary', closed: 'info', unknown: 'warning' }[String(status || '').toLowerCase()] || 'warning'
}

function historyMetricStatusLabel(status) {
  return { known: '数据完整', partial: '样本不完整', unknown: '暂无可靠数据' }[String(status || '').toLowerCase()] || '数据状态待补充'
}

function historyMetricValue(metric) {
  if (!metric || metric.status === 'unknown') return '暂无数据'
  if (metric.value === null || metric.value === undefined) return '待补充'
  const value = Math.round(Number(metric.value))
  const prefix = metric.allow_negative && value > 0 ? '+' : ''
  return `${prefix}${value}${metric.unit || '项'}`
}

function trendStatusLabel(status) {
  return { known: '已知', partial: '部分已知', unknown: '未知' }[status] || '未知'
}

function trendStatusType(status) {
  return { known: 'success', partial: 'warning', unknown: 'info' }[status] || 'info'
}

function activityStatusLabel(status) {
  return {
    pending: '待处理',
    active: '进行中',
    generated: '已生成',
    confirmed: '已确认',
    recorded: '已记录',
    completed: '已完成',
    succeeded: '已完成',
    executed: '已执行',
    failed: '失败',
    expired: '已过期',
    ignored: '已忽略',
    dismissed: '已忽略',
    unavailable: '不可用',
  }[String(status || '').toLowerCase()] || '未知状态'
}

function activityStatusType(status) {
  return {
    pending: 'warning',
    active: 'warning',
    generated: 'info',
    confirmed: 'success',
    recorded: 'success',
    completed: 'success',
    succeeded: 'success',
    executed: 'success',
    failed: 'danger',
    expired: 'info',
    ignored: 'info',
    dismissed: 'info',
    unavailable: 'info',
  }[String(status || '').toLowerCase()] || 'info'
}

function activityEventLabel(eventType) {
  return {
    suggestion_created: '生成建议',
    suggestion_accepted: '确认建议',
    action_executed: '执行动作',
    action_failed: '动作失败',
    reminder_created: '创建提醒',
    reminder_dismissed: '忽略提醒',
    briefing_refreshed: '刷新简报',
    material_extraction_confirmed: '确认资料提取',
  }[String(eventType || '').toLowerCase()] || safeText(eventType, '活动')
}

function activityOccurredAt(item) {
  const value = safeText(item?.occurred_at)
  if (!value || Number.isNaN(new Date(value).getTime())) return ''
  return value
}

function rhythmSignalLabel(code) {
  return { learning_day_distribution: '学习日分布', longest_idle_gap: '最长空档', load_concentration: '负荷集中度', completion_pace: '完成节奏' }[code] || '学习节奏信号'
}

function rhythmHistoryWindowLabel(window) {
  const start = window.window_start ? String(window.window_start).slice(0, 10) : '日期待补充'
  const end = window.window_end ? String(window.window_end).slice(0, 10) : '日期待补充'
  return `${start} 至 ${end}（结束不含）`
}

function rhythmHistoryWindowSample(window) {
  if (window.known_count !== null) return `已知 ${window.known_count}${window.sample_count !== null ? ` / ${window.sample_count}` : ''}`
  return '待补充'
}

function rhythmSignalValue(value, status) {
  if (value === null || value === undefined || status === 'unknown') return '未知'
  return String(value)
}

function rhythmDeltaLabel(value) {
  if (value === null || value === undefined) return '差值未知'
  return `差值 ${value > 0 ? '+' : ''}${value}`
}

function rhythmHistoryStatusType(status) {
  return { known: 'success', partial: 'warning', unknown: 'info' }[status] || 'info'
}

function rhythmHistoryStatusLabel(history) {
  if (history.comparison.comparable) return history.comparison.status === 'partial' ? '可比·含未知' : '可比'
  return history.comparison.reason_codes.length ? '不可比·已降级' : '暂无可比窗口'
}

function rhythmHistoryReasonLabel(history) {
  const labels = {
    legacy_snapshot_missing_rhythm_summary: '旧快照缺少节奏摘要',
    rhythm_summary_caliber_mismatch: '两个窗口摘要口径不一致',
    insufficient_rhythm_summary_samples: '两个窗口各自已知样本不足 4 条',
    insufficient_closed_snapshots: '已关闭窗口不足 2 个',
    current_snapshot_excluded: '当前窗口不是已关闭历史，已排除',
    current_window_excluded: '当前窗口不是已关闭历史，已排除',
  }
  return history.comparison.reason_codes.map((code) => labels[code] || code).join('；') || '暂无可比较结论'
}

function rhythmHistoryFallbackText(history) {
  if (!history.available_windows.length) return '暂无可比较的历史窗口；不会把当前趋势或实时数据当作历史。'
  return `当前两个已关闭窗口不可比较：${rhythmHistoryReasonLabel(history)}。`
}
</script>

<style scoped>
.briefing-section { margin-top: 20px; padding-top: 18px; border-top: 1px solid #f0f2f6; }
.concise-list-note { margin: 10px 0 0; color: var(--ledger-muted, #667085); font-size: 13px; line-height: 1.6; }
.briefing-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.briefing-section-heading h3 { margin: 0; color: #344054; font-size: 14px; }
.briefing-section-heading span { display: block; margin-top: 4px; color: #667085; font-size: 12px; line-height: 1.5; }
.briefing-inline-empty { padding: 16px 4px 2px; color: #667085; font-size: 12px; line-height: 1.7; }
.evidence-source-list { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; margin-top: 9px; color: #667085; font-size: 12px; line-height: 1.5; }
.evidence-source-list.compact { margin-top: 7px; }
.evidence-source-label { flex: 0 0 auto; color: #667085; font-weight: 600; }
.evidence-source-button { max-width: 100%; min-height: 44px; padding: 8px 10px; color: var(--ledger-link, #4650c9); text-align: left; overflow-wrap: anywhere; background: #f3f8f5; border: 1px solid #e4e6ff; border-radius: 999px; cursor: pointer; font: inherit; line-height: 1.5; }
.evidence-source-button:hover:not(:disabled) { background: #eef0ff; border-color: #cfd3ff; }
.evidence-source-button:focus-visible { outline: 2px solid var(--ledger-indigo); outline-offset: 2px; }
.evidence-source-button:disabled { color: #a0a8b6; background: #f6f7f9; border-color: #e7e9ee; cursor: not-allowed; }
.evidence-source-unavailable { color: #667085; }
.evidence-source-unavailable { margin-top: 8px; font-size: 12px; line-height: 1.5; }
.history-evidence-list { margin-top: 10px; padding-top: 9px; border-top: 1px solid #f0f2f6; }
.muted-action { color: #667085; font-size: 12px; line-height: 1.5; }
.weekly-review-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 9px; margin-top: 14px; }
.weekly-review-metric { min-width: 0; padding: 12px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 10px; }
.weekly-review-metric > span { display: block; color: #667085; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.weekly-review-metric strong { display: block; margin-top: 8px; color: #344054; font-size: 18px; }
.weekly-review-metric small { display: block; margin-top: 5px; color: #667085; font-size: 12px; line-height: 1.5; }
.weekly-review-metric.metric-missing { background: #fffdf8; border-color: #f5ead1; }
.weekly-review-metric.metric-missing strong { color: #946020; font-size: 14px; }
.weekly-history-block { margin-top: 18px; padding-top: 16px; border-top: 1px solid #f0f2f6; }
.weekly-history-list { display: grid; gap: 8px; margin-top: 11px; }
.weekly-history-card { min-width: 0; padding: 11px 12px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 9px; }
.weekly-history-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.weekly-history-tags { display: flex; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; gap: 5px; }
.weekly-history-period { min-width: 0; }
.weekly-history-period strong { display: block; color: #344054; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.weekly-history-period span { display: block; margin-top: 3px; color: #667085; font-size: 12px; line-height: 1.5; }
.weekly-history-meta { display: flex; flex-wrap: wrap; gap: 5px 14px; margin-top: 8px; color: #667085; font-size: 12px; line-height: 1.5; }
.weekly-history-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; margin-top: 10px; }
.weekly-history-metric { min-width: 0; padding: 8px 9px; background: #fff; border: 1px solid #edf0f8; border-radius: 8px; }
.weekly-history-metric > span { display: block; color: #667085; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.weekly-history-metric strong { display: block; margin-top: 5px; color: #344054; font-size: 14px; }
.weekly-history-metric small { display: block; margin-top: 4px; color: #667085; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.weekly-history-metric.metric-missing { background: #fffdf8; border-color: #f5ead1; }
.weekly-history-metric.metric-missing strong { color: #946020; font-size: 12px; }
.weekly-history-summary { margin: 7px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }
.activity-timeline { position: relative; display: grid; gap: 8px; margin: 14px 0 0; padding: 0; list-style: none; }
.activity-timeline::before { position: absolute; top: 15px; bottom: 15px; left: 4px; width: 1px; background: #e5e8f5; content: ''; }
.activity-item { position: relative; display: flex; min-width: 0; gap: 10px; }
.activity-marker { z-index: 1; flex: 0 0 9px; width: 9px; height: 9px; margin-top: 14px; background: var(--ledger-indigo); border: 2px solid #eef0ff; border-radius: 50%; box-sizing: content-box; }
.activity-body { min-width: 0; flex: 1; padding: 10px 12px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 9px; }
.activity-item-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.activity-item-heading strong { min-width: 0; color: #344054; font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
.activity-body p { margin: 5px 0 0; color: #667085; font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.activity-meta { display: flex; flex-wrap: wrap; gap: 5px 14px; margin-top: 6px; color: #667085; font-size: 12px; line-height: 1.5; }
.activity-meta time { color: #667085; }
.activity-live-status { min-height: 1.5em; margin-top: 9px; color: #667085; font-size: 12px; line-height: 1.5; }
.activity-load-error { margin-top: 8px; padding: 8px 10px; color: #9c4a4a; background: #fff7f7; border: 1px solid #f4dada; border-radius: 8px; font-size: 13px; line-height: 1.65; }
.rhythm-history-windows, .rhythm-history-change-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.rhythm-history-window, .rhythm-history-change { min-width: 0; padding: 10px 12px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 9px; }
.rhythm-history-window-heading, .rhythm-history-change { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.rhythm-history-window-heading strong, .rhythm-history-change strong { color: #344054; font-size: 12px; }
.rhythm-history-window-heading span, .rhythm-history-window-meta, .rhythm-history-change small { color: #667085; font-size: 12px; line-height: 1.5; }
.rhythm-history-window-meta { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 7px; }
.rhythm-history-change-list { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.rhythm-history-change { align-items: center; }
.rhythm-history-change small { display: block; margin-top: 5px; }
.rhythm-history-limits { margin-top: 10px; padding-top: 9px; color: #667085; border-top: 1px solid #f0f2f6; font-size: 13px; line-height: 1.65; }
.rhythm-history-limits strong { color: #8d713b; }
.weekly-missing-note { margin-top: 12px; padding: 10px 12px; color: #8d713b; background: #fffaf0; border: 1px solid #f5ead1; border-radius: 9px; font-size: 13px; line-height: 1.65; }
.weekly-missing-note strong { color: #7b5d27; }
.weekly-review-notes { display: flex; gap: 8px; margin-top: 10px; color: #667085; font-size: 13px; line-height: 1.65; }
.weekly-review-notes > span { flex: 0 0 auto; color: #667085; font-weight: 600; }
.weekly-next-actions { margin-top: 18px; padding-top: 16px; border-top: 1px solid #f0f2f6; }
.briefing-subheading { display: flex; align-items: baseline; gap: 9px; }
.briefing-subheading strong { color: #344054; font-size: 13px; }
.briefing-subheading span { color: #667085; font-size: 12px; }
.weekly-next-action-list { display: grid; gap: 8px; margin-top: 11px; }
.weekly-next-action-card { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 13px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 10px; }
.weekly-next-action-main { min-width: 0; flex: 1; }
.weekly-next-action-heading { display: flex; align-items: center; justify-content: space-between; gap: 9px; }
.weekly-next-action-heading h4 { margin: 0; color: #344054; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.weekly-next-action-main p { margin: 7px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }
.weekly-next-action-meta, .reminder-meta { display: flex; flex-wrap: wrap; gap: 5px 15px; margin-top: 7px; color: #667085; font-size: 12px; line-height: 1.5; }
.weekly-next-action-control, .reminder-control { display: flex; align-items: center; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; gap: 7px; }
.weekly-next-action-control .el-button + .el-button, .reminder-control .el-button + .el-button { margin-left: 0; }
.reminder-list { display: grid; gap: 8px; margin-top: 14px; }
.learning-trend-signal-list, .learning-trend-candidates { display: grid; gap: 8px; margin-top: 14px; }
.learning-trends-meta { display: flex; flex-wrap: wrap; gap: 5px 15px; margin-top: 4px; color: #667085; font-size: 12px; line-height: 1.5; }
.learning-trend-signal, .learning-trend-candidate { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 11px 13px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 10px; }
.learning-trend-signal-main { min-width: 0; flex: 1; }
.learning-trend-signal-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.learning-trend-signal-heading strong, .learning-trend-candidate strong { color: #344054; font-size: 13px; }
.learning-trend-signal p, .learning-trend-candidate p { margin: 6px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }
.learning-trend-signal small { display: block; margin-top: 6px; color: #667085; font-size: 12px; line-height: 1.5; }
.learning-trends-limitations { margin-top: 12px; padding-top: 10px; color: #667085; border-top: 1px solid #f0f2f6; font-size: 13px; line-height: 1.65; }
.reminder-card { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 13px; background: #fbfcff; border: 1px solid #edf0f8; border-left-width: 3px; border-radius: 10px; }
.reminder-high { border-left-color: #e45656; }
.reminder-medium { border-left-color: #e7a43a; }
.reminder-low { border-left-color: #9aa3b1; }
.reminder-main { min-width: 0; flex: 1; }
.reminder-heading { display: flex; align-items: center; justify-content: space-between; gap: 9px; }
.reminder-heading h4 { margin: 0; color: #344054; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.reminder-main p { margin: 7px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }

@media (max-width: 900px) {
  .evidence-source-button { min-height: 44px; padding: 9px 11px; }
}

@media (max-width: 720px) {
  .weekly-review-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .weekly-history-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .rhythm-history-windows, .rhythm-history-change-list { grid-template-columns: minmax(0, 1fr); }
  .weekly-next-action-card, .reminder-card { align-items: flex-start; flex-direction: column; }
  .weekly-next-action-control, .reminder-control { width: 100%; justify-content: flex-start; }
}

@media (max-width: 560px) {
  .weekly-review-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .weekly-history-heading { align-items: flex-start; flex-direction: column; }
  .weekly-history-tags { justify-content: flex-start; }
  .weekly-review-notes, .briefing-subheading { align-items: flex-start; flex-direction: column; gap: 2px; }
}
</style>
