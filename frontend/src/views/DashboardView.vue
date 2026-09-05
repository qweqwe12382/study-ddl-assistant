<template>
  <div v-loading="loading" :aria-busy="loading">
    <div class="page-intro">
      <div>
        <h1>今天先做最重要的一步</h1>
        <p>学伴管家把待确认事项、今日任务和风险集中在一张行动单里。</p>
      </div>
      <div v-if="dashboard.study_streak_days >= 1" class="streak-chip" role="status" aria-label="连续学习天数">
        <span class="streak-flame" aria-hidden="true">🔥</span>
        <span>连续学习 <strong>{{ dashboard.study_streak_days }}</strong> 天</span>
      </div>
    </div>

    <div id="dashboard-first-learning-loop-priority" class="first-learning-loop-slot"></div>

    <TodayFocusStage
      :state="focusStageState"
      :focus="focusStageItem"
      :attention-items="focusAttentionItems"
      :summary-items="focusSummaryItems"
      :details-count="focusDetailsCount"
      @retry="refreshAgent(false)"
      @act-focus="handleFocusAction"
      @act-attention="handleFocusAttention"
      @open-details="openDetailedLedger"
    />

    <div v-if="isConciseView" class="concise-flow-grid" aria-label="今日学习流">
      <DeadlineFlow
        :state="deadlineFlowState"
        :tasks="upcomingTasks"
        :busy-material-keys="deadlineMaterialBusyKeys"
        @open-task="openDeadlineTask"
        @open-material="openDeadlineMaterial"
      />
      <AiInboxShortcut
        :state="aiInboxShortcutState"
        :ready-count="aiInboxShortcutState === 'ready' ? inbox.ready_count : null"
        :review-count="aiInboxShortcutState === 'ready' ? inbox.needs_review_count : null"
        :failed-count="aiInboxShortcutState === 'ready' ? inbox.failed_count : null"
        @upload="openMaterialUpload"
        @open-inbox="openLearningInbox"
      />
    </div>

    <div id="dashboard-first-learning-loop-default" class="first-learning-loop-slot"></div>
    <Teleport defer :to="firstLearningLoopTarget">
      <FirstLearningLoop
        :state="dashboardState"
        :concise="isConciseView"
        :compact="isConciseView"
        :progress="dashboard"
        :material-source-available="Boolean(firstLoopMaterialRef)"
        @retry="loadDashboard"
        @navigate="navigateFirstLearningLoop"
        @open-material-source="openFirstLearningMaterial"
      />
    </Teleport>

    <el-alert v-if="error" :title="error" type="error" show-icon closable role="alert" @close="error = ''" />
    <el-alert v-if="isDetailedView && !agent.suggestions.length && dashboard.next_action" :title="dashboard.next_action" type="info" show-icon class="dashboard-action" />

    <el-card
      v-if="isDetailedView"
      id="detailed-learning-ledger"
      class="agent-center-card"
      shadow="never"
      aria-labelledby="agent-center-title"
      tabindex="-1"
    >
      <div class="agent-center-heading">
        <div>
          <div class="agent-kicker">AGENT CENTER</div>
          <div class="agent-title-row">
            <h2 id="agent-center-title">学习助手</h2>
            <el-tag type="primary" effect="plain" size="small">待确认 {{ agentPendingDisplay }}</el-tag>
          </div>
          <p class="agent-description">根据临近截止时间和任务状态，给出需要你确认的安排调整。</p>
        </div>
        <el-button
          type="primary"
          plain
          :loading="agentLoading"
          :disabled="agentLoading || hasAgentActionLoading()"
          aria-label="刷新学习助手建议"
          @click="refreshAgent(false)"
        >
          刷新建议
        </el-button>
      </div>

      <el-alert
        v-if="agentMessage.text"
        :title="agentMessage.text"
        :type="agentMessage.type"
        show-icon
        closable
        class="agent-message"
        @close="clearAgentMessage"
      />

      <nav class="learning-ledger-index" aria-label="今日安排导航">
        <div class="ledger-index-heading">
          <div>
            <span class="ledger-index-kicker">LEARNING LEDGER / TODAY</span>
            <strong>今日导航</strong>
          </div>
          <span>跳到对应区块</span>
        </div>
        <div class="ledger-index-tabs">
          <template v-for="entry in learningLedgerIndex" :key="entry.target">
            <a
              v-if="entry.targetReady"
              class="ledger-index-tab"
              :href="`#${entry.target}`"
              :aria-label="`${entry.label}：${entry.status}`"
            >
              <span class="ledger-index-tab-label">{{ entry.label }}</span>
              <span class="ledger-index-tab-status">{{ entry.status }}</span>
            </a>
            <span v-else class="ledger-index-tab ledger-index-tab-disabled" aria-disabled="true">
              <span class="ledger-index-tab-label">{{ entry.label }}</span>
              <span class="ledger-index-tab-status">{{ entry.status }}</span>
            </span>
          </template>
        </div>
      </nav>

      <div
        class="detailed-data-status"
        :class="`is-${detailedDataState}`"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {{ detailedDataStatusMessage }}
      </div>

      <div v-if="agentLoading && !briefingLoaded" class="briefing-loading" role="status" aria-live="polite">正在整理资料和今天的安排…</div>
      <template v-else>
        <section id="today-decision-desk" class="decision-desk-section" aria-labelledby="decision-desk-title" tabindex="-1">
          <div class="decision-desk-heading">
            <div>
              <div class="decision-desk-kicker">TODAY / DECISION DESK</div>
              <h3 id="decision-desk-title">今日确认台</h3>
              <p>先看最需要你确认的一步；这里只提供入口，不会自动执行。</p>
            </div>
            <span class="decision-desk-limit">最多 5 项 · 仅查看</span>
          </div>
          <div v-if="decisionQueue.length" class="decision-queue" role="list" aria-label="今日待确认事项">
            <article
              v-for="(decision, index) in visibleDecisionQueue"
              :key="decision.decision_id"
              class="decision-card"
              :class="`decision-card-${decision.priority}`"
              role="listitem"
            >
              <div class="decision-card-rail" aria-hidden="true">
                <span class="decision-source-stamp">{{ decisionSourceTypeLabel(decision) }}</span>
                <span class="decision-rail-line"></span>
                <span class="decision-rail-arrow">→</span>
              </div>
              <div class="decision-card-main">
                <div class="decision-card-heading">
                  <div class="decision-card-context">
                    <span class="decision-order">{{ String(index + 1).padStart(2, '0') }}</span>
                    <span class="decision-reason">{{ decisionReasonLabel(decision.reason_code) }}</span>
                  </div>
                  <span class="decision-priority" :class="`decision-priority-${decision.priority}`">{{ decisionPriorityLabel(decision.priority) }}</span>
                </div>
                <h4>{{ decision.title }}</h4>
                <p class="decision-description">{{ decision.description }}</p>
                <div class="decision-next-step">
                  <span>下一步</span>
                  <strong>{{ decision.action_label }}</strong>
                </div>
                <div class="decision-source-group" role="group" :aria-label="`${decision.action_label}的来源入口`">
                  <span class="decision-source-label">查看依据</span>
                  <button
                    v-for="ref in decisionSourceRefs(decision)"
                    :key="sourceRefKey(ref)"
                    type="button"
                    class="decision-source-button"
                    :disabled="isSourceNavigationLoading(ref) || isSourceUnavailable(ref)"
                    :aria-label="`${decision.action_label}：打开${sourceRefDisplayLabel(ref)}`"
                    @click="navigateSourceRef(ref)"
                  >
                    {{ sourceRefButtonLabel(ref) }}
                  </button>
                </div>
              </div>
            </article>
          </div>
          <p v-if="isConciseView && decisionQueue.length > visibleDecisionQueue.length" class="concise-list-note">
            另有 {{ decisionQueue.length - visibleDecisionQueue.length }} 条待确认事项，可在完整视图查看。
          </p>
          <template v-if="!visibleDecisionQueue.length">
            <div v-if="decisionQueueStatus === 'empty'" class="decision-queue-empty">
              <strong>今天没有需要优先确认的事项。</strong>
              <span>出现新的资料、计划差异或容量风险后，这里会给出下一步入口。</span>
            </div>
            <div v-else-if="decisionQueueStatus === 'invalid'" class="decision-queue-empty decision-queue-invalid" role="status">
              <strong>部分事项信息不完整。</strong>
              <span>来源或字段未确认，已暂时隐藏这轮内容。</span>
            </div>
            <div v-else class="decision-queue-empty decision-queue-unavailable" role="status">
              <strong>今日确认列表暂不可用。</strong>
              <span>当前页面不会用其他数据替代，也不会自行拼接来源地址。</span>
            </div>
          </template>
        </section>

        <section id="learning-inbox" class="briefing-section inbox-section" aria-labelledby="learning-inbox-title" tabindex="-1">
          <div class="briefing-section-heading">
            <div>
              <h3 id="learning-inbox-title">学习收件箱</h3>
              <span>资料处理状态与待确认事项</span>
            </div>
          </div>
          <template v-if="inbox.available">
            <div class="inbox-count-grid">
              <div class="inbox-count ready"><span>可确认</span><strong>{{ inbox.ready_count }}</strong></div>
              <div class="inbox-count review"><span>待确认</span><strong>{{ inbox.needs_review_count }}</strong></div>
              <div class="inbox-count failed"><span>处理失败</span><strong>{{ inbox.failed_count }}</strong></div>
            </div>
            <div v-if="inbox.materials.length" class="inbox-sources">
              <span class="inbox-sources-label">可查看依据的资料</span>
              <button
                v-for="material in inbox.materials"
                :key="material.id || material.name"
                type="button"
                class="inbox-source-row"
                :aria-label="`查看资料${material.name}`"
                @click="goToBriefingMaterial(material)"
              >
                <span>{{ material.name }}</span>
                <el-tag size="small" effect="plain">{{ inboxStatusLabel(material.status) }}</el-tag>
              </button>
            </div>
            <div v-else class="briefing-inline-empty">暂时没有需要追踪的资料入口。</div>
          </template>
          <div v-else class="briefing-inline-empty">当前服务尚未返回收件箱摘要，原有建议仍可继续确认。</div>
        </section>

        <section id="today-actions" class="briefing-section today-section" aria-labelledby="today-actions-title" tabindex="-1">
          <div class="briefing-section-heading">
            <div>
              <h3 id="today-actions-title">今日三件事</h3>
              <span>最多 3 项，顺序由当前数据决定</span>
            </div>
          </div>
          <div v-if="todayActions.length" class="today-actions-grid">
            <article v-for="action in todayActions" :key="action.ui_key" class="today-action-card">
              <div class="today-action-heading">
                <div class="today-action-title-wrap">
                  <h4>{{ action.task_name || '待处理任务' }}</h4>
                  <span>{{ action.course_name || '未归类课程' }}</span>
                </div>
                <el-tag :type="riskType(action.risk_level)" size="small" effect="plain">{{ riskLabel(action.risk_level) }}风险</el-tag>
              </div>
              <p class="today-action-reason">{{ action.reason || '系统建议优先查看这项安排。' }}</p>
              <div class="today-action-meta">
                <span>预计：{{ minutesLabel(action.estimated_minutes) }}</span>
                <span>剩余：{{ minutesLabel(action.remaining_minutes) }}</span>
                <span>排入：{{ minutesLabel(action.counted_minutes) }}<template v-if="action.minute_source">（{{ minuteSourceLabel(action.minute_source) }}）</template></span>
                <span>建议时段：{{ slotLabel(action.suggested_slot) }}</span>
              </div>
              <div class="today-sort-basis"><strong>排序原因</strong>{{ sortBasisLabel(action.sort_basis) }}</div>
              <EvidenceSourceList
                v-if="actionSourceRefs(action).length"
                :items="evidenceSourceItems(actionSourceRefs(action), `今日行动${action.task_name || ''}`)"
                label="查看来源"
                @open="navigateSourceRef"
              />
              <div v-else class="evidence-source-unavailable">暂时没有可查看的来源</div>
              <div class="today-action-controls">
                <el-button
                  v-if="isNavigableAction(action)"
                  size="small"
                  plain
                  :aria-label="`查看${action.task_name || '行动'}来源`"
                  @click="navigateAction(action)"
                >
                  查看来源
                </el-button>
                <el-button
                  v-else-if="isExecutableAction(action) && action.action_type === 'set_task_estimate'"
                  size="small"
                  plain
                  :disabled="hasAgentActionLoading()"
                  :aria-label="`为${action.task_name || '任务'}补充预计用时`"
                  @click="openEstimateAction(action)"
                >
                  补充估时
                </el-button>
                <el-button
                  v-else-if="isExecutableAction(action)"
                  type="primary"
                  size="small"
                  :loading="isActionLoading(actionActionKey(action), 'execute')"
                  :disabled="isAnyActionLoading(actionActionKey(action))"
                  :aria-label="`${actionButtonLabel(action)}：${action.task_name || '行动'}`"
                  @click="executeAction(action)"
                >
                  {{ actionButtonLabel(action) }}
                </el-button>
                <span v-else class="muted-action">{{ actionUnavailableLabel(action) }}</span>
              </div>
            </article>
          </div>
          <div v-else class="briefing-inline-empty">当前没有可执行的今日行动。</div>
        </section>

        <section v-if="capacityActions.length" class="briefing-section capacity-actions-section">
          <div class="briefing-section-heading">
            <div>
              <h3>时间安排建议</h3>
              <span>这里只显示可确认的安排调整</span>
            </div>
          </div>
          <div class="capacity-action-list">
            <article v-for="action in capacityActions" :key="action.ui_key" class="capacity-action-row">
              <div class="row-main">
                <div class="row-title">{{ action.title || '容量调整建议' }}</div>
                <div class="row-meta">{{ action.reason || '基于容量风险生成' }} · {{ targetLabel(action) }}</div>
                <EvidenceSourceList
                  v-if="actionSourceRefs(action).length"
                  :items="evidenceSourceItems(actionSourceRefs(action), `时间安排${action.title || ''}`)"
                  label="查看来源"
                  compact
                  @open="navigateSourceRef"
                />
              </div>
              <div class="capacity-action-control">
                <el-button
                  v-if="isNavigableAction(action)"
                  size="small"
                  plain
                  :aria-label="`查看${action.title || '相关安排'}`"
                  @click="navigateAction(action)"
                >
                  查看
                </el-button>
                <el-button
                  v-else-if="isExecutableAction(action) && action.action_type === 'set_task_estimate'"
                  size="small"
                  plain
                  :disabled="hasAgentActionLoading()"
                  :aria-label="`为${action.title || '任务'}补充预计用时`"
                  @click="openEstimateAction(action)"
                >
                  补充估时
                </el-button>
                <el-button
                  v-else-if="isExecutableAction(action)"
                  type="primary"
                  size="small"
                  :loading="isActionLoading(actionActionKey(action), 'execute')"
                  :disabled="isAnyActionLoading(actionActionKey(action))"
                  :aria-label="`${actionButtonLabel(action)}：${action.title || '时间安排建议'}`"
                  @click="executeAction(action)"
                >
                  {{ actionButtonLabel(action) }}
                </el-button>
                <span v-else class="muted-action">{{ actionUnavailableLabel(action) }}</span>
              </div>
            </article>
          </div>
        </section>

        <template v-if="isDetailedView">
        <section class="briefing-section recent-results-section">
          <div class="briefing-section-heading">
            <div>
              <h3>最近处理记录</h3>
              <span>查看最近的处理结果</span>
            </div>
          </div>
          <div v-if="recentResults.length" class="recent-results-list">
            <article v-for="result in recentResults" :key="result.ui_key" class="recent-result-row">
              <div class="row-main">
                <div class="row-title">{{ result.title }}</div>
                <div class="row-meta">
                  {{ actionTypeLabel(result.action_type) }} · {{ result.updated_at ? formatDateTime(result.updated_at) : '时间待补充' }}
                </div>
                <div v-if="result.receipt?.message" class="recent-result-receipt">处理结果：{{ result.receipt.message }}</div>
                <div v-else-if="result.receipt?.outcome" class="recent-result-receipt">结果：{{ result.receipt.outcome }}</div>
              </div>
              <el-tag :type="suggestionStatusType(result.status)" size="small" effect="plain">
                {{ suggestionStatusLabel(result.status) }}
              </el-tag>
            </article>
          </div>
          <div v-else class="briefing-inline-empty">暂时没有可追踪的执行或处理记录。</div>
        </section>

        <LedgerDisclosure
          v-model:open="reviewInsightsOpen"
          section-id="review-and-learning-rhythm"
          title="复盘与学习节奏"
          description="需要时再查看活动记录、复盘历史、学习趋势和提醒。"
          meta="活动、周度复盘、趋势与提醒"
        >
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
          <div v-if="activityError" class="activity-load-error" role="alert" aria-live="assertive">
            {{ activityErrorMessage }}
          </div>
          <div v-if="activityLoading && !activityLoaded" class="briefing-inline-empty activity-loading-state">
            正在加载学习处理记录…
          </div>
          <div v-else-if="activityError && !activityLoaded" class="briefing-inline-empty activity-load-failed">
            当前未显示处理记录；请稍后刷新学习建议后重试。
          </div>
          <div v-else-if="!activityLoaded" class="briefing-inline-empty activity-not-loaded">
            处理记录尚未加载；请先刷新学习建议后重试。
          </div>
          <template v-else-if="activity.available">
            <ol v-if="activity.items.length" class="activity-timeline" aria-label="学习处理记录">
              <li v-for="item in activity.items" :key="item.ui_key" class="activity-item">
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
                  <div v-if="activitySourceRef(item)" class="evidence-source-list compact" role="group" aria-label="活动来源入口">
                    <span class="evidence-source-label">来源</span>
                    <button
                      v-if="activitySourceCanNavigate(item)"
                      type="button"
                      class="evidence-source-button"
                      :disabled="isSourceNavigationLoading(activitySourceRef(item))"
                      :aria-label="activitySourceButtonAriaLabel(item)"
                      @click="navigateSourceRef(activitySourceRef(item))"
                    >
                      {{ activitySourceButtonLabel(item) }}
                    </button>
                    <span v-else class="evidence-source-unavailable">{{ activitySourceUnavailableLabel(item) }}</span>
                  </div>
                  <div v-else class="evidence-source-unavailable">{{ activitySourceUnavailableLabel(item) }}</div>
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
              <span>{{ weeklyReview.period_label }} · 只展示近 7 天已记录的数据</span>
            </div>
            <el-tag v-if="weeklyReview.evaluated_at" size="small" effect="plain">{{ formatDateTime(weeklyReview.evaluated_at) }}</el-tag>
          </div>
          <template v-if="weeklyReview.available">
            <div class="weekly-review-grid">
              <div
                v-for="metric in weeklyReview.metrics"
                :key="metric.key"
                class="weekly-review-metric"
                :class="{ 'metric-missing': metric.status === 'unknown' || metric.value === null }"
              >
                <span>{{ metric.label }}</span>
                <strong>{{ weeklyMetricValue(metric) }}</strong>
                <small>{{ metric.detail }}<template v-if="metric.status === 'partial'"> · 样本不完整</template></small>
              </div>
            </div>
            <div v-if="weeklyReview.missing_fields.length" class="weekly-missing-note">
              <strong>数据缺失：</strong>{{ weeklyReview.missing_fields.join('、') }}。缺失部分没有用估算值替代。
            </div>
            <div v-if="weeklyReview.notes.length" class="weekly-review-notes">
              <span>口径说明</span>{{ weeklyReview.notes.join('；') }}
            </div>
            <div class="weekly-next-actions">
              <div class="briefing-subheading">
                <strong>下周行动</strong>
                <span>最多 3 项，原因、来源、风险和执行方式均来自当前数据</span>
              </div>
              <div v-if="weeklyReview.next_actions.length" class="weekly-next-action-list">
                <article v-for="action in weeklyReview.next_actions" :key="action.ui_key" class="weekly-next-action-card">
                  <div class="weekly-next-action-main">
                    <div class="weekly-next-action-heading">
                      <h4>{{ action.title || action.task_name || '下周学习行动' }}</h4>
                      <el-tag :type="riskType(action.risk_level)" size="small" effect="plain">{{ riskLabel(action.risk_level) }}风险</el-tag>
                    </div>
                    <p>{{ action.reason || '系统还没有返回行动原因。' }}</p>
                    <div class="weekly-next-action-meta">
                      <span>来源：{{ actionSourceLabel(action) }}</span>
                      <span>处理方式：{{ executionModeLabel(action.execution_mode) }}</span>
                    </div>
                    <EvidenceSourceList
                      v-if="actionSourceRefs(action).length"
                      :items="evidenceSourceItems(actionSourceRefs(action), `下周行动${action.title || action.task_name || ''}`)"
                      label="查看来源"
                      compact
                      @open="navigateSourceRef"
                    />
                    <div v-else class="evidence-source-unavailable">暂时没有可查看的来源</div>
                  </div>
                  <div class="weekly-next-action-control">
                    <el-button
                      v-if="isNavigableAction(action)"
                      size="small"
                      plain
                      :disabled="hasAgentActionLoading()"
                      :aria-label="`查看${action.title || action.task_name || '下周行动'}来源`"
                      @click="navigateAction(action)"
                    >
                      查看来源
                    </el-button>
                    <el-button
                      v-else-if="isExecutableAction(action) && action.action_type === 'set_task_estimate'"
                      size="small"
                      plain
                      :disabled="hasAgentActionLoading()"
                      :aria-label="`为${action.title || action.task_name || '下周行动'}补充预计用时`"
                      @click="openEstimateAction(action)"
                    >
                      补充估时
                    </el-button>
                    <el-button
                      v-else-if="isExecutableAction(action)"
                      type="primary"
                      size="small"
                      :loading="isActionLoading(actionActionKey(action), 'execute')"
                      :disabled="isAnyActionLoading(actionActionKey(action))"
                      :aria-label="`${actionButtonLabel(action)}：${action.title || action.task_name || '下周行动'}`"
                      @click="executeAction(action)"
                    >
                      {{ actionButtonLabel(action) }}
                    </el-button>
                    <span v-else class="muted-action">{{ actionUnavailableLabel(action) }}</span>
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
            <div v-if="weeklyHistory.snapshots.length" class="weekly-history-list">
              <article v-for="snapshot in weeklyHistory.snapshots" :key="snapshot.ui_key" class="weekly-history-card">
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
                  :items="evidenceSourceItems(snapshot.source_refs, `复盘快照${snapshot.period_label || ''}`)"
                  label="查看来源"
                  :initial-limit="6"
                  compact
                  @open="navigateSourceRef"
                />
                <div v-else class="evidence-source-unavailable">该历史快照没有可点击的来源入口。</div>
              </article>
            </div>
            <div v-else class="briefing-inline-empty">
              {{ weeklyHistory.available ? '当前还没有可展示的历史记录。' : '历史复盘尚未开启；当前页不把实时复盘当作历史。' }}
            </div>
          </div>
        </section>

        <section class="briefing-section rhythm-history-section" aria-labelledby="rhythm-history-title">
          <div class="briefing-section-heading">
            <div>
              <h3 id="rhythm-history-title">学习节奏历史比较</h3>
              <span>只比较已关闭的历史摘要，不把当前趋势当作历史</span>
            </div>
            <el-tag size="small" effect="plain" :type="rhythmHistoryStatusType(rhythmHistory.comparison.status)">
              {{ rhythmHistoryStatusLabel(rhythmHistory) }}
            </el-tag>
          </div>
          <div v-if="rhythmHistory.available_windows.length" class="rhythm-history-windows">
            <article v-for="(window, index) in rhythmHistory.available_windows.slice(0, 2)" :key="window.snapshot_id" class="rhythm-history-window">
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
          <div v-if="rhythmHistory.comparison.comparable" class="rhythm-history-change-list">
            <article v-for="change in rhythmHistoryChanges" :key="change.code" class="rhythm-history-change">
              <div>
                <strong>{{ rhythmSignalLabel(change.code) }}</strong>
                <small>A：{{ rhythmSignalValue(change.newer_value, change.newer_status) }} · B：{{ rhythmSignalValue(change.older_value, change.older_status) }}</small>
              </div>
              <el-tag size="small" effect="plain">{{ rhythmDeltaLabel(change.delta) }}</el-tag>
            </article>
          </div>
          <div v-else class="briefing-inline-empty">{{ rhythmHistoryFallbackText(rhythmHistory) }}</div>
          <div v-if="rhythmHistory.comparison.reason_codes.length || rhythmHistory.comparison.limitations.length" class="rhythm-history-limits">
             <strong>当前限制：</strong>{{ rhythmHistoryReasonLabel(rhythmHistory) }}<template v-if="rhythmHistory.comparison.limitations.length"> · {{ rhythmHistory.comparison.limitations[0] }}</template>
          </div>
        </section>

        <section class="briefing-section learning-trends-section" aria-labelledby="learning-trends-title">
          <div class="briefing-section-heading">
            <div>
              <h3 id="learning-trends-title">学习节奏趋势</h3>
              <span>{{ learningTrends.window_label }} · 只展示已记录的数据</span>
            </div>
            <el-tag size="small" effect="plain" :type="trendStatusType(learningTrends.status)">{{ trendStatusLabel(learningTrends.status) }}</el-tag>
          </div>
          <template v-if="learningTrends.available">
            <div class="learning-trends-meta">
              <span>样本：{{ learningTrends.sample_count === null ? '待补充' : `${learningTrends.sample_count} 条` }}</span>
              <span>已知：{{ learningTrends.known_count === null ? '待补充' : learningTrends.known_count }}</span>
              <span>缺失：{{ learningTrends.unknown_count === null ? '待补充' : learningTrends.unknown_count }}</span>
              <span>最低样本：{{ learningTrends.minimum_sample_count === null ? '待补充' : learningTrends.minimum_sample_count }} · {{ learningTrends.timezone }}</span>
              <span v-if="learningTrends.evaluated_at">评估于 {{ formatDateTime(learningTrends.evaluated_at) }}</span>
            </div>
            <div v-if="learningTrends.signals.length" class="learning-trend-signal-list">
              <article v-for="signal in learningTrends.signals" :key="signal.ui_key" class="learning-trend-signal">
                <div class="learning-trend-signal-main">
                  <div class="learning-trend-signal-heading">
                    <strong>{{ signal.label }}</strong>
                    <el-tag size="small" effect="plain" :type="trendStatusType(signal.status)">{{ trendStatusLabel(signal.status) }}</el-tag>
                  </div>
                  <p>{{ signal.summary || '当前还没有趋势解读。' }}</p>
                  <small>{{ signal.sample_count === null ? '样本待补充' : `样本 ${signal.sample_count} 条` }} · {{ signal.evidence_label }}</small>
                  <EvidenceSourceList
                    v-if="actionSourceRefs(signal).length"
                    :items="evidenceSourceItems(actionSourceRefs(signal), `学习趋势${signal.label || ''}`)"
                    label="查看来源"
                    compact
                    @open="navigateSourceRef"
                  />
                </div>
              </article>
            </div>
            <div v-else class="briefing-inline-empty">当前窗口没有足够的实际完成记录，趋势不作推断。</div>
            <div v-if="learningTrends.adjustment_candidates.length" class="learning-trend-candidates">
               <div class="briefing-subheading"><strong>可考虑的调整</strong><span>仅供你确认；不会自动修改课程或计划</span></div>
              <article v-for="candidate in learningTrends.adjustment_candidates" :key="candidate.ui_key" class="learning-trend-candidate">
                <div><strong>{{ candidate.title || '学习节奏调整建议' }}</strong><p>{{ candidate.reason || '当前还没有说明这项建议的原因。' }}</p></div>
                <el-tag size="small" effect="plain">确认</el-tag>
              </article>
            </div>
            <div v-if="learningTrends.limitations.length" class="learning-trends-limitations"><strong>限制：</strong>{{ learningTrends.limitations.join('；') }}</div>
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
          <div v-if="reminders.length" class="reminder-list">
            <article v-for="reminder in visibleReminders" :key="reminder.ui_key" class="reminder-card" :class="`reminder-${reminder.severity}`">
              <div class="reminder-main">
                <div class="reminder-heading">
                  <h4>{{ reminder.title || '学习提醒' }}</h4>
                  <el-tag :type="reminderSeverityType(reminder.severity)" size="small" effect="plain">
                    {{ reminderSeverityLabel(reminder.severity) }}
                  </el-tag>
                </div>
                <p>{{ reminder.reason || reminder.explanation || '当前还没有说明这条提醒的原因。' }}</p>
                <div class="reminder-meta">
                  <span>来源：{{ actionSourceLabel(reminder) }}</span>
                  <span>处理：可导航或忽略</span>
                </div>
                <EvidenceSourceList
                  v-if="actionSourceRefs(reminder).length"
                  :items="evidenceSourceItems(actionSourceRefs(reminder), `站内提醒${reminder.title || ''}`)"
                  label="查看来源"
                  compact
                  @open="navigateSourceRef"
                />
                <div v-else class="evidence-source-unavailable">暂时没有可查看的来源</div>
              </div>
              <div class="reminder-control">
                <el-button
                  v-if="isNavigableReminder(reminder)"
                  size="small"
                  plain
                  :disabled="hasAgentActionLoading()"
                  :aria-label="`查看${reminder.title || '学习提醒'}来源`"
                  @click="navigateReminder(reminder)"
                >
                  查看
                </el-button>
                <el-button
                  v-else-if="isExecutableAction(reminder)"
                  type="primary"
                  size="small"
                  :loading="isActionLoading(actionActionKey(reminder), 'execute')"
                  :disabled="isAnyActionLoading(actionActionKey(reminder))"
                  :aria-label="`${actionButtonLabel(reminder)}：${reminder.title || '学习提醒'}`"
                  @click="executeAction(reminder)"
                >
                  {{ actionButtonLabel(reminder) }}
                </el-button>
                <span v-else-if="!isDismissibleReminder(reminder)" class="muted-action">{{ actionUnavailableLabel(reminder) }}</span>
                <el-button
                  v-if="isDismissibleReminder(reminder)"
                  size="small"
                  :loading="isActionLoading(reminderActionKey(reminder), 'dismiss')"
                  :disabled="isAnyActionLoading(reminderActionKey(reminder))"
                  :aria-label="`忽略${reminder.title || '学习提醒'}`"
                  @click="dismissReminder(reminder)"
                >
                  忽略
                </el-button>
              </div>
            </article>
          </div>
          <p v-if="isConciseView && reminders.length > visibleReminders.length" class="concise-list-note">
            另有 {{ reminders.length - visibleReminders.length }} 条普通提醒，可在完整视图查看；高风险提醒始终全部显示。
          </p>
          <div v-else class="briefing-inline-empty">暂无站内提醒；系统未返回的提醒不会在页面中补造。</div>
        </section>
        </LedgerDisclosure>
        </template>
        <aside v-if="isConciseView" class="detail-view-nudge" aria-label="完整内容提示">
          <div>
            <strong>先完成今天最重要的几件事。</strong>
            <span>完整视图还保留最近处理记录、活动时间线、周度复盘、历史比较、学习趋势、计划差异和建议详情。</span>
          </div>
          <el-button plain size="small" aria-label="切换到完整视图查看学习记录" @click="openDetailedLedger">查看完整内容</el-button>
        </aside>
      </template>

      <template v-if="isDetailedView">
      <section id="plan-deltas" class="briefing-section plan-deltas-section" tabindex="-1" aria-labelledby="plan-deltas-title">
        <div class="briefing-section-heading">
          <div>
            <h3 id="plan-deltas-title">计划差异提醒</h3>
            <span>完成反馈或新的截止任务改变后，只提出需要你确认的重排方案</span>
          </div>
        </div>
        <p v-if="!planDeltas.length" class="muted">{{ detailedDataState === 'ready' ? '当前没有计划调整候选。' : '计划调整尚未确认，请查看加载状态。' }}</p>
        <div class="plan-delta-list">
          <article v-for="delta in planDeltas" :key="delta.ui_key" class="plan-delta-card">
            <div class="plan-delta-heading">
              <div>
                <h4>{{ delta.title }}</h4>
                <div class="suggestion-source">{{ delta.course_name || '未归类课程' }}<template v-if="delta.plan_id"> · 计划 #{{ delta.plan_id }}</template></div>
              </div>
              <el-tag :type="suggestionStatusType(delta.status)" size="small" effect="plain">{{ suggestionStatusLabel(delta.status) }}</el-tag>
            </div>
            <p class="plan-delta-trigger"><strong>触发原因：</strong>{{ delta.trigger || '学习安排发生变化，需要重新检查计划。' }}</p>
            <div class="plan-delta-change-grid">
              <div class="plan-delta-change before">
                <span class="plan-delta-change-label">调整前</span>
                <ul v-if="delta.before_lines.length"><li v-for="line in delta.before_lines" :key="`before-${line}`">{{ line }}</li></ul>
                <span v-else class="plan-delta-empty">原计划信息待补充</span>
              </div>
              <div class="plan-delta-arrow" aria-hidden="true">→</div>
              <div class="plan-delta-change after">
                <span class="plan-delta-change-label">调整后</span>
                <ul v-if="delta.after_lines.length"><li v-for="line in delta.after_lines" :key="`after-${line}`">{{ line }}</li></ul>
                <span v-else class="plan-delta-empty">建议变化待补充</span>
              </div>
            </div>
            <div v-if="delta.protected_lines.length" class="plan-delta-protected">
              <span class="plan-delta-change-label">保持不变</span>
              <span>{{ delta.protected_lines.join('；') }}</span>
            </div>
            <p v-if="delta.explanation" class="plan-delta-explanation">{{ delta.explanation }}</p>
            <div class="plan-delta-actions">
              <el-button
                size="small"
                :loading="isActionLoading(planDeltaActionKey(delta), 'dismiss')"
                :disabled="isAnyActionLoading(planDeltaActionKey(delta)) || delta.status !== 'pending'"
                :aria-label="`忽略${delta.title || '计划差异提醒'}`"
                @click="dismissPlanDelta(delta)"
              >
                忽略
              </el-button>
              <el-button
                type="primary"
                size="small"
                :loading="isActionLoading(planDeltaActionKey(delta), 'accept')"
                :disabled="isAnyActionLoading(planDeltaActionKey(delta)) || delta.status !== 'pending'"
                :aria-label="`确认${delta.title || '计划差异提醒'}并重排`"
                @click="acceptPlanDelta(delta)"
              >
                确认重排
              </el-button>
            </div>
          </article>
        </div>
      </section>

      <div v-if="agent.suggestions.length" class="agent-suggestions">
        <article v-for="suggestion in agent.suggestions" :key="suggestion.id" class="agent-suggestion-card">
          <div class="suggestion-main">
            <div class="suggestion-heading">
              <div>
                <h3>{{ suggestion.title || '学习安排调整建议' }}</h3>
                <div class="suggestion-source">来源：{{ sourceLabel(suggestion) }}</div>
              </div>
              <el-tag :type="riskType(suggestion.risk_level)" size="small" effect="plain">
                {{ riskLabel(suggestion.risk_level) }}风险
              </el-tag>
              <el-tag :type="suggestionStatusType(suggestion.status)" size="small" effect="plain">
                {{ suggestionStatusLabel(suggestion.status) }}
              </el-tag>
            </div>
            <p class="suggestion-explanation">{{ suggestion.explanation || '学习助手发现这项安排可能需要调整。' }}</p>
            <div class="suggestion-meta">
              <span>截止：{{ deadlineLabel(suggestion) }}</span>
              <span>优先级：{{ currentPriority(suggestion) }} → {{ proposedPriority(suggestion) }}</span>
              <span v-if="suggestion.confidence !== null && suggestion.confidence !== undefined">
                置信度：{{ confidenceLabel(suggestion.confidence) }}
              </span>
              <span v-if="suggestion.receipt?.message">处理结果：{{ suggestion.receipt.message }}</span>
            </div>
          </div>
          <div class="suggestion-actions">
            <div class="priority-control">
              <span class="priority-label">确认优先级</span>
              <el-radio-group
                v-model="selectedPriorities[suggestion.id]"
                size="small"
                :aria-label="`为${suggestion.title || '建议'}选择优先级`"
                :disabled="isAnyActionLoading(suggestion.id)"
              >
                <el-radio-button :value="4">4</el-radio-button>
                <el-radio-button :value="5">5</el-radio-button>
              </el-radio-group>
            </div>
            <div class="suggestion-buttons">
              <el-button
                size="small"
                :loading="isActionLoading(suggestion.id, 'dismiss')"
                :disabled="isAnyActionLoading(suggestion.id)"
                :aria-label="`忽略${suggestion.title || '这条建议'}`"
                @click="dismissSuggestion(suggestion)"
              >
                忽略
              </el-button>
              <el-button
                type="primary"
                size="small"
                :loading="isActionLoading(suggestion.id, 'accept')"
                :disabled="isAnyActionLoading(suggestion.id)"
                :aria-label="`接受${suggestion.title || '这条建议'}`"
                @click="acceptSuggestion(suggestion)"
              >
                接受建议
              </el-button>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="agent-empty-state">
        <div class="agent-empty-title">当前没有待处理建议</div>
        <div>学习助手会在任务临近截止或安排发生变化时提醒你。</div>
      </div>
      </template>
    </el-card>

    <el-card v-if="isDetailedView" id="risk-center" class="risk-center-card" shadow="never" aria-labelledby="risk-center-title" tabindex="-1">
      <div class="risk-center-heading">
        <div>
          <div class="agent-kicker">CAPACITY WATCH</div>
          <div class="risk-title-row">
            <h2 id="risk-center-title">风险中心</h2>
            <el-tag :type="capacityRisk.type" effect="plain" size="small">{{ capacityRisk.label }}</el-tag>
          </div>
          <p class="risk-description">根据已填写的任务工作量和可用学习时间，帮助你判断安排是否需要留出余量。</p>
        </div>
        <el-button
          plain
          :loading="capacityLoading"
          :disabled="capacityLoading"
          aria-label="刷新学习容量风险"
          @click="loadCapacity"
        >
          刷新容量
        </el-button>
      </div>

      <el-alert v-if="capacityError" :title="capacityError" type="warning" show-icon closable class="capacity-message" @close="capacityError = ''" />
      <div v-if="capacityLoading && !capacityLoaded" class="capacity-empty-state" role="status" aria-live="polite">正在汇总任务工作量和可用时间…</div>
      <template v-else>
        <div class="capacity-metrics">
          <div class="capacity-metric">
            <div class="capacity-label">可用容量</div>
            <div class="capacity-value">{{ formatMinutes(capacity.available_minutes) }}</div>
            <div class="capacity-note">未来 7 天，已扣除缓冲</div>
          </div>
          <div class="capacity-metric">
            <div class="capacity-label">已知工作量</div>
            <div class="capacity-value">{{ formatMinutes(capacity.known_workload_minutes) }}</div>
            <div class="capacity-note">剩余用时优先，预计用时兜底</div>
          </div>
          <div class="capacity-metric">
            <div class="capacity-label">时间负荷</div>
            <div class="capacity-value">{{ formatLoadRatio(capacity.load_ratio) }}</div>
            <div class="capacity-note">工作量 ÷ 可用时间</div>
          </div>
          <div class="capacity-metric">
            <div class="capacity-label">缺失估时</div>
            <div class="capacity-value">{{ formatCount(capacity.missing_estimates_count) }}</div>
            <div class="capacity-note">预计或剩余用时待补充</div>
          </div>
          <div class="capacity-metric">
            <div class="capacity-label">同日多个截止任务</div>
            <div class="capacity-value">{{ formatCount(capacity.same_day_ddl_count, '天') }}</div>
            <div class="capacity-note">可能需要错峰安排</div>
          </div>
          <div class="capacity-metric">
            <div class="capacity-label">单日超载</div>
            <div class="capacity-value">{{ formatCount(capacity.daily_overload_count, '天') }}</div>
            <div class="capacity-note">已知工作量超过单日有效容量</div>
          </div>
        </div>
        <div class="capacity-basis">
          <span class="capacity-basis-label">计算依据</span>
          <span>{{ capacityBasis }}</span>
        </div>
      </template>
    </el-card>

    <div v-if="isDetailedView" class="stats-grid">
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon purple"><el-icon><List /></el-icon></div>
        <div class="stat-label">未完成任务</div>
        <div class="stat-value">{{ dashboardCountDisplay('active_task_count') }}</div>
        <div class="stat-note">保持节奏，逐个完成</div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon orange"><el-icon><Clock /></el-icon></div>
        <div class="stat-label">7 天内到期</div>
        <div class="stat-value">{{ dashboardCountDisplay('due_soon_count') }}</div>
           <div class="stat-note">优先查看临近截止任务</div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon red"><el-icon><WarningFilled /></el-icon></div>
        <div class="stat-label">已逾期任务</div>
        <div class="stat-value">{{ dashboardCountDisplay('overdue_count') }}</div>
        <div class="stat-note">及时调整你的安排</div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <div class="stat-icon green"><el-icon><Collection /></el-icon></div>
        <div class="stat-label">资料总数</div>
        <div class="stat-value">{{ dashboardCountDisplay('materials_count') }}</div>
        <div class="stat-note">{{ dashboardState === 'ready' ? `来自 ${dashboard.courses_count} 门课程` : '课程数量待确认' }}</div>
      </el-card>
    </div>

    <aside v-if="isConciseView" class="concise-ledger-invite" aria-labelledby="concise-ledger-invite-title">
      <div>
        <span class="concise-ledger-kicker">完整记录</span>
        <strong id="concise-ledger-invite-title">需要查看依据、复盘和历史记录？</strong>
         <p>完整视图保留决策详情、容量计算、复盘快照和依据入口，不改变任何执行权限。</p>
      </div>
       <el-button plain aria-label="切换到完整视图查看学习记录" @click="openDetailedLedger">查看完整记录</el-button>
    </aside>

    <div v-if="isDetailedView" class="content-grid">
      <el-card class="content-card" shadow="never">
        <div class="card-heading">
          <h2>近期任务</h2>
          <router-link to="/tasks">查看全部</router-link>
        </div>
        <div v-if="dashboardState === 'ready' && upcomingTasks.length">
          <div v-for="task in upcomingTasks" :key="task.id" class="task-row clickable-row" role="link" tabindex="0" :aria-label="`打开任务${task.name}`" @click="goToTasks" @keydown.enter="goToTasks" @keydown.space.prevent="goToTasks">
            <div class="row-main">
              <div class="row-title">{{ task.name }}</div>
              <div class="row-meta">{{ task.course_name || '未归类课程' }} · {{ dueLabel(task) }}</div>
            </div>
            <el-tag :type="statusType(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag>
          </div>
        </div>
        <div v-else-if="dashboardState === 'ready'" class="empty-state">未来 7 天没有待处理任务。</div>
        <div v-else class="empty-state">任务数据尚未确认。</div>
        <div v-if="dashboardState === 'ready' && overdueTasks.length" class="dashboard-subsection">
          <div class="subsection-title">逾期提醒</div>
          <div v-for="task in overdueTasks" :key="task.id" class="task-row clickable-row" role="link" tabindex="0" :aria-label="`打开逾期任务${task.name}`" @click="goToTasks" @keydown.enter="goToTasks" @keydown.space.prevent="goToTasks">
            <div class="row-main">
              <div class="row-title">{{ task.name }}</div>
              <div class="row-meta">{{ task.course_name || '未归类课程' }} · 已逾期 {{ formatDateTime(task.due_at) }}</div>
            </div>
            <el-tag type="danger" size="small">优先处理</el-tag>
          </div>
        </div>
      </el-card>

      <el-card class="content-card" shadow="never">
        <div class="card-heading">
          <h2>最近资料</h2>
          <router-link to="/materials">查看全部资料</router-link>
        </div>
        <div v-if="dashboardState === 'ready' && recentMaterials.length">
          <div v-for="material in recentMaterials" :key="material.id" class="material-row clickable-row" role="link" tabindex="0" :aria-label="`打开资料${material.original_filename}`" @click="goToMaterial(material)" @keydown.enter="goToMaterial(material)" @keydown.space.prevent="goToMaterial(material)">
            <div class="row-main">
              <div class="row-title">{{ material.original_filename }}</div>
              <div class="row-meta">{{ material.course_name || '未归类课程' }} · {{ materialType(material) }}</div>
            </div>
            <el-tag size="small" effect="plain">{{ material.processing_status }}</el-tag>
          </div>
        </div>
        <div v-else-if="dashboardState === 'ready'" class="empty-state">还没有资料记录。</div>
        <div v-else class="empty-state">资料数据尚未确认。</div>
      </el-card>
    </div>

    <el-dialog v-model="estimateDialogVisible" title="补充预计用时" width="420px" destroy-on-close>
       <p class="estimate-dialog-help">这次填写的预计用时只用于当前建议，不会自动替你估算。</p>
      <el-form label-width="96px">
        <el-form-item label="预计用时" required>
          <div class="estimate-input-wrap">
            <el-input-number v-model="estimateMinutes" :min="15" :max="10080" :step="15" controls-position="right" />
            <span class="unit-label">分钟</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="form-actions">
          <el-button @click="closeEstimateAction">取消</el-button>
         <el-button type="primary" :loading="isEstimateActionLoading" @click="submitEstimateAction">保存预计用时</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElAlert,
  ElCard,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInputNumber,
  ElMessage,
  ElRadioButton,
  ElRadioGroup,
} from 'element-plus'
import { Clock, Collection, List, WarningFilled } from '@element-plus/icons-vue'

import { agentApi, dashboardApi } from '../api'
import { useViewMode } from '../composables/useViewMode'
import { formatDateTime, isOverdue, statusLabel, statusType } from '../utils/format'
import {
  navigationKey,
  navigationSourceCacheKey,
  normalizedNavigationSourceRef,
  positiveMaterialId,
  validatedMaterialTarget,
  validatedSourceNavigationTarget,
} from '../utils/materialSourceNavigation'
import AiInboxShortcut from '../components/AiInboxShortcut.vue'
import DeadlineFlow from '../components/DeadlineFlow.vue'
import EvidenceSourceList from '../components/EvidenceSourceList.vue'
import FirstLearningLoop from '../components/FirstLearningLoop.vue'
import LedgerDisclosure from '../components/LedgerDisclosure.vue'
import TodayFocusStage from '../components/TodayFocusStage.vue'
import { shouldPrioritizeFirstLearningLoop } from '../utils/firstLearningLoopPlacement'
import { normalizePlanDeltaLines } from '../utils/planDeltaDisplay'

const loading = ref(true)
const dashboardState = ref('loading')
const router = useRouter()
const { isConciseView, isDetailedView, setViewMode } = useViewMode()
const error = ref('')
const dashboard = ref({
  active_task_count: null,
  due_soon_count: null,
  overdue_count: null,
  completed_task_count: null,
  study_streak_days: 0,
  materials_count: null,
  courses_count: null,
  next_action: '',
  upcoming_tasks: [],
  overdue_tasks: [],
  recent_materials: [],
})
const upcomingTasks = ref([])
const overdueTasks = ref([])
const recentMaterials = ref([])
const deadlineMaterialLoading = ref({})
const agentLoading = ref(false)
const agentBriefingState = ref('loading')
const agent = ref({ generated_at: '', pending_count: null, suggestions: [] })
const agentMessage = ref({ type: 'info', text: '' })
const briefingLoaded = ref(false)
const inbox = ref(normalizeInbox({}))
const decisionQueue = ref([])
const decisionQueueStatus = ref('unavailable')
const todayActions = ref([])
const capacityActions = ref([])
const recentResults = ref([])
const planDeltas = ref([])
const weeklyReview = ref(normalizeWeeklyReview({}))
const learningTrends = ref(normalizeLearningTrends({}))
const weeklyHistory = ref(normalizeWeeklyReviewHistory({}))
const rhythmHistory = ref(normalizeLearningRhythmHistory({}))
const activity = ref(normalizeActivity({}))
const activityLoading = ref(false)
const activityLoaded = ref(false)
const activityError = ref('')
// Detailed resources are deliberately kept out of the concise first paint.
// `detailedDataRequested` records a completed attempt (including a partial
// failure), so repeatedly changing views never turns into repeated requests.
const detailedDataState = ref('idle')
const detailedDataFailures = ref([])
const detailedDataRequested = ref(false)
const reminders = ref([])
const reviewInsightsOpen = ref(false)
// Source evidence is resolved by the server.  Keeping the result separately
// from the displayed refs lets the UI distinguish "not checked yet" from a
// real unavailable source without ever constructing a route locally.
const sourceNavigation = ref({})
const sourceNavigationLoading = ref({})
const selectedPriorities = ref({})
const actionLoading = ref({})
const idempotencyKeys = new Map()
const controlledActionTypes = new Set([
  'set_task_estimate',
  'start_task',
  'adjust_priority',
  'review',
  'navigate',
  'review_daily_overload',
  'navigate_same_day_deadlines',
])
const decisionKindLabels = Object.freeze({
  material_failed: '资料处理',
  material_needs_review: '资料待确认',
  material_ready: '资料确认',
  plan_delta_review: '计划差异',
  suggestion_priority_review: '任务建议',
  capacity_estimate_review: '容量估时',
  capacity_start_review: '今日安排',
  capacity_overload_review: '容量风险',
  capacity_same_day_review: '截止冲突',
})
const decisionPriorityLabels = Object.freeze({
  critical: '立即处理',
  high: '优先处理',
  medium: '安排处理',
  normal: '稍后查看',
})
const decisionReasonLabels = Object.freeze({
  material_processing_failed: '资料处理失败',
  material_extraction_failed: '资料识别失败',
  material_needs_review: '资料待确认',
  material_ready: '资料已识别',
  pending_plan_delta: '计划差异待确认',
  pending_priority_suggestion: '优先级建议待确认',
  capacity_missing_estimate: '任务缺少估时',
  capacity_start_task: '容量计算下的今日任务',
  capacity_daily_overload: '单日容量超载',
  capacity_same_day_deadlines: '同日截止任务',
})
const decisionKinds = new Set(Object.keys(decisionKindLabels))
const decisionPriorities = new Set(Object.keys(decisionPriorityLabels))
const decisionReasonCodes = new Set(Object.keys(decisionReasonLabels))
const decisionSourceTypes = new Set(['task', 'material', 'study_plan', 'capacity'])
const decisionSourceStates = new Set(['failed', 'needs_review', 'ready', 'pending', 'current_capacity'])
const estimateDialogVisible = ref(false)
const estimateAction = ref(null)
const estimateMinutes = ref(null)
const capacity = ref(normalizeCapacity({}))
const capacityLoading = ref(false)
const capacityLoaded = ref(false)
const capacityError = ref('')
const activityStatusMessage = computed(() => {
  if (activityLoading.value) {
    return activityLoaded.value
       ? '正在刷新学习处理记录，页面暂时保留上次成功加载的记录。'
       : '正在加载学习处理记录。'
  }
  if (activityError.value) {
    return activityLoaded.value
      ? `活动记录刷新失败，仍显示上次成功加载的 ${activity.value.items.length} 条记录。`
       : '处理记录加载失败，当前未显示处理数据。'
  }
   if (!activityLoaded.value) return '处理记录尚未加载。'
   if (!activity.value.available) return '处理记录暂不可用，未使用其他数据替代。'
   return `已加载 ${activity.value.items.length} 条学习处理记录。`
})
const activityErrorMessage = computed(() => {
  const detail = safeText(activityError.value, '服务暂时不可用，请稍后重试。')
  return activityLoaded.value
     ? `处理记录刷新失败：${detail} 当前仍显示上次成功加载的记录。`
     : `处理记录加载失败：${detail} 当前未显示处理记录。`
})
const capacityRisk = computed(() => capacityRiskInfo(capacity.value))
const capacityBasis = computed(() => capacityBasisText(capacity.value))
const agentPendingDisplay = computed(() => (
  agentBriefingState.value === 'ready' && nonNegativeInteger(agent.value.pending_count) !== null
    ? agent.value.pending_count
    : '—'
))
const firstLoopMaterialRef = computed(() => {
  for (const decision of decisionQueue.value) {
    if (!String(decision?.kind || '').startsWith('material_')) continue
    const ref = decisionSourceRefs(decision).find((item) => item.source_type === 'material')
    if (ref) return ref
  }
  return null
})
const detailedDataStatusMessage = computed(() => {
  if (detailedDataState.value === 'loading') {
    return '正在加载完整记录：复盘、历史、趋势、活动、计划差异和依据入口会在本次请求完成后显示。'
  }
  if (detailedDataState.value === 'error') {
    return `部分完整记录未能加载：${detailedDataFailures.value.join('、')}。已保留本次成功返回的数据；可刷新建议后重试。`
  }
  if (detailedDataState.value === 'ready') {
    return '完整记录已加载；复盘、历史、趋势、活动、计划差异和依据入口均来自本次查询。'
  }
  return '完整记录尚未加载。'
})
const focusStageState = computed(() => {
  if (agentBriefingState.value === 'loading') return 'loading'
  if (agentBriefingState.value === 'error') return 'error'
  if (agentBriefingState.value === 'invalid' || decisionQueueStatus.value === 'invalid') return 'invalid'
  return 'ready'
})
const deadlineFlowState = computed(() => {
  if (dashboardState.value === 'loading') return 'loading'
  if (dashboardState.value === 'ready') return 'ready'
  return 'error'
})
const deadlineMaterialBusyKeys = computed(() => Object.keys(deadlineMaterialLoading.value))
const aiInboxShortcutState = computed(() => {
  if (agentBriefingState.value === 'loading') return 'loading'
  if (agentBriefingState.value === 'ready' && inbox.value.available) return 'ready'
  return 'error'
})
const focusStageSource = computed(() => {
  const firstDecision = decisionQueue.value[0] || null
  const firstAction = todayActions.value[0] || null
  if (firstDecision && ['critical', 'high'].includes(firstDecision.priority)) {
    return { kind: 'decision', item: firstDecision }
  }
  if (firstAction) return { kind: 'action', item: firstAction }
  if (firstDecision) return { kind: 'decision', item: firstDecision }
  return null
})
const focusStageItem = computed(() => {
  const source = focusStageSource.value
  if (!source) return null
  return source.kind === 'decision' ? decisionFocusItem(source.item) : todayActionFocusItem(source.item)
})
const focusAttentionItems = computed(() => buildFocusAttentionItems(focusStageSource.value))
const firstLearningLoopPriority = computed(() => shouldPrioritizeFirstLearningLoop({
  dashboardState: dashboardState.value,
  agentState: agentBriefingState.value,
  decisionQueueStatus: decisionQueueStatus.value,
  hasFocus: Boolean(focusStageSource.value),
  attentionCount: focusAttentionItems.value.length,
  progress: dashboard.value,
}))
// Moving one Teleport target keeps the loop's hide/restore state intact while
// the first actionable area changes after trustworthy data arrives.
const firstLearningLoopTarget = computed(() => (
  firstLearningLoopPriority.value
    ? '#dashboard-first-learning-loop-priority'
    : '#dashboard-first-learning-loop-default'
))
const focusSummaryItems = computed(() => {
  const inboxTotal = inbox.value.ready_count + inbox.value.needs_review_count + inbox.value.failed_count
  const capacityState = capacityLoading.value
    ? { value: '读取中', state: 'default' }
    : capacityError.value || !capacityLoaded.value
      ? { value: '待确认', state: 'warning' }
      : { value: capacityRisk.value.label, state: capacityRisk.value.type === 'danger' ? 'danger' : capacityRisk.value.type === 'warning' ? 'warning' : 'success' }
  return [
    { label: '待确认', value: decisionQueueStatus.value === 'available' || decisionQueueStatus.value === 'empty' ? `${decisionQueue.value.length} 项` : '—', state: decisionQueue.value.length ? 'warning' : 'success' },
    { label: '今日安排', value: briefingLoaded.value ? `${todayActions.value.length} 项` : '—', state: todayActions.value.some((action) => ['high', 'critical'].includes(action.risk_level)) ? 'danger' : 'default' },
    { label: '学习收件箱', value: inbox.value.available ? `${inboxTotal} 项` : '—', state: inbox.value.failed_count ? 'danger' : inboxTotal ? 'warning' : 'success' },
    { label: '容量状态', ...capacityState },
  ]
})
const focusDetailsCount = computed(() => (
  decisionQueue.value.length
  + todayActions.value.length
  + capacityActions.value.length
  + reminders.value.length
  + recentResults.value.length
  + planDeltas.value.length
  + agent.value.suggestions.length
))
const visibleDecisionQueue = computed(() => {
  if (isDetailedView.value || decisionQueue.value.length <= 3) return decisionQueue.value
  // Concise mode can trim ordinary follow-ups, never a critical/high review
  // item. The server's original ordering is retained in the final filter.
  const highRisk = decisionQueue.value.filter((decision) => ['critical', 'high'].includes(decision.priority))
  const ordinarySlots = Math.max(0, 3 - highRisk.length)
  const ordinary = decisionQueue.value.filter((decision) => !['critical', 'high'].includes(decision.priority)).slice(0, ordinarySlots)
  const visible = new Set([...highRisk, ...ordinary])
  return decisionQueue.value.filter((decision) => visible.has(decision))
})
const visibleReminders = computed(() => {
  if (isDetailedView.value || reminders.value.length <= 3) return reminders.value
  const highRisk = reminders.value.filter((reminder) => reminder.severity === 'high')
  const ordinarySlots = Math.max(0, 3 - highRisk.length)
  const ordinary = reminders.value.filter((reminder) => reminder.severity !== 'high').slice(0, ordinarySlots)
  const visible = new Set([...highRisk, ...ordinary])
  return reminders.value.filter((reminder) => visible.has(reminder))
})
const learningLedgerIndex = computed(() => {
  const briefingReady = briefingLoaded.value
  const inboxTotal = inbox.value.ready_count + inbox.value.needs_review_count + inbox.value.failed_count
  let decisionStatus = '正在读取'
  if (briefingReady) {
    if (decisionQueueStatus.value === 'available') decisionStatus = `${decisionQueue.value.length} 项待确认`
    else if (decisionQueueStatus.value === 'empty') decisionStatus = '暂无待确认'
    else if (decisionQueueStatus.value === 'invalid') decisionStatus = '内容待校验'
    else decisionStatus = '队列暂不可用'
  }
  const inboxStatus = !briefingReady
    ? '正在读取'
    : !inbox.value.available
      ? '摘要暂不可用'
      : inboxTotal
        ? `${inboxTotal} 项待处理`
        : '收件箱已清空'
  const todayStatus = !briefingReady
    ? '正在读取'
    : todayActions.value.length
      ? `${todayActions.value.length} 项已排定`
      : '暂无已排定事项'
  const riskStatus = capacityLoading.value
    ? '正在汇总'
    : capacityError.value
      ? '容量暂不可用'
      : capacityLoaded.value
        ? capacityRisk.value.label
        : '待载入'
  return [
    { target: 'today-decision-desk', label: '今日确认', status: decisionStatus, targetReady: briefingReady },
    { target: 'learning-inbox', label: '学习收件箱', status: inboxStatus, targetReady: briefingReady },
    { target: 'today-actions', label: '今日行动', status: todayStatus, targetReady: briefingReady },
    { target: 'risk-center', label: '风险中心', status: riskStatus, targetReady: true },
  ]
})

function goToTasks() {
  router.push('/tasks')
}

async function openDeadlineTask(task) {
  const taskId = safePositiveId(task?.id)
  const taskKey = navigationKey(task?.navigation_key)
  if (!taskId || !taskKey) {
    announceSourceUnavailable('暂不能确认任务来源，请从任务列表查看。')
    return
  }
  await navigateSourceRef({ source_type: 'task', source_id: String(taskId), navigation_key: taskKey })
}

function setDeadlineMaterialLoading(sourceRef, loadingState) {
  const key = sourceRefKey(sourceRef)
  if (!key) return
  const next = { ...deadlineMaterialLoading.value }
  if (loadingState) next[key] = true
  else delete next[key]
  deadlineMaterialLoading.value = next
}

async function openDeadlineMaterial(task) {
  const materialId = positiveMaterialId(task?.material_id)
  const materialName = safeText(task?.material_name)
  const materialKey = navigationKey(task?.material_navigation_key)
  if (materialId === null || task?.source_available !== true || !materialName || !materialKey) {
    ElMessage.warning(materialId !== null && materialName && !materialKey
      ? '暂不能确认资料来源，请从资料库查看。'
      : '该任务的资料状态不完整，已停止跳转。')
    return
  }
  const sourceRef = { source_type: 'material', source_id: String(materialId), navigation_key: materialKey }
  const cacheKey = sourceRefKey(sourceRef)
  if (deadlineMaterialLoading.value[cacheKey]) return

  setDeadlineMaterialLoading(sourceRef, true)
  try {
    const response = await agentApi.resolveSourceRefs([sourceRef])
    const target = validatedMaterialTarget(response, materialId, materialKey)
    if (!target) {
      const resolvedItem = Array.isArray(response?.items) && response.items.length === 1
        ? response.items[0]
        : null
      const unavailableMessage = resolvedItem?.available === false
        ? safeText(resolvedItem.message, '这份资料当前不可打开。')
        : '资料入口校验失败，已停止跳转。'
      ElMessage.warning(unavailableMessage)
      return
    }
    await router.push(target)
  } catch (err) {
    ElMessage.error(err?.message || '资料入口暂时无法解析，请稍后重试。')
  } finally {
    setDeadlineMaterialLoading(sourceRef, false)
  }
}

function openMaterialUpload() {
  router.push({ path: '/materials', query: { action: 'upload' } })
}

function openLearningInbox() {
  router.push({ path: '/materials', query: { view: 'current_inbox' } })
}

async function openDetailedLedger(targetId = 'detailed-learning-ledger') {
  setViewMode('detailed')
  await nextTick()
  const detailedLoad = loadDetailedLedgerData()
  await detailedLoad
  await nextTick()
  window.requestAnimationFrame(() => {
    const target = document.getElementById(typeof targetId === 'string' ? targetId : 'detailed-learning-ledger')
    if (!target) return
    target.scrollIntoView({ block: 'start' })
    target.focus({ preventScroll: true })
  })
}

async function handleDecisionFocus(decision) {
  if (decision.kind === 'plan_delta_review') {
    await openDetailedLedger('plan-deltas')
    return
  }
  const ref = decisionSourceRefs(decision)[0]
  if (ref) await navigateSourceRef(ref)
}

async function handleActionCandidate(action) {
  if (!action) return
  if (isNavigableAction(action)) {
    await navigateAction(action)
    return
  }
  if (isExecutableAction(action) && action.action_type === 'set_task_estimate') {
    openEstimateAction(action)
    return
  }
  if (isExecutableAction(action)) await executeAction(action)
}

async function handleFocusAction() {
  const source = focusStageSource.value
  if (!source) return
  if (source.kind === 'decision') {
    await handleDecisionFocus(source.item)
    return
  }
  await handleActionCandidate(source.item)
}

async function handleFocusAttention(item) {
  if (!item || item.actionDisabled) return
  if (item.sourceKind === 'decision') {
    await handleDecisionFocus(item.source)
    return
  }
  if (item.sourceKind === 'reminder') {
    await navigateReminder(item.source)
    return
  }
  if (item.sourceKind === 'action') {
    await handleActionCandidate(item.source)
    return
  }
  await openDetailedLedger(item.targetId || 'detailed-learning-ledger')
}

const firstLearningLoopRoutes = Object.freeze({
  course: { path: '/settings', query: { action: 'create-course' } },
  material: { path: '/materials', query: { action: 'upload' } },
  task: { path: '/tasks', query: { action: 'create-task' } },
  complete: { path: '/tasks' },
})

function navigateFirstLearningLoop(action) {
  const target = firstLearningLoopRoutes[action] || firstLearningLoopRoutes.task
  return router.push(target)
}

async function openFirstLearningMaterial() {
  if (firstLoopMaterialRef.value) {
    await navigateSourceRef(firstLoopMaterialRef.value)
    return
  }
  await navigateFirstLearningLoop('task')
}

function dashboardCountDisplay(key) {
  return dashboardState.value === 'ready' ? dashboard.value[key] : '—'
}

async function goToMaterial(material) {
  const materialId = positiveMaterialId(material?.id)
  const materialKey = navigationKey(material?.navigation_key)
  if (materialId !== null && materialKey) {
    await navigateSourceRef({ source_type: 'material', source_id: String(materialId), navigation_key: materialKey })
    return
  }
  router.push({ path: '/materials', query: { q: material?.original_filename } })
}

function dueLabel(task) {
  if (isOverdue(task)) return '已逾期 · ' + formatDateTime(task.due_at)
  return task.due_at ? '截止 ' + formatDateTime(task.due_at) : '未设置截止时间'
}

function materialType(material) {
  return material.material_type || material.file_type || '未分类'
}

function firstDefined(source, keys, fallback = null) {
  if (!source || typeof source !== 'object') return fallback
  const key = keys.find((candidate) => source[candidate] !== undefined && source[candidate] !== null)
  return key ? source[key] : fallback
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function nonNegativeInteger(value) {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null
}

function emptyDashboard() {
  return {
    active_task_count: null,
    due_soon_count: null,
    overdue_count: null,
    completed_task_count: null,
    study_streak_days: 0,
    materials_count: null,
    courses_count: null,
    next_action: '',
    upcoming_tasks: [],
    overdue_tasks: [],
    recent_materials: [],
  }
}

function normalizeDashboard(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response)) return null
  const countKeys = [
    'active_task_count', 'due_soon_count', 'overdue_count',
    'completed_task_count', 'materials_count', 'courses_count',
  ]
  const counts = {}
  for (const key of countKeys) {
    const value = nonNegativeInteger(response[key])
    if (value === null) return null
    counts[key] = value
  }
  // Streak is an optional newer field: an absent value reads as no streak
  // instead of rejecting the whole dashboard.
  counts.study_streak_days = nonNegativeInteger(response.study_streak_days) ?? 0
  if (!Array.isArray(response.upcoming_tasks) || !Array.isArray(response.overdue_tasks) || !Array.isArray(response.recent_materials)) return null
  return { ...response, ...counts }
}

function collectionCount(value) {
  if (Array.isArray(value)) return value.length
  if (value && typeof value === 'object') return Object.keys(value).length
  return numberOrNull(value)
}

function normalizeCapacity(response) {
  let data = response?.capacity || response?.data || response || {}
  if (data?.capacity && typeof data.capacity === 'object') data = data.capacity
  if (!data || typeof data !== 'object' || Array.isArray(data)) data = {}
  const availableMinutes = firstDefined(data, ['effective_capacity_minutes', 'available_minutes', 'available_capacity_minutes', 'capacity_minutes'])
  const knownWorkloadMinutes = firstDefined(data, ['known_workload_minutes', 'workload_minutes', 'known_minutes'])
  const missingTaskIds = firstDefined(data, ['missing_estimate_task_ids'])
  const missingCount = firstDefined(data, ['missing_estimates_count', 'missing_estimate_count', 'missing_duration_count', 'tasks_missing_estimates'], collectionCount(missingTaskIds))
  const sameDayGroups = firstDefined(data, ['same_day_deadline_groups'])
  const sameDayCount = firstDefined(data, ['same_day_ddl_count', 'same_day_deadline_count', 'same_day_conflict_count', 'multi_ddl_days'], collectionCount(sameDayGroups))
  const dailyRiskGroups = firstDefined(data, ['daily_risk_groups'])
  const dailyOverloadCount = Array.isArray(dailyRiskGroups)
    ? dailyRiskGroups.filter((group) => String(group?.risk_level || '').toLowerCase() === 'high').length
    : null
  const reportedRatio = firstDefined(data, ['load_ratio', 'workload_ratio', 'utilization_ratio'])
  const availableNumber = numberOrNull(availableMinutes)
  const knownNumber = numberOrNull(knownWorkloadMinutes)
  return {
    ...data,
    available_minutes: availableMinutes,
    known_workload_minutes: knownWorkloadMinutes,
    load_ratio: reportedRatio ?? (availableNumber !== null && availableNumber > 0 && knownNumber !== null ? knownNumber / availableNumber : null),
    risk_level: firstDefined(data, ['risk_level', 'risk']),
    missing_estimate_task_ids: missingTaskIds,
    missing_estimates_count: missingCount,
    same_day_deadline_groups: sameDayGroups,
    same_day_ddl_count: sameDayCount,
    daily_risk_groups: dailyRiskGroups,
    daily_overload_count: dailyOverloadCount,
    calculation_basis: firstDefined(data, ['calculation_basis', 'basis', 'explanation', 'reason']),
  }
}

function capacityRiskInfo(data) {
  const missing = numberOrNull(data.missing_estimates_count)
  const completeMetrics = [data.available_minutes, data.known_workload_minutes, data.load_ratio].every((value) => numberOrNull(value) !== null)
  const level = String(data.risk_level || '').toLowerCase()
  const labels = {
    low: { label: '当前可控', type: 'success' },
    medium: { label: '需要留意', type: 'warning' },
    high: { label: '容量紧张', type: 'danger' },
    critical: { label: '容量不足', type: 'danger' },
  }
  if (level === 'high') return labels.high
  if (missing === null || missing > 0 || !completeMetrics || !labels[level]) return { label: '需补充数据', type: 'warning' }
  return labels[level]
}

function formatMinutes(value) {
  const minutes = numberOrNull(value)
  if (minutes === null) return '待补充'
  const rounded = Math.max(0, Math.round(minutes))
  const hours = Math.floor(rounded / 60)
  const remainder = rounded % 60
  if (!hours) return `${remainder}分钟`
  if (!remainder) return `${hours}小时`
  return `${hours}小时${remainder}分钟`
}

function formatCount(value, unit = '项') {
  const count = numberOrNull(value)
  return count === null ? '待补充' : `${Math.max(0, Math.round(count))} ${unit}`
}

function formatLoadRatio(value) {
  const ratio = numberOrNull(value)
  if (ratio === null) return '待补充'
  const percent = ratio <= 1 ? ratio * 100 : ratio
  return `${Math.round(percent)}%`
}

function capacityBasisText(data) {
  const raw = data.calculation_basis
  let basis = ''
  if (Array.isArray(raw)) basis = raw.filter(Boolean).join('；')
  else if (typeof raw === 'string') basis = raw
  else if (raw && typeof raw === 'object') {
    const buffer = numberOrNull(raw.buffer_ratio)
    basis = [
      raw.task_filter ? `统计范围：${raw.task_filter}` : '',
      raw.workload_formula ? `工作量公式：${raw.workload_formula}` : '',
      raw.weekly_available_minutes !== undefined ? `每周可用 ${raw.weekly_available_minutes} 分钟` : '',
      raw.daily_limit_minutes !== undefined ? `单日上限 ${raw.daily_limit_minutes} 分钟` : '',
      buffer !== null ? `缓冲 ${Math.round(buffer * 100)}%` : '',
      raw.effective_capacity_minutes !== undefined ? `有效容量 ${raw.effective_capacity_minutes} 分钟` : '',
      raw.effective_daily_capacity_minutes !== undefined ? `单日有效容量 ${raw.effective_daily_capacity_minutes} 分钟` : '',
      raw.summary || raw.description || raw.text || '',
    ].filter(Boolean).join('；')
  }
  if (!basis) basis = '根据每周可用分钟、单日上限、缓冲比例与任务剩余用时计算。'
  const missing = numberOrNull(data.missing_estimates_count)
  if (missing === null) return `${basis} 当前缺失估时统计，风险等级仅作提醒。`
  if (missing > 0) return `${basis} 仍有 ${Math.round(missing)} 项任务缺少预计或剩余用时，风险等级不会被当作精确低风险。`
  return basis
}

function payloadValue(payload, key) {
  if (!payload || typeof payload !== 'object') return null
  return payload[key]
}

function normalizePriority(value, fallback = 4) {
  const priority = Number(value)
  return priority === 4 || priority === 5 ? priority : fallback
}

function currentPriority(suggestion) {
  const value = payloadValue(suggestion.current_payload, 'priority')
  return value === null || value === undefined ? '未设置' : value
}

function proposedPriority(suggestion) {
  return normalizePriority(payloadValue(suggestion.proposed_payload, 'priority'), 4)
}

function sourceLabel(suggestion) {
  const source = suggestion.source_name || suggestion.source_type || '学习任务'
  return suggestion.source_id ? `${source} · ${suggestion.source_id}` : source
}

function deadlineValue(suggestion) {
  return (
    payloadValue(suggestion.current_payload, 'due_at') ||
    payloadValue(suggestion.current_payload, 'deadline') ||
    payloadValue(suggestion.proposed_payload, 'due_at') ||
    suggestion.due_at ||
    suggestion.expires_at
  )
}

function deadlineLabel(suggestion) {
  const value = deadlineValue(suggestion)
  return value ? formatDateTime(value) : '未设置'
}

function riskLabel(level) {
  return { low: '低', medium: '中', high: '高', critical: '高' }[String(level || '').toLowerCase()] || '待评估'
}

function riskType(level) {
  return { low: 'success', medium: 'warning', high: 'danger', critical: 'danger' }[String(level || '').toLowerCase()] || 'info'
}

function focusTone(level) {
  return { high: 'coral', critical: 'coral', medium: 'amber' }[String(level || '').toLowerCase()] || 'neutral'
}

function conciseFocusDetail(value) {
  const detail = safeText(value)
  if (!detail) return ''
  return detail.split('；').filter(Boolean)[0] || detail
}

function decisionFocusItem(decision) {
  const ref = decisionSourceRefs(decision)[0] || null
  return {
    kind: '需要你确认',
    kicker: decisionSourceTypeLabel(decision),
    title: decision.title,
    detail: decision.description,
    meta: `下一步：${decision.action_label}`,
    tone: focusTone(decision.priority),
    badge: decisionPriorityLabel(decision.priority),
    actionLabel: decision.action_label,
    actionDisabled: !ref || isSourceUnavailable(ref),
    actionLoading: ref ? isSourceNavigationLoading(ref) : false,
  }
}

function focusActionLabel(action) {
  if (isNavigableAction(action)) return action.target_ids?.task_id ? '打开任务' : '查看并处理'
  if (isExecutableAction(action) && action.action_type === 'set_task_estimate') return '补充估时'
  if (isExecutableAction(action)) return actionButtonLabel(action)
  return actionUnavailableLabel(action)
}

function focusActionDisabled(action) {
  if (isNavigableAction(action)) {
    const refs = actionSourceRefs(action)
    return Boolean(refs.length) && refs.every(isSourceUnavailable)
  }
  return !isExecutableAction(action)
}

function focusActionLoading(action) {
  if (isNavigableAction(action)) return actionSourceRefs(action).some(isSourceNavigationLoading)
  return isAnyActionLoading(actionActionKey(action))
}

function todayActionFocusItem(action) {
  const course = action.course_name || '未归类课程'
  return {
    kind: '今天先做',
    kicker: slotLabel(action.suggested_slot),
    title: action.task_name || action.title || '待处理任务',
    detail: conciseFocusDetail(action.reason) || '系统已将这项任务排入今天的行动列表。',
    meta: `${course} · ${dueLabel(action)}`,
    tone: focusTone(action.risk_level),
    badge: `${riskLabel(action.risk_level)}风险`,
    actionLabel: focusActionLabel(action),
    actionDisabled: focusActionDisabled(action),
    actionLoading: focusActionLoading(action),
  }
}

function decisionAttentionItem(decision) {
  const ref = decisionSourceRefs(decision)[0] || null
  return {
    id: `focus-decision-${decision.decision_id}`,
    sourceKind: 'decision',
    source: decision,
    title: decision.title,
    detail: decision.description,
    tone: focusTone(decision.priority),
    badge: decisionPriorityLabel(decision.priority),
    actionLabel: decision.action_label,
    actionDisabled: !ref || isSourceUnavailable(ref),
  }
}

function actionAttentionItem(action) {
  return {
    id: `focus-action-${action.ui_key}`,
    sourceKind: 'action',
    source: action,
    title: action.task_name || action.title || '待处理任务',
    detail: conciseFocusDetail(action.reason),
    tone: focusTone(action.risk_level),
    badge: `${riskLabel(action.risk_level)}风险`,
    actionLabel: focusActionLabel(action),
    actionDisabled: focusActionDisabled(action),
  }
}

function reminderAttentionItem(reminder) {
  const canNavigate = isNavigableReminder(reminder)
  const canExecute = isExecutableAction(reminder)
  return {
    id: `focus-reminder-${reminder.ui_key}`,
    sourceKind: canNavigate ? 'reminder' : canExecute ? 'action' : 'details',
    source: reminder,
    targetId: 'detailed-learning-ledger',
    title: reminder.title || '高风险提醒',
    detail: conciseFocusDetail(reminder.reason || reminder.explanation),
    tone: focusTone(reminder.severity),
    badge: `${reminderSeverityLabel(reminder.severity)}风险`,
    actionLabel: canNavigate ? '查看' : canExecute ? focusActionLabel(reminder) : '查看详情',
    actionDisabled: false,
  }
}

function buildFocusAttentionItems(selected) {
  const items = []
  const selectedItem = selected?.item || null
  const seen = new Set()
  const add = (item) => {
    if (!item || seen.has(item.id)) return
    seen.add(item.id)
    items.push(item)
  }

  decisionQueue.value.forEach((decision, index) => {
    if (decision === selectedItem) return
    if (['critical', 'high'].includes(decision.priority) || (selected?.kind === 'action' && index === 0)) {
      add(decisionAttentionItem(decision))
    }
  })
  todayActions.value.forEach((action) => {
    if (action === selectedItem) return
    if (['critical', 'high'].includes(action.risk_level)) add(actionAttentionItem(action))
  })
  reminders.value.forEach((reminder) => {
    if (reminder.severity === 'high') add(reminderAttentionItem(reminder))
  })

  if (capacityError.value || (capacityLoaded.value && capacityRisk.value.type !== 'success')) {
    add({
      id: 'focus-capacity',
      sourceKind: 'details',
      targetId: 'risk-center',
      title: capacityError.value ? '容量状态暂不可用' : capacityRisk.value.label,
      detail: capacityError.value || '容量指标需要查看或补充，页面不会把未知数据当作低风险。',
      tone: capacityRisk.value.type === 'danger' ? 'coral' : 'amber',
      badge: '容量',
      actionLabel: '查看容量',
      actionDisabled: false,
    })
  }
  return items
}

function confidenceLabel(value) {
  const confidence = Number(value)
  if (!Number.isFinite(confidence)) return value
  return `${Math.round(confidence <= 1 ? confidence * 100 : confidence)}%`
}

function suggestionStatusLabel(status) {
  return {
    pending: '待确认',
    accepted: '已接受',
    executed: '已执行',
    failed: '执行失败',
    dismissed: '已忽略',
    expired: '已过期',
  }[String(status || '').toLowerCase()] || '未知状态'
}

function suggestionStatusType(status) {
  return {
    pending: 'warning',
    accepted: 'info',
    executed: 'success',
    failed: 'danger',
    dismissed: 'info',
    expired: 'info',
  }[String(status || '').toLowerCase()] || 'info'
}

function inboxStatusLabel(status) {
  return {
    ready: '待处理',
    needs_review: '待确认',
    failed: '处理失败',
  }[String(status || '').toLowerCase()] || '待追踪'
}

function actionTypeLabel(actionType) {
  return {
    set_task_estimate: '补充任务估时',
    start_task: '开始任务',
    adjust_priority: '调整优先级',
    review: '查看确认项',
    navigate: '打开相关内容',
    review_daily_overload: '确认当日超载',
    navigate_same_day_deadlines: '查看同日截止任务',
    complete_task: '完成任务',
    reset_course_calibration: '重置课程校准',
    apply_plan_delta: '应用计划差异',
  }[String(actionType || '').toLowerCase()] || '学习安排动作'
}

function weeklyMetricValue(metric) {
  if (!metric || metric.status === 'unknown') return '暂无数据'
  if (metric.value === null || metric.value === undefined) return '待补充'
  const value = Math.round(Number(metric.value))
  const prefix = metric.allow_negative && value > 0 ? '+' : ''
  return `${prefix}${value}${metric.unit || '项'}`
}

function actionSourceLabel(action) {
  const refs = Array.isArray(action?.source_refs) ? action.source_refs : []
  const firstRef = objectOrEmpty(refs[0])
  if (refs.length) {
    const labels = refs.slice(0, 3).map((ref) => {
      const name = safeText(ref.source_name || ref.source_type, '来源')
      return ref.source_id !== undefined && ref.source_id !== null ? `${name} · ${ref.source_id}` : name
    })
    return `${labels.join('、')}${refs.length > 3 ? `（另有 ${refs.length - 3} 条）` : ''}`
  }
  const source = safeText(
    action?.source_name
      || action?.course_name
      || firstRef.source_name
      || action?.source_type
      || firstRef.source_type,
    '系统安排',
  )
  const sourceId = action?.source_id || action?.target_id
  const refId = firstRef.source_id
  const suffix = refId || sourceId
  const countSuffix = refs.length > 1 ? `（共 ${refs.length} 条来源）` : ''
  if (!suffix || action?.target_type === 'local_date') return `${source}${countSuffix}`
  return `${source} · ${suffix}${countSuffix}`
}

function executionModeLabel(mode) {
  return {
    accept: '确认后执行',
    review: '仅供确认',
    navigate: '仅导航',
  }[String(mode || '').toLowerCase()] || '安排方式未说明'
}

function reminderSeverityLabel(level) {
  return { high: '高', medium: '中', low: '低' }[String(level || '').toLowerCase()] || '待分级'
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

function minutesLabel(value) {
  const minutes = numberOrNull(value)
  return minutes === null ? '待补估时' : `${Math.max(0, Math.round(minutes))} 分钟`
}

function minuteSourceLabel(value) {
  return {
    remaining_minutes: '按剩余用时',
    estimated_minutes: '按预计用时',
  }[String(value || '').toLowerCase()] || safeText(value, '已知用时')
}

function slotLabel(slot) {
  return { morning: '上午', afternoon: '下午', evening: '晚上' }[String(slot || '').toLowerCase()] || '未指定'
}

function sortBasisLabel(value) {
  return Array.isArray(value) && value.length ? value.join('；') : '排序依据暂未说明'
}

function targetLabel(action) {
  const ids = action.target_ids || {}
  const targets = []
  if (ids.task_id) targets.push(`任务 #${ids.task_id}`)
  if (ids.material_id) targets.push(`资料 #${ids.material_id}`)
  if (ids.course_id) targets.push(`课程 #${ids.course_id}`)
  if (!targets.length && action.target_type === 'local_date' && action.target_id) targets.push(`日期 ${action.target_id}`)
  if (!targets.length && action.target_type === 'task' && action.target_id) targets.push(`任务 #${action.target_id}`)
  return targets.length ? targets.join('、') : '目标待补充'
}

function actionActionKey(action) {
  return String(action.suggestion_id || action.ui_key)
}

function actionTargetAvailable(action) {
  const ids = action.target_ids || {}
  if (['set_task_estimate', 'start_task', 'adjust_priority'].includes(action.action_type)) {
    return Boolean(ids.task_id || (action.target_type === 'task' && action.target_id))
  }
  if (['review_daily_overload', 'navigate_same_day_deadlines'].includes(action.action_type)) {
    return action.target_type === 'local_date' && Boolean(action.target_id)
  }
  return Boolean(ids.task_id || ids.material_id || ids.course_id || (action.target_type && action.target_id))
}

function actionSourceRefs(action) {
  const refs = Array.isArray(action?.source_refs)
    ? action.source_refs.map(normalizeSourceRef).filter((ref) => ref.source_type && ref.source_id !== null)
    : []
  if (refs.length) return refs
  const fallback = normalizeSourceRef({
    source_type: action?.source_type,
    source_id: action?.source_id,
    navigation_key: action?.source_navigation_key,
    source_name: action?.source_name,
  })
  return fallback.source_type && fallback.source_id !== null ? [fallback] : []
}

function evidenceSourceItems(refs, context = '') {
  return uniqueSourceRefs((Array.isArray(refs) ? refs : []).map(normalizeSourceRef).filter((ref) => ref.source_type && ref.source_id !== null))
    .map((ref) => ({
      key: sourceRefKey(ref),
      label: sourceRefButtonLabel(ref),
      ariaLabel: `${context ? `${context}：` : ''}打开${sourceRefDisplayLabel(ref)}来源`,
      disabled: isSourceUnavailable(ref),
      loading: isSourceNavigationLoading(ref),
      payload: ref,
    }))
}

function isExecutableAction(action) {
  return controlledActionTypes.has(action.action_type)
    && !['review', 'navigate', 'review_daily_overload', 'navigate_same_day_deadlines'].includes(action.action_type)
    && Boolean(action.suggestion_id)
    && actionTargetAvailable(action)
    && (!action.execution_mode || action.execution_mode === 'accept')
    && (!action.status || action.status === 'pending')
}

function isNavigableAction(action) {
  const navigationMode = (
    ['review', 'navigate', 'review_daily_overload', 'navigate_same_day_deadlines'].includes(action.action_type)
      || ['review', 'navigate'].includes(action.execution_mode)
  )
  if (!navigationMode) return false
  return actionSourceRefs(action).some(sourceRefNavigable)
}

function actionButtonLabel(action) {
  return { start_task: '开始任务', adjust_priority: '执行调整' }[action.action_type] || '执行行动'
}

async function goToBriefingMaterial(material) {
  const materialId = positiveMaterialId(material?.id)
  const materialKey = navigationKey(material?.navigation_key)
  if (materialId !== null && materialKey) {
    await navigateSourceRef({ source_type: 'material', source_id: String(materialId), navigation_key: materialKey })
    return
  }
  // Inbox summaries from old contracts contain only a numeric bucket id.
  // Keep them useful as a named collection, but never treat that id as a
  // verified link to a newly recreated material.
  router.push({ path: '/materials', query: { view: 'current_inbox' } })
}

async function navigateAction(action) {
  const refs = actionSourceRefs(action).filter(sourceRefNavigable)
  if (refs.length) {
    await navigateResolvedSourceRefs(refs)
    return
  }
  announceSourceUnavailable('暂时没有可用的安全来源入口。')
}

function actionUnavailableLabel(action) {
  if (action.status && action.status !== 'pending') return `当前状态：${suggestionStatusLabel(action.status)}`
  if (['set_task_estimate', 'start_task', 'adjust_priority'].includes(action.action_type) && !action.suggestion_id) {
    return '缺少建议 ID，无法执行'
  }
  if (controlledActionTypes.has(action.action_type) && !actionTargetAvailable(action)) {
    return '缺少受控目标，无法执行'
  }
  if (action.action_type && !controlledActionTypes.has(action.action_type)) {
    return '暂不支持该动作'
  }
  return '等待系统提供可执行的操作'
}

function isExecutedResult(result) {
  return result?.status === 'executed' && result?.receipt?.outcome === 'executed'
}

const isEstimateActionLoading = computed(() => {
  return Boolean(estimateAction.value && isActionLoading(actionActionKey(estimateAction.value), 'execute'))
})

function objectOrEmpty(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function safePositiveId(value) {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : null
}

function safeText(value, fallback = '') {
  return typeof value === 'string' ? value.trim() : fallback
}

function normalizeSourceRef(ref) {
  const item = objectOrEmpty(ref)
  const sourceType = safeText(item.source_type || item.type).toLowerCase()
  const rawId = item.source_id ?? item.id
  const numericId = safePositiveId(rawId)
  const sourceId = numericId !== null
    ? numericId
    : typeof rawId === 'string' && rawId.trim() && rawId.trim().length <= 128
      ? rawId.trim()
      : null
  const key = navigationKey(item.navigation_key)
  return {
    source_type: sourceType,
    source_id: sourceId,
    navigation_key: key,
    source_name: safeText(item.source_name || item.name),
  }
}

const sourceRefTypeLabels = Object.freeze({
  task: '任务',
  material: '资料',
  study_plan: '复习计划',
  study_plan_item: '复习计划项',
  action_receipt: '操作结果',
  task_collection: '任务集合',
  material_collection: '资料集合',
  study_plan_collection: '复习计划集合',
  capacity: '学习容量',
})

function sourceRefKey(ref) {
  const item = normalizeSourceRef(ref)
  if (!item.source_type || item.source_id === null) return ''
  return navigationSourceCacheKey(item) || `${item.source_type}:${String(item.source_id)}:${item.navigation_key || 'invalid'}`
}

function sourceRefDisplayLabel(ref) {
  const item = normalizeSourceRef(ref)
  const name = safeText(item.source_name) || sourceRefTypeLabels[item.source_type] || '来源'
  return item.source_id === null ? name : `${name} · ${item.source_id}`
}

function sourceRefButtonLabel(ref) {
  const entry = sourceNavigation.value[sourceRefKey(ref)]
  if (entry?.available === false) return `不可用：${entry.label || sourceRefDisplayLabel(ref)}`
  if (entry?.loading) return '检查来源…'
  return entry?.label || sourceRefDisplayLabel(ref)
}

function activitySourceRef(item) {
  const raw = objectOrEmpty(item?.source_ref)
  if (!raw.source_type && raw.source_id === null) return null
  const ref = normalizeSourceRef({ ...raw, source_name: item?.source_label || raw.source_name })
  return ref.source_type ? ref : null
}

function activitySourceDisplayLabel(item) {
  const ref = activitySourceRef(item)
  return safeText(item?.source_label) || (ref ? sourceRefDisplayLabel(ref) : '来源')
}

function activitySourceCanNavigate(item) {
  const ref = activitySourceRef(item)
  if (!ref || item?.source_available === false || !sourceRefNavigable(ref)) return false
  const entry = sourceNavigation.value[sourceRefKey(ref)]
  return entry?.available !== false
}

function activitySourceButtonLabel(item) {
  const ref = activitySourceRef(item)
  if (!ref) return '来源待补充'
  const entry = sourceNavigation.value[sourceRefKey(ref)]
  if (entry?.loading) return '检查来源…'
  return entry?.label || safeText(item?.source_label) || sourceRefDisplayLabel(ref)
}

function activitySourceButtonAriaLabel(item) {
   const activityLabel = safeText(item?.title, '学习处理')
  const sourceLabel = safeText(activitySourceDisplayLabel(item), '来源')
  return `打开活动“${activityLabel}”的${sourceLabel}来源`
}

function activitySourceUnavailableLabel(item) {
  const ref = activitySourceRef(item)
   const activityLabel = safeText(item?.title, '学习处理')
   if (!ref) return `处理“${activityLabel}”的${safeText(item?.source_message) || '来源待补充'}`
   if (item?.source_available === false) return `处理“${activityLabel}”的${safeText(item?.source_message) || `来源不可用：${safeText(item?.source_label) || sourceRefDisplayLabel(ref)}`}`
  const entry = sourceNavigation.value[sourceRefKey(ref)]
   if (entry?.available === false) return `处理“${activityLabel}”的${safeText(item?.source_message) || safeText(entry.message) || `来源不可用：${entry.label || safeText(item?.source_label) || sourceRefDisplayLabel(ref)}`}`
   if (!sourceRefNavigable(ref)) return `处理“${activityLabel}”的来源类型或编号不受支持`
   return `处理“${activityLabel}”的来源待确认`
}

function isSourceNavigationLoading(ref) {
  return Boolean(sourceNavigationLoading.value[sourceRefKey(ref)])
}

function normalizeNavigationTarget(target) {
  const item = objectOrEmpty(target)
  const path = safeText(item.path)
  if (!['/tasks', '/materials', '/study-plans'].includes(path)) return null
  const rawQuery = objectOrEmpty(item.query)
  const allowedKeys = {
    '/tasks': ['task_id', 'course_id', 'material_id', 'date', 'q', 'view'],
    '/materials': ['material_id', 'course_id', 'q', 'view'],
    '/study-plans': ['plan_id', 'study_plan_id', 'course_id', 'item_id', 'view'],
  }[path]
  const allowedViews = new Set([
    'weekly_overdue', 'weekly_estimate_variance', 'capacity_next_7_days',
    'current_inbox', 'failed_materials', 'review_materials', 'weekly_plan_delays',
  ])
  const query = {}
  for (const key of allowedKeys) {
    const value = rawQuery[key]
    if (value === null || value === undefined || value === '') continue
    if (key === 'date') {
      if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) query[key] = value
      continue
    }
    if (key === 'q') {
      const text = safeText(value)
      if (text && text.length <= 120) query[key] = text
      continue
    }
    if (key === 'view') {
      if (typeof value === 'string' && allowedViews.has(value)) query[key] = value
      continue
    }
    if (key === 'item_id') {
      const itemId = safeText(value)
      if (itemId && itemId.length <= 80 && !/[\u0000-\u001f]/.test(itemId)) query[key] = itemId
      continue
    }
    const id = safePositiveId(value)
    if (id !== null) query[key] = String(id)
  }
  return { path, ...(Object.keys(query).length ? { query } : {}) }
}

function normalizeReceipt(receipt) {
  if (!receipt || typeof receipt !== 'object') return null
  return {
    outcome: safeText(receipt.outcome),
    message: safeText(receipt.message),
    action_type: safeText(receipt.action_type),
    source_type: safeText(receipt.source_type),
    source_id: safePositiveId(receipt.source_id),
    navigation_key: navigationKey(receipt.navigation_key),
    source_navigation_key: navigationKey(receipt.source_navigation_key),
    executed_at: receipt.executed_at || null,
  }
}

function normalizeSuggestion(suggestion) {
  const item = objectOrEmpty(suggestion)
  const id = safePositiveId(item.id)
  if (!id) return null
  return {
    id,
    action_type: safeText(item.action_type),
    status: safeText(item.status, 'pending'),
    source_type: safeText(item.source_type),
    source_id: safePositiveId(item.source_id),
    source_navigation_key: navigationKey(item.source_navigation_key),
    source_name: safeText(item.source_name),
    title: safeText(item.title, '学习安排建议'),
    explanation: safeText(item.explanation),
    reason_code: safeText(item.reason_code),
    current_payload: objectOrEmpty(item.current_payload),
    proposed_payload: objectOrEmpty(item.proposed_payload),
    risk_level: safeText(item.risk_level),
    confidence: numberOrNull(item.confidence),
    expires_at: item.expires_at || null,
    created_at: item.created_at || null,
    updated_at: item.updated_at || null,
    receipt: normalizeReceipt(item.receipt),
  }
}

function planDeltaTriggerLabel(value) {
  const raw = safeText(value)
  return {
    task_completed: '关联任务已完成',
    task_created: '新增了关联任务',
    task_overdue: '关联任务已逾期',
    actual_minutes_changed: '收到了实际用时反馈',
    user_requested_reset: '用户请求重置估时依据',
  }[raw] || raw
}

function normalizePlanDelta(item, index = 0) {
  const data = objectOrEmpty(item)
  const rawId = data.suggestion_id ?? data.id ?? data.delta_id
  const id = safePositiveId(rawId) || safeText(rawId)
  if (!id) return null
  const lines = normalizePlanDeltaLines(data)
  const proposedPayload = objectOrEmpty(data.proposed_payload)
  const currentPayload = objectOrEmpty(data.current_payload)
  const protectedValue = data.protected_items || data.protected || data.locked_items || data.guardrails || data.invariants
  const protectedLines = planStateLines(protectedValue)
  if (!protectedLines.length) {
    protectedLines.push('已完成的计划项不会被覆盖', '手动修改过的计划项不会被覆盖')
  }
  const trigger = safeText(
    data.trigger_event
      || data.trigger
      || data.trigger_reason
      || data.event
      || data.reason
      || data.reason_code
      || proposedPayload.trigger
      || currentPayload.trigger,
  )
  return {
    id,
    ui_key: `plan-delta-${id}-${index}`,
    status: safeText(data.status, 'pending'),
    title: safeText(data.title || data.plan_title || data.name, '复习计划需要重新安排'),
    course_id: safePositiveId(data.course_id),
    course_name: safeText(data.course_name || data.course?.name || data.source_name),
    plan_id: safePositiveId(data.plan_id || data.study_plan_id || proposedPayload.plan_id || data.source_id),
    trigger: planDeltaTriggerLabel(trigger),
    explanation: safeText(data.explanation || data.message),
    before_lines: lines.before,
    after_lines: lines.after,
    protected_lines: protectedLines,
    receipt: normalizeReceipt(data.receipt),
  }
}

function normalizePlanDeltaList(response) {
  const data = objectOrEmpty(response)
  const raw = data.plan_deltas || data.plan_delta_candidates || data.pending_plan_deltas || data.items || response
  return listValue(raw).map((item, index) => normalizePlanDelta(item, index)).filter(Boolean).slice(0, 8)
}

function normalizeInbox(response) {
  const data = objectOrEmpty(response)
  const raw = objectOrEmpty(data.inbox || data.learning_inbox || data.inbox_summary)
  const hasSummary = ['ready_count', 'needs_review_count', 'failed_count', 'ready', 'needs_review', 'failed', 'materials', 'material_refs'].some((key) => Object.prototype.hasOwnProperty.call(raw, key))
  const bucket = (name) => {
    const rawValue = raw[name]
    const value = objectOrEmpty(rawValue)
    const count = numberOrNull(value.count ?? raw[`${name}_count`] ?? (typeof rawValue === 'number' ? rawValue : null))
    const ids = Array.isArray(value.material_ids)
      ? value.material_ids.map(safePositiveId).filter(Boolean)
      : []
    return {
      count: Math.max(0, Math.round(count ?? ids.length)),
      ids,
    }
  }
  const buckets = {
    ready: bucket('ready'),
    needs_review: bucket('needs_review'),
    failed: bucket('failed'),
  }
  const materialsRaw = Array.isArray(raw.materials) ? raw.materials : Array.isArray(raw.material_refs) ? raw.material_refs : []
  const listedMaterials = materialsRaw.slice(0, 8).map((material) => {
    const item = objectOrEmpty(material)
    return {
      id: safePositiveId(item.id ?? item.material_id),
      name: safeText(item.name || item.original_filename || item.source_name, '未命名资料'),
      status: safeText(item.status || item.processing_status || item.extraction_status),
    }
  })
  const bucketMaterials = ['ready', 'needs_review', 'failed'].flatMap((status) => buckets[status].ids.map((id) => ({
    id,
    name: `资料 #${id}`,
    status,
  })))
  const materials = [...listedMaterials, ...bucketMaterials]
    .filter((material, index, items) => material.id && items.findIndex((candidate) => candidate.id === material.id) === index)
    .slice(0, 8)
  return {
    available: hasSummary,
    ready_count: buckets.ready.count,
    needs_review_count: buckets.needs_review.count,
    failed_count: buckets.failed.count,
    materials,
  }
}

function listValue(value) {
  if (Array.isArray(value)) return value
  if (value && typeof value === 'object' && Array.isArray(value.items)) return value.items
  return []
}

function normalizeTargetIds(item) {
  const data = objectOrEmpty(item)
  const nested = objectOrEmpty(data.target_ids || data.targets || data.target)
  const targetType = safeText(data.target_type || nested.type)
  const targetId = data.target_id !== undefined && data.target_id !== null ? data.target_id : nested.id
  return {
    task_id: safePositiveId(nested.task_id ?? data.task_id ?? (targetType === 'task' ? targetId : null)),
    material_id: safePositiveId(nested.material_id ?? data.material_id ?? (targetType === 'material' ? targetId : null)),
    course_id: safePositiveId(nested.course_id ?? data.course_id ?? (targetType === 'course' ? targetId : null)),
  }
}

function normalizeSortBasis(value) {
  if (Array.isArray(value)) return value.filter((item) => typeof item === 'string' && item.trim()).map((item) => item.trim()).slice(0, 5)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  if (value && typeof value === 'object') {
    return Object.entries(value)
      .filter(([, item]) => item !== null && item !== undefined && item !== '')
      .map(([key, item]) => {
        const label = {
          deadline_hours: '距截止',
          course_weight: '课程权重',
          minute_source: '用时依据',
          effective_daily_capacity_minutes: '单日有效容量',
          deadline_risk: '截止风险',
          capacity_risk: '容量风险',
          same_day_conflict: '同日截止冲突',
          same_day_deadline_count: '同日截止数量',
          deadline: '截止因素',
          priority: '优先级因素',
          in_progress: '进行中因素',
          quick_win: '快速完成因素',
        }[key]
        if (key === 'deadline_hours') {
          const hours = numberOrNull(item)
          return hours === null ? '距截止：未设置' : hours < 0 ? '距截止：已逾期' : `距截止：${hours} 小时`
        }
        if (key === 'course_weight') return `课程权重：${item} 倍`
        if (key === 'minute_source') return `用时依据：${minuteSourceLabel(item)}`
        if (key.endsWith('_minutes')) return `${label || '时间因素'}：${item} 分钟`
        if (key.endsWith('_risk')) return `${label || '风险因素'}：${riskLabel(item)}风险`
        if (typeof item === 'object') return label ? `${label}：已纳入排序` : '已纳入排序因素'
        return label ? `${label}：${item}` : '已纳入排序因素'
      })
      .slice(0, 5)
  }
  return []
}

function normalizeActionCandidate(candidate, index, category) {
  const item = objectOrEmpty(candidate)
  const task = objectOrEmpty(item.task)
  const targetIds = normalizeTargetIds(item)
  const suggestionId = safePositiveId(item.suggestion_id ?? item.id)
  const actionType = safeText(
    item.action_type
      || item.controlled_action
      // A plain today action is still a server-ranked task; expose only a
      // route to that task when no executable suggestion was supplied.
      || (category === 'today' && targetIds.task_id ? 'navigate' : ''),
  )
  const targetType = safeText(item.target_type || (targetIds.task_id ? 'task' : ''))
  const targetId = item.target_id !== undefined && item.target_id !== null
    ? (['local_date', 'task_collection', 'study_plan_collection', 'material_collection', 'course_collection'].includes(targetType)
      ? safeText(item.target_id)
      : safePositiveId(item.target_id))
    : null
  const displayReasons = Array.isArray(item.display_reasons)
    ? item.display_reasons.filter((reason) => typeof reason === 'string' && reason.trim()).map((reason) => reason.trim())
    : []
  const sourceRefs = Array.isArray(item.source_refs)
    ? item.source_refs.slice(0, 50).map(normalizeSourceRef).filter((ref) => ref.source_type && ref.source_id !== null)
    : []
  if (!sourceRefs.length) {
    const fallbackType = safeText(item.source_type || item.source?.type).toLowerCase()
      || (targetIds.task_id ? 'task' : targetIds.material_id ? 'material' : targetIds.course_id ? 'course' : '')
    const fallbackId = item.source_id ?? item.source?.id ?? targetIds.task_id ?? targetIds.material_id ?? targetIds.course_id
    const fallbackRef = normalizeSourceRef({
      source_type: fallbackType,
      source_id: fallbackId,
      navigation_key: item.source_navigation_key || item.task_navigation_key || item.source?.navigation_key,
      source_name: item.source_name || item.source?.name || task.name,
    })
    if (fallbackRef.source_type && fallbackRef.source_id !== null) sourceRefs.push(fallbackRef)
  }
  const uiKey = `${category}-${suggestionId || 'unknown'}-${index}`
  return {
    ui_key: uiKey,
    suggestion_id: suggestionId,
    action_type: actionType,
    target_ids: targetIds,
    target_type: targetType,
    target_id: targetId,
    execution_mode: safeText(item.execution_mode),
    source_type: safeText(item.source_type || item.source?.type),
    source_id: safePositiveId(item.source_id || item.source?.id),
    source_navigation_key: navigationKey(item.source_navigation_key || item.task_navigation_key || item.source?.navigation_key),
    source_name: safeText(item.source_name || item.source?.name),
    source_refs: sourceRefs,
    navigation_target: normalizeNavigationTarget(item.navigation_target || item.navigation_target_hint || item.navigation),
    title: safeText(item.title || item.task_name || task.name),
    task_name: safeText(item.task_name || task.name || item.name),
    course_name: safeText(item.course_name || task.course_name),
    due_at: item.due_at || task.due_at || null,
    reason: safeText(item.reason || item.explanation || item.reason_text) || displayReasons.join('；'),
    risk_level: safeText(item.risk_level),
    estimated_minutes: numberOrNull(item.estimated_minutes ?? task.estimated_minutes),
    remaining_minutes: numberOrNull(item.remaining_minutes ?? task.remaining_minutes),
    counted_minutes: numberOrNull(item.counted_minutes ?? task.counted_minutes),
    minute_source: safeText(item.minute_source || task.minute_source),
    suggested_slot: safeText(item.suggested_slot || item.suggested_time_slot || item.preferred_time_slot),
    sort_basis: normalizeSortBasis(item.sort_basis || item.ranking_basis || item.sort_reason || item.score_basis || item.score_components),
    status: safeText(item.status, 'pending'),
    dismissible: item.dismissible !== undefined ? Boolean(item.dismissible) : item.can_dismiss !== undefined ? Boolean(item.can_dismiss) : Boolean(suggestionId),
    receipt: normalizeReceipt(item.receipt),
  }
}

function normalizeReminder(reminder, index) {
  const item = objectOrEmpty(reminder)
  const normalized = normalizeActionCandidate(item, index, 'reminder')
  const sourceRefs = Array.isArray(item.source_refs)
    ? item.source_refs.slice(0, 50).map(normalizeSourceRef).filter((ref) => ref.source_type && ref.source_id !== null)
    : normalized.source_refs
  const firstRef = objectOrEmpty(sourceRefs[0])
  const rawSeverity = safeText(item.severity || item.severity_level || item.level || item.priority_level || item.risk_level, 'medium').toLowerCase()
  const severity = ['critical', 'urgent', 'high'].includes(rawSeverity)
    ? 'high'
    : ['low', 'info'].includes(rawSeverity)
      ? 'low'
      : 'medium'
  const suggestionId = safePositiveId(item.suggestion_id)
  const reminderId = safePositiveId(item.id)
  return {
    ...normalized,
    ui_key: `reminder-${suggestionId || reminderId || `unknown-${index}`}`,
    // Reminders are a distinct server resource. Their id must never be sent
    // to the suggestion accept/dismiss endpoints.
    reminder_id: reminderId,
    suggestion_id: suggestionId,
    status: safeText(item.status, 'active'),
    source_type: safeText(item.source_type || firstRef.source_type),
    source_id: item.source_id !== undefined && item.source_id !== null ? item.source_id : firstRef.source_id,
    source_navigation_key: navigationKey(item.source_navigation_key || firstRef.navigation_key),
    source_name: safeText(item.source_name || firstRef.source_name),
    source_refs: sourceRefs,
    navigation_target: normalizeNavigationTarget(item.navigation_target || item.navigation_target_hint || item.navigation),
    target_type: safeText(firstRef.source_type || item.target_type),
    target_id: firstRef.source_id ?? item.target_id ?? null,
    severity,
    reason: safeText(item.reason || item.explanation || item.message || item.reason_text) || normalized.reason,
    dismissible: item.dismissible !== undefined
      ? Boolean(item.dismissible)
      : item.can_dismiss !== undefined
      ? Boolean(item.can_dismiss)
        : Boolean(item.id),
  }
}

function numericMetric(source, keys) {
  for (const key of keys) {
    const value = source?.[key]
    const candidate = Array.isArray(value)
      ? value.length
      : value && typeof value === 'object'
        ? (value.count ?? value.total ?? value.value)
        : value
    const number = numberOrNull(candidate)
    if (number !== null) return Math.max(0, Math.round(number))
  }
  return null
}

function textList(value) {
  if (Array.isArray(value)) return value.filter((item) => typeof item === 'string' && item.trim()).map((item) => item.trim()).slice(0, 6)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function normalizeWeeklyReview(response) {
  const data = objectOrEmpty(response)
  const nestedReviewKey = ['weekly_review', 'weeklyReview', 'review'].find((key) => Object.prototype.hasOwnProperty.call(data, key))
  const nestedReview = nestedReviewKey ? data[nestedReviewKey] : undefined
  const raw = nestedReviewKey ? objectOrEmpty(nestedReview) : objectOrEmpty(response)
  const metricsSource = {
    ...data,
    ...objectOrEmpty(raw.metrics),
    ...objectOrEmpty(raw.summary),
    ...raw,
  }
  const metricDefinitions = [
    { key: 'completed', label: '近 7 天完成', keys: ['completed_count', 'completed_tasks', 'completed'], detail: '已完成任务数' },
    { key: 'overdue', label: '近 7 天逾期', keys: ['overdue_count', 'overdue_tasks', 'overdue'], detail: '进入逾期状态的任务数' },
    { key: 'plan_deviation', label: '计划偏差', keys: ['plan_deviation_count', 'plan_deviation', 'plan_deviations', 'plan_delta_count', 'plan_deltas', 'plan_item_status', 'plan_progress'], detail: '系统记录的延期计划项数' },
    { key: 'estimate_deviation', label: '估时偏差', keys: ['estimate_deviation_count', 'estimate_deviation', 'estimate_deviations', 'estimate_error_count', 'actual_vs_estimated_count', 'actual_minutes_deviation_count', 'estimate_variance'], detail: '已知任务的实际−预计用时' },
    { key: 'materials_review', label: '资料待确认', keys: ['materials_needs_review_count', 'material_needs_review_count', 'materials_pending_review', 'needs_review_material_count', 'materials_needs_review', 'materials_review', 'review_materials'], detail: '当前资料收件箱待确认数' },
  ]
  const metrics = metricDefinitions.map((definition) => ({
    ...definition,
    ...(() => {
      const value = numericMetric(metricsSource, definition.keys)
      const rawMetric = definition.keys
        .map((key) => metricsSource[key])
        .find((candidate) => candidate && typeof candidate === 'object' && !Array.isArray(candidate))
      return {
        value,
        unit: '项',
        allow_negative: false,
        status: safeText(rawMetric?.status, value === null ? 'unknown' : 'known'),
      }
    })(),
  }))
  const planMetric = metrics.find((metric) => metric.key === 'plan_deviation')
  const planProgress = objectOrEmpty(metricsSource.plan_item_status || metricsSource.plan_progress)
  const planBasis = objectOrEmpty(planProgress.calculation_basis)
  const delayedPlanCount = numberOrNull(planBasis.current_delayed_item_count ?? planBasis.delayed_count)
  if (planMetric && Object.keys(planProgress).length) {
    planMetric.value = delayedPlanCount
    planMetric.detail = delayedPlanCount === null ? '延期计划项数待补充' : '系统记录的延期计划项数'
  }
  const varianceMetric = metrics.find((metric) => metric.key === 'estimate_deviation')
  const estimateVariance = objectOrEmpty(metricsSource.estimate_variance)
  if (varianceMetric && Object.keys(estimateVariance).length) {
    varianceMetric.value = numberOrNull(estimateVariance.value)
    varianceMetric.unit = '分钟'
    varianceMetric.allow_negative = true
    varianceMetric.direction = safeText(estimateVariance.direction)
    const sampleCount = numberOrNull(estimateVariance.sample_count ?? estimateVariance.known_count)
    const missingCount = numberOrNull(estimateVariance.missing_count ?? estimateVariance.unknown_count)
    const directionLabel = { overrun: '总体超出预计', underrun: '总体少于预计', balanced: '总体与预计持平' }[varianceMetric.direction]
    varianceMetric.detail = sampleCount !== null && missingCount !== null
      ? `${directionLabel ? `${directionLabel} · ` : ''}已知 ${sampleCount} 项 · 缺少完整反馈 ${missingCount} 项`
      : '仅展示同时有预计和实际用时的记录'
  }
  const explicitMissing = textList(raw.missing_fields || raw.missing_data || raw.data_missing || data.weekly_missing_fields)
  const inferredMissing = metrics
    .filter((metric) => metric.status === 'unknown' || metric.value === null)
    .map((metric) => metric.label)
  const missingFields = [...new Set([...explicitMissing, ...inferredMissing])].slice(0, 8)
  const nextRaw = raw.next_week_actions || raw.next_actions || raw.actions || data.next_week_actions || data.next_actions
  const nextActions = listValue(nextRaw)
    .map((item, index) => normalizeActionCandidate(item, index, 'next-week'))
    .slice(0, 3)
  const rawReminders = data.reminders || raw.reminders || raw.in_app_reminders || data.in_app_reminders
  const normalizedReminders = listValue(rawReminders)
    .map(normalizeReminder)
    .filter(Boolean)
  const severityRank = { high: 0, medium: 1, low: 2 }
  normalizedReminders.sort((left, right) => severityRank[left.severity] - severityRank[right.severity])
  const reviewKeys = [
    'weekly_review', 'weeklyReview', 'review', 'metrics', 'summary', 'completed_count', 'overdue_count',
    'plan_deviation_count', 'plan_deviation', 'plan_item_status', 'plan_progress', 'estimate_deviation_count', 'estimate_deviation', 'actual_minutes_deviation_count', 'estimate_variance', 'materials_needs_review_count', 'material_needs_review_count', 'materials_review', 'review_materials', 'missing_fields',
    'next_week_actions', 'next_actions', 'period_label', 'period', 'window_label', 'evaluated_at',
  ]
  const hasNestedReview = Boolean(nestedReviewKey && nestedReview && typeof nestedReview === 'object')
  const hasDirectReview = reviewKeys
    .filter((key) => !['weekly_review', 'weeklyReview', 'review'].includes(key))
    .some((key) => Object.prototype.hasOwnProperty.call(data, key))
  const hasReviewPayload = hasNestedReview || hasDirectReview
  const available = raw.available !== undefined ? Boolean(raw.available) : hasReviewPayload
  return {
    available: Boolean(available),
    evaluated_at: raw.evaluated_at || raw.generated_at || data.weekly_evaluated_at || null,
    period_label: safeText(raw.period_label || raw.period || raw.window_label, '近 7 天'),
    metrics,
    missing_fields: missingFields,
    notes: textList(raw.notes || raw.limitations || raw.explanations || data.weekly_notes),
    next_actions: nextActions,
    reminders: normalizedReminders,
  }
}

function normalizeTrendStatus(value, fallback = 'unknown') {
  const status = String(value || '').trim().toLowerCase()
  return ['known', 'partial', 'unknown'].includes(status) ? status : fallback
}

function trendStatusLabel(status) {
  return { known: '已知', partial: '部分已知', unknown: '未知' }[status] || '未知'
}

function trendStatusType(status) {
  return { known: 'success', partial: 'warning', unknown: 'info' }[status] || 'info'
}

function normalizeLearningTrends(response) {
  const data = objectOrEmpty(response)
  const rawSignals = listValue(data.signals || data.items)
  const sampleCount = numberOrNull(data.sample_count)
  const knownCount = numberOrNull(data.known_count)
  const unknownCount = numberOrNull(data.unknown_count)
  const signals = rawSignals.map((item, index) => {
    const raw = objectOrEmpty(item)
    const actualMinutes = numberOrNull(raw.actual_minutes)
    const completedAt = raw.completed_at || raw.completedAt
    const difficulty = safeText(raw.difficulty)
    const rawRefs = listValue(raw.source_refs || raw.sources || raw.evidence)
    const evidence = rawRefs.map((ref) => objectOrEmpty(ref.snapshot)).find((snapshot) => snapshot.completed_at && numberOrNull(snapshot.actual_minutes) !== null && snapshot.difficulty !== null && snapshot.difficulty !== undefined)
    const hasEvidence = Boolean(completedAt && actualMinutes !== null && difficulty) || Boolean(evidence)
    const status = normalizeTrendStatus(raw.status, hasEvidence ? 'known' : 'unknown')
    const codeLabels = { learning_day_distribution: '学习日分布', longest_idle_gap: '最长空档', load_concentration: '负荷集中度', completion_pace: '完成节奏' }
    return {
      ...raw,
      ui_key: `learning-trend-${raw.id || raw.key || index}`,
      label: safeText(raw.label || raw.name || raw.signal || codeLabels[raw.code], '学习节奏信号'),
      summary: safeText(raw.summary || raw.explanation || raw.reason),
      status,
      sample_count: numberOrNull(raw.sample_count),
      evidence_label: hasEvidence ? `实际完成反馈（completed_at、actual_minutes、difficulty）` : '需要 completed_at、actual_minutes 和 difficulty 才能确认',
      source_refs: rawRefs.map(normalizeSourceRef).filter((ref) => ref.source_type && ref.source_id !== null),
    }
  })
  const candidates = listValue(data.adjustment_candidates).map((item, index) => {
    const raw = objectOrEmpty(item)
    return { ...raw, ui_key: `learning-trend-candidate-${raw.id || index}`, execution_mode: 'review', title: safeText(raw.title || raw.label), reason: safeText(raw.reason || raw.explanation) }
  })
  const hasPayload = Object.prototype.hasOwnProperty.call(data, 'signals') || Object.prototype.hasOwnProperty.call(data, 'status')
  return {
    available: data.available !== undefined ? Boolean(data.available) : hasPayload,
    status: normalizeTrendStatus(data.status, signals.length ? signals.some((item) => item.status === 'unknown') ? 'partial' : 'known' : 'unknown'),
    window_start: data.window_start || null,
    window_end: data.window_end || null,
    window_label: data.window_start && data.window_end ? `${String(data.window_start).slice(0, 10)} 至 ${String(data.window_end).slice(0, 10)}（结束不含）` : '窗口日期待补充',
    evaluated_at: data.evaluated_at || null,
    timezone: safeText(data.timezone, '时区待补充'),
    minimum_sample_count: numberOrNull(data.minimum_sample_count),
    sample_count: sampleCount,
    known_count: knownCount,
    unknown_count: unknownCount,
    limitations: textList(data.limitations),
    source_refs: listValue(data.source_refs || data.sources).map(normalizeSourceRef).filter((ref) => ref.source_type && ref.source_id !== null),
    signals,
    adjustment_candidates: candidates,
  }
}

function normalizeHistorySourceStatus(value) {
  const status = String(value || '').trim().toLowerCase()
  if (['complete', 'known', 'ready', '完整'].includes(status)) return 'complete'
  if (['partial', 'incomplete', 'partially_known', '部分'].includes(status)) return 'partial'
  return 'unknown'
}

function normalizeHistorySnapshotStatus(value) {
  const status = String(value || '').trim().toLowerCase()
  if (['current', 'open', 'active', '当前'].includes(status)) return 'current'
  if (['closed', 'archived', '封存', '已封存'].includes(status)) return 'closed'
  return 'unknown'
}

function normalizeHistoryMetric(metric, key, label, unit = '项', valueOverride = undefined) {
  const raw = objectOrEmpty(metric)
  const rawStatus = String(raw.status || '').trim().toLowerCase()
  const status = ['known', 'partial', 'unknown'].includes(rawStatus)
    ? rawStatus
    : (valueOverride !== undefined ? numberOrNull(valueOverride) : numberOrNull(raw.value)) === null ? 'unknown' : 'known'
  const value = status === 'unknown'
    ? null
    : numberOrNull(valueOverride !== undefined ? valueOverride : raw.value)
  const knownCount = numberOrNull(raw.known_count ?? raw.sample_count)
  const unknownCount = numberOrNull(raw.unknown_count ?? raw.missing_count)
  let detail = '样本明细暂未提供'
  if (knownCount !== null && unknownCount !== null) {
    detail = status === 'partial'
      ? `已知 ${Math.max(0, Math.round(knownCount))} 项 · 缺失 ${Math.max(0, Math.round(unknownCount))} 项`
      : `已知 ${Math.max(0, Math.round(knownCount))} 项`
  } else if (key === 'estimate_variance') {
    detail = '仅展示同时填写预计和实际用时的记录'
  }
  return {
    key,
    label,
    value,
    unit,
    status,
    allow_negative: key === 'estimate_variance',
    direction: safeText(raw.direction),
    detail,
  }
}

function normalizeHistoryMetrics(review) {
  const raw = objectOrEmpty(review)
  const plan = objectOrEmpty(raw.plan_item_status || raw.plan_progress)
  const planBasis = objectOrEmpty(plan.calculation_basis)
  return [
    normalizeHistoryMetric(raw.completed_tasks || raw.completed, 'completed_tasks', '完成'),
    normalizeHistoryMetric(raw.overdue_tasks || raw.overdue, 'overdue_tasks', '逾期'),
    normalizeHistoryMetric(plan, 'plan_delays', '计划延期', '项', planBasis.current_delayed_item_count ?? planBasis.delayed_count),
    normalizeHistoryMetric(raw.estimate_variance || raw.estimate_deviation, 'estimate_variance', '估时偏差', '分钟'),
  ]
}

function historyStorageBasisLabel(value, fallback = '') {
  if (typeof value === 'string' && value.trim()) {
    const text = value.trim()
    if (text === 'parsed text, paths, credentials and raw payload fields are not persisted in history') {
      return '不保存原文、路径、凭据或原始载荷'
    }
    return text
  }
  const raw = objectOrEmpty(value)
  const text = raw.formula || raw.summary || raw.description || raw.presentation || raw.scope || raw.evidence
  return typeof text === 'string' && text.trim() ? text.trim() : fallback
}

function historySourceRefLabel(ref) {
  const item = objectOrEmpty(ref)
  const source = safeText(item.source_name || item.name || item.source_type, '来源')
  const id = item.source_id ?? item.id
  return id !== undefined && id !== null && String(id).trim() ? `${source} · ${id}` : source
}

function normalizeHistorySnapshot(item, index) {
  const raw = objectOrEmpty(item)
  const review = objectOrEmpty(raw.review || raw.weekly_review || raw.weeklyReview)
  const windowStart = raw.window_start || raw.start_at || raw.period_start || raw.start_date
  const windowEnd = raw.window_end || raw.end_at || raw.period_end || raw.end_date
  // A historical row is only real when the server persisted an explicit
  // seven-day window.  Do not render a current briefing as a prior snapshot.
  if (!windowStart || !windowEnd) return null
  const metricSources = Object.values(review)
    .filter((metric) => metric && typeof metric === 'object' && !Array.isArray(metric))
    .flatMap((metric) => listValue(metric.source_refs || metric.sources || metric.evidence))
  const sourceRefs = listValue(raw.source_refs || raw.sources || raw.evidence)
  const allSourceRefs = [...sourceRefs, ...metricSources]
    .map(normalizeSourceRef)
    .filter((ref) => ref.source_type && ref.source_id !== null)
    .filter((ref, refIndex, refs) => sourceRefKey(ref) && refs.findIndex((candidate) => sourceRefKey(candidate) === sourceRefKey(ref)) === refIndex)
  const sourceCount = numberOrNull(raw.source_count ?? raw.source_refs_count ?? raw.evidence_count)
  const metricStatuses = Object.values(review)
    .filter((metric) => metric && typeof metric === 'object' && !Array.isArray(metric) && metric.status)
    .map((metric) => String(metric.status).toLowerCase())
  const derivedStatus = metricStatuses.length === 0
    ? 'unknown'
    : metricStatuses.some((status) => ['unknown', 'partial'].includes(status)) ? 'partial' : 'complete'
  const sourceStatus = normalizeHistorySourceStatus(raw.source_status || raw.evidence_status || raw.data_status || derivedStatus)
  const basis = objectOrEmpty(raw.calculation_basis || review.calculation_basis || raw.basis || raw.calculationBasis)
  const basisLabel = safeText(
    typeof raw.calculation_basis === 'string' ? raw.calculation_basis : raw.basis_label || raw.calculation_basis_label,
  ) || safeText(basis.formula || basis.summary || basis.description || basis.window_semantics) || '计算依据暂未提供'
  const sourceNames = allSourceRefs.slice(0, 3).map(historySourceRefLabel).filter(Boolean)
  const sourceLabel = sourceNames.length
    ? `${sourceNames.join('、')}${allSourceRefs.length > 3 ? `（另有 ${allSourceRefs.length - 3} 条）` : ''}`
    : sourceCount !== null
      ? `${Math.max(0, Math.round(sourceCount))} 条可追溯来源，名称待补充`
      : raw.evidence_digest
        ? '证据摘要已保存，来源名称待补充'
        : '来源名称与数量待补充'
  const snapshotStorage = objectOrEmpty(basis.snapshot_storage)
  const storageBasis = raw.snapshot_storage_basis
    || raw.evidence_basis
    || snapshotStorage.sensitive_field_policy
    || snapshotStorage.summary
  const startLabel = String(windowStart).slice(0, 10)
  const endLabel = String(windowEnd).slice(0, 10)
  return {
    ui_key: `weekly-history-${raw.id || raw.snapshot_id || `${startLabel}-${endLabel}-${index}`}`,
    period_label: safeText(raw.period_label || raw.period || raw.label, '已保存复盘'),
    window_label: startLabel && endLabel ? `${startLabel} 至 ${endLabel}（结束不含）` : '窗口日期暂未提供',
    evaluated_at: raw.evaluated_at || raw.generated_at || raw.created_at || null,
    snapshot_status: normalizeHistorySnapshotStatus(raw.snapshot_status || raw.history_status),
    source_status: sourceStatus,
    ruleset_label: safeText(raw.ruleset_version || review.ruleset_version, '规则版本待补充'),
    basis_label: basisLabel,
    storage_basis_label: historyStorageBasisLabel(storageBasis, '历史保存范围暂未说明'),
    source_label: sourceLabel,
    source_refs: allSourceRefs.slice(0, 50),
    metrics: normalizeHistoryMetrics(review),
    summary_label: safeText(raw.summary_label || raw.summary || raw.explanation || review.notes?.[0]),
  }
}

function normalizeWeeklyReviewHistory(response) {
  const data = objectOrEmpty(response)
  const rawItems = Array.isArray(response)
    ? response
    : listValue(data.snapshots || data.reviews || data.items || data.history)
  const snapshots = rawItems.map(normalizeHistorySnapshot).filter(Boolean).slice(0, 12)
  const explicitAvailable = data.available
  const hasHistoryContract = Array.isArray(response)
    || ['snapshots', 'reviews', 'items', 'history', 'retention_limit'].some((key) => Object.prototype.hasOwnProperty.call(data, key))
  return {
    available: explicitAvailable !== undefined ? Boolean(explicitAvailable) : snapshots.length > 0 || hasHistoryContract,
    snapshots,
  }
}

function normalizeActivityItem(item, index) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) return null
  const raw = objectOrEmpty(item)
  const rawId = raw.activity_id ?? raw.id ?? raw.event_id
  const numericId = safePositiveId(rawId)
  const textId = typeof rawId === 'string' && rawId.trim() && rawId.trim().length <= 128 && !/[\u0000-\u001f]/.test(rawId)
    ? rawId.trim()
    : null
  const source = objectOrEmpty(raw.source || raw.source_ref)
  const sourceRaw = objectOrEmpty(source.source_ref || source.ref || (raw.source_ref && !raw.source?.source_ref ? raw.source_ref : null))
  const sourceRef = sourceRaw.source_type || sourceRaw.type || sourceRaw.source_id !== undefined || sourceRaw.id !== undefined
    ? normalizeSourceRef({ ...sourceRaw, source_name: source.source_label || source.label || raw.source_label || sourceRaw.source_name || sourceRaw.name })
    : null
  const sourceStatus = safeText(source.status || raw.source_status).toLowerCase()
  return {
    ...raw,
    ui_key: `activity-${numericId || textId || index}`,
    id: numericId || textId || `row-${index}`,
    event_type: safeText(raw.event || raw.event_type || raw.kind || raw.type, 'activity'),
    status: safeText(raw.status, 'unknown').toLowerCase() || 'unknown',
    title: safeText(raw.title, '学习处理'),
    description: safeText(raw.description || raw.detail || raw.message),
    occurred_at: typeof raw.occurred_at === 'string' && raw.occurred_at.trim() ? raw.occurred_at.trim() : null,
    source_ref: sourceRef && sourceRef.source_type ? sourceRef : null,
    source_label: safeText(source.source_label || source.label || raw.source_label || sourceRef?.source_name),
    source_message: safeText(source.message || raw.source_message),
    source_available: sourceStatus === 'available' ? true : sourceStatus === 'unavailable' ? false : null,
  }
}

function normalizeActivity(response) {
  const data = objectOrEmpty(response)
  const rawItems = Array.isArray(response)
    ? response
    : listValue(data.items || data.activity || data.events)
  const items = rawItems.map(normalizeActivityItem).filter(Boolean).slice(0, 40)
  const hasActivityContract = Array.isArray(response)
    || ['items', 'activity', 'events', 'available'].some((key) => Object.prototype.hasOwnProperty.call(data, key))
  return {
    available: data.available !== undefined ? Boolean(data.available) : hasActivityContract,
    items,
    generated_at: typeof data.generated_at === 'string' ? data.generated_at : null,
    limit: numberOrNull(data.limit),
    calculation_basis: safeText(data.calculation_basis),
  }
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

function normalizeLearningRhythmHistory(response) {
  const data = objectOrEmpty(response)
  const comparison = objectOrEmpty(data.comparison)
  const windows = listValue(data.available_windows).map((item) => {
    const raw = objectOrEmpty(item)
    const summary = objectOrEmpty(raw.rhythm_summary || raw.summary)
    return {
      ...raw,
      snapshot_id: raw.snapshot_id ?? raw.id,
      window_start: raw.window_start || null,
      window_end: raw.window_end || null,
      ruleset_version: safeText(raw.ruleset_version),
      rhythm_summary_version: safeText(raw.rhythm_summary_version || summary.summary_version),
      rhythm_summary_status: normalizeTrendStatus(raw.rhythm_summary_status || summary.status),
      sample_count: numberOrNull(raw.sample_count ?? summary.sample_count),
      known_count: numberOrNull(raw.known_count ?? summary.known_count),
    }
  }).filter((item) => item.snapshot_id !== null && item.snapshot_id !== undefined)
  const changes = listValue(comparison.calculation_basis?.changes).map((item) => objectOrEmpty(item)).filter((item) => item.code)
  const reasonCodes = textList(comparison.reason_codes)
  const limitations = textList(comparison.limitations || data.limitations)
  return {
    available_windows: windows,
    comparison: {
      status: normalizeTrendStatus(comparison.status || data.status),
      comparable: comparison.comparable === true,
      reason_codes: reasonCodes,
      limitations,
      changes,
      sample_count: numberOrNull(comparison.sample_count) || 0,
      known_count: numberOrNull(comparison.known_count) || 0,
      unknown_count: numberOrNull(comparison.unknown_count) || 0,
    },
  }
}

const rhythmHistoryChanges = computed(() => rhythmHistory.value.comparison.changes)

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

function safeDecisionText(value, maxLength) {
  const text = safeText(value)
  if (!text || text.length > maxLength || /[\u0000-\u001f\u007f]/.test(text)) return ''
  return text
}

function normalizeDecisionSourceRef(ref) {
  const item = objectOrEmpty(ref)
  const sourceType = safeText(item.source_type).toLowerCase()
  if (!decisionSourceTypes.has(sourceType)) return null
  if (sourceType === 'capacity') {
    return item.source_id === 'next_7_days' ? { source_type: sourceType, source_id: 'next_7_days' } : null
  }
  const sourceId = safePositiveId(item.source_id)
  const key = navigationKey(item.navigation_key)
  return sourceId === null || !key ? null : { source_type: sourceType, source_id: sourceId, navigation_key: key }
}

function normalizeDecisionQueueItem(item) {
  const data = objectOrEmpty(item)
  const decisionId = safeDecisionText(data.decision_id, 120)
  const kind = safeText(data.kind).toLowerCase()
  const priority = safeText(data.priority).toLowerCase()
  const reasonCode = safeText(data.reason_code).toLowerCase()
  const title = safeDecisionText(data.title, 80)
  const description = safeDecisionText(data.description, 240)
  const actionLabel = safeDecisionText(data.action_label, 80)
  const basis = objectOrEmpty(data.calculation_basis)
  const evaluatedAt = safeDecisionText(basis.evaluated_at, 80)
  const sourceState = safeText(basis.source_state).toLowerCase()
  if (!decisionId || !decisionKinds.has(kind) || !decisionPriorities.has(priority) || !decisionReasonCodes.has(reasonCode)) return null
  if (!title || !description || !actionLabel || basis.ordering_rule !== 'risk_then_kind_then_source' || !evaluatedAt || !decisionSourceStates.has(sourceState)) return null
  if (!Array.isArray(data.source_refs) || data.source_refs.length !== 1) return null
  const sourceRef = normalizeDecisionSourceRef(data.source_refs[0])
  if (!sourceRef) return null
  return {
    decision_id: decisionId,
    kind,
    priority,
    title,
    description,
    action_label: actionLabel,
    reason_code: reasonCode,
    source_refs: [sourceRef],
    calculation_basis: {
      evaluated_at: evaluatedAt,
      ordering_rule: 'risk_then_kind_then_source',
      source_state: sourceState,
    },
  }
}

function decisionPriorityLabel(priority) {
  return decisionPriorityLabels[priority] || '待分级'
}

function decisionReasonLabel(reasonCode) {
  return decisionReasonLabels[reasonCode] || '已纳入排序'
}

function decisionSourceRefs(decision) {
  return Array.isArray(decision?.source_refs)
    ? decision.source_refs.map(normalizeDecisionSourceRef).filter(Boolean).filter(sourceRefNavigable)
    : []
}

function decisionSourceTypeLabel(decision) {
  const ref = decisionSourceRefs(decision)[0]
  return ref ? sourceRefTypeLabels[ref.source_type] || '来源' : '来源'
}

function isSourceUnavailable(ref) {
  return sourceNavigation.value[sourceRefKey(ref)]?.available === false
}

function normalizeBriefing(response) {
  const data = objectOrEmpty(response)
  const suggestions = (Array.isArray(data.suggestions) ? data.suggestions : []).map(normalizeSuggestion).filter(Boolean)
  const pendingCount = nonNegativeInteger(data.pending_count)
  const rawDecisionQueue = data.decision_queue
  const decisionQueuePresent = Object.prototype.hasOwnProperty.call(data, 'decision_queue')
  const normalizedDecisionQueue = Array.isArray(rawDecisionQueue)
    ? rawDecisionQueue.map(normalizeDecisionQueueItem).filter(Boolean).slice(0, 5)
    : []
  const decisionQueueStatus = !decisionQueuePresent || !Array.isArray(rawDecisionQueue)
    ? 'unavailable'
    : rawDecisionQueue.length && !normalizedDecisionQueue.length
      ? 'invalid'
      : normalizedDecisionQueue.length
        ? 'available'
        : 'empty'
  const todayRaw = data.today_actions || data.today_three || data.today_items
  const capacityRaw = data.capacity_actions || data.capacity_action_candidates
  const capacityData = data.capacity && typeof data.capacity === 'object' ? data.capacity : null
  const todayActions = listValue(todayRaw).map((item, index) => normalizeActionCandidate(item, index, 'today')).slice(0, 3)
  const todaySuggestionIds = new Set(todayActions.map((action) => action.suggestion_id).filter(Boolean))
  const capacityActions = listValue(capacityRaw)
    .map((item, index) => normalizeActionCandidate(item, index, 'capacity'))
    .filter((action) => !action.suggestion_id || !todaySuggestionIds.has(action.suggestion_id))
  const planDeltas = normalizePlanDeltaList(data)
  const weekly = normalizeWeeklyReview(data)
  return {
    generated_at: data.generated_at || '',
    pending_count: pendingCount,
    suggestions,
    decision_queue: normalizedDecisionQueue,
    decision_queue_status: decisionQueueStatus,
    inbox: normalizeInbox(data),
    today_actions: todayActions,
    capacity_actions: capacityActions,
    recent_results: listValue(data.recent_results || data.recent_activity)
      .map((item, index) => {
        const normalized = normalizeSuggestion(item)
        if (!normalized) return null
        return { ...normalized, ui_key: `recent-${normalized.id}-${index}` }
      })
      .filter(Boolean)
      .slice(0, 5),
    plan_deltas: planDeltas,
    weekly_review: weekly,
    reminders: weekly.reminders || [],
    capacity: capacityData,
  }
}

function setAgentResponse(response) {
  const normalized = normalizeBriefing(response)
  // Evidence targets are resolved against the current database state. Never
  // carry a previous target across a refresh where an id may have been
  // deleted, renamed, or recreated.
  sourceNavigation.value = {}
  sourceNavigationLoading.value = {}
  const previous = selectedPriorities.value
  const nextPriorities = {}
  normalized.suggestions.forEach((suggestion) => {
    const id = suggestion.id
    if (!id) return
    nextPriorities[id] = normalizePriority(previous[id], proposedPriority(suggestion))
  })
  agent.value = {
    generated_at: normalized.generated_at,
    pending_count: normalized.pending_count,
    suggestions: normalized.suggestions,
  }
  inbox.value = normalized.inbox
  decisionQueue.value = normalized.decision_queue
  decisionQueueStatus.value = normalized.decision_queue_status
  todayActions.value = normalized.today_actions
  capacityActions.value = normalized.capacity_actions
  recentResults.value = normalized.recent_results
  planDeltas.value = normalized.plan_deltas
  weeklyReview.value = normalized.weekly_review
  reminders.value = normalized.reminders
  briefingLoaded.value = true
  if (normalized.capacity) {
    capacity.value = normalizeCapacity(normalized.capacity)
    capacityLoaded.value = true
  }
  selectedPriorities.value = nextPriorities
  return Boolean(normalized.capacity)
}

function clearAgentMessage() {
  agentMessage.value = { type: 'info', text: '' }
}

function setAgentMessage(type, text) {
  agentMessage.value = { type, text }
}

function isActionLoading(id, action) {
  return actionLoading.value[id] === action
}

function isAnyActionLoading(id) {
  return Boolean(actionLoading.value[id])
}

function hasAgentActionLoading() {
  return Object.keys(actionLoading.value).length > 0
}

function setActionLoading(id, action) {
  actionLoading.value = { ...actionLoading.value, [id]: action }
}

function clearActionLoading(id) {
  const next = { ...actionLoading.value }
  delete next[id]
  actionLoading.value = next
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
  return `agent-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function idempotencyKeyFor(suggestion) {
  if (!idempotencyKeys.has(suggestion.id)) idempotencyKeys.set(suggestion.id, createIdempotencyKey())
  return idempotencyKeys.get(suggestion.id)
}

async function loadAgentBriefing() {
  agentLoading.value = true
  agentBriefingState.value = 'loading'
  try {
    const hasCapacity = setAgentResponse(await agentApi.briefing())
    agentBriefingState.value = nonNegativeInteger(agent.value.pending_count) === null ? 'invalid' : 'ready'
    if (!hasCapacity) await loadCapacity()
  } catch (err) {
    agent.value = { ...agent.value, pending_count: null }
    agentBriefingState.value = 'error'
    setAgentMessage('error', err.message)
  } finally {
    agentLoading.value = false
  }
}

async function loadWeeklyReview() {
  try {
    const normalized = normalizeWeeklyReview(await agentApi.weeklyReview())
    if (normalized.available) weeklyReview.value = normalized
    if (normalized.reminders.length) reminders.value = normalized.reminders
    return true
  } catch {
    // M8.5 data is intentionally optional.  The page keeps an explicit
    // unavailable state instead of converting a 404 into invented metrics.
    return false
  }
}

async function loadLearningTrends() {
  try {
    learningTrends.value = normalizeLearningTrends(await agentApi.learningTrends())
    return true
  } catch {
    // Trends are optional. Keep the unavailable state visible instead of
    // treating missing/failed telemetry as a zero or a calibration result.
    learningTrends.value = normalizeLearningTrends({})
    return false
  }
}

async function loadWeeklyReviewHistory() {
  try {
    weeklyHistory.value = normalizeWeeklyReviewHistory(await agentApi.weeklyReviewHistory({ limit: 12 }))
    return true
  } catch {
    // History is an optional persisted view.  A missing endpoint or empty
    // store must remain visibly distinct from a fabricated prior week.
    weeklyHistory.value = normalizeWeeklyReviewHistory({})
    return false
  }
}

async function loadLearningRhythmHistory() {
  try {
    rhythmHistory.value = normalizeLearningRhythmHistory(await agentApi.learningRhythmHistory())
    return true
  } catch {
    rhythmHistory.value = normalizeLearningRhythmHistory({})
    return false
  }
}

async function loadActivity() {
  activityLoading.value = true
  activityError.value = ''
  try {
    activity.value = normalizeActivity(await agentApi.activity({ limit: 50 }))
    activityLoaded.value = true
    return true
  } catch (err) {
    // Activity is an optional read-only view. A missing endpoint, malformed
    // payload, or transient failure remains an explicit unavailable state.
    activityError.value = safeText(err?.message, '服务暂时不可用，请稍后重试。')
    if (!activityLoaded.value) activity.value = normalizeActivity({})
    return false
  } finally {
    activityLoading.value = false
  }
}

function collectEvidenceRefs() {
  const actionGroups = [todayActions.value, capacityActions.value, weeklyReview.value.next_actions, reminders.value]
  const actionRefs = actionGroups.flatMap((group) => group.flatMap((item) => actionSourceRefs(item)))
  const decisionRefs = decisionQueue.value.flatMap((decision) => decisionSourceRefs(decision))
  const trendRefs = [
    ...learningTrends.value.source_refs,
    ...learningTrends.value.signals.flatMap((signal) => actionSourceRefs(signal)),
  ]
  const historyRefs = weeklyHistory.value.snapshots.flatMap((snapshot) => snapshot.source_refs || [])
  const activityRefs = activity.value.items
    .filter((item) => activity.value.available && item.source_available !== false)
    .map((item) => activitySourceRef(item))
    .filter(Boolean)
  return uniqueSourceRefs([...decisionRefs, ...actionRefs, ...trendRefs, ...historyRefs, ...activityRefs]).slice(0, 50)
}

async function warmSourceNavigation() {
  const refs = collectEvidenceRefs()
  if (!refs.length) return true
  return resolveSourceRefs(refs, { silent: true })
}

async function loadPlanDeltas() {
  try {
    planDeltas.value = normalizePlanDeltaList(await agentApi.planDeltas())
    return true
  } catch (err) {
    // The briefing remains usable while the optional dedicated endpoint is being deployed.
    planDeltas.value = planDeltas.value || []
    return false
  }
}

async function loadDetailedLedgerData({ force = false } = {}) {
  if (detailedDataState.value === 'loading') return
  if (detailedDataRequested.value && !force) return

  detailedDataState.value = 'loading'
  detailedDataFailures.value = []
  const resources = [
    ['周度复盘', loadWeeklyReview],
    ['复盘历史', loadWeeklyReviewHistory],
    ['学习趋势', loadLearningTrends],
    ['学习节奏历史比较', loadLearningRhythmHistory],
    ['学习处理记录', loadActivity],
    ['计划差异', loadPlanDeltas],
  ]
  const results = await Promise.all(resources.map(async ([label, load]) => {
    try {
      return { label, loaded: await load() }
    } catch {
      return { label, loaded: false }
    }
  }))
  const failures = results.filter((result) => !result.loaded).map((result) => result.label)
  try {
    if (!(await warmSourceNavigation())) failures.push('来源入口')
  } catch {
    failures.push('来源入口')
  }

  detailedDataFailures.value = failures
  detailedDataRequested.value = true
  detailedDataState.value = failures.length ? 'error' : 'ready'
}

async function loadCapacity() {
  capacityLoading.value = true
  capacityError.value = ''
  try {
    capacity.value = normalizeCapacity(await agentApi.capacity())
  } catch (err) {
    capacity.value = normalizeCapacity({})
    capacityError.value = err.message
  } finally {
    capacityLoaded.value = true
    capacityLoading.value = false
  }
}

async function refreshAgent(silent = false) {
  if (agentLoading.value || hasAgentActionLoading()) return
  const refreshIncludesDetails = isDetailedView.value
  agentLoading.value = true
  agentBriefingState.value = 'loading'
  if (!silent) clearAgentMessage()
  try {
    const hasCapacity = setAgentResponse(await agentApi.refresh())
    agentBriefingState.value = nonNegativeInteger(agent.value.pending_count) === null ? 'invalid' : 'ready'
    if (!hasCapacity) await loadCapacity()
    if (refreshIncludesDetails) await loadDetailedLedgerData({ force: true })
    if (!silent) setAgentMessage('success', '建议已刷新，请确认需要调整的学习安排。')
  } catch (err) {
    agent.value = { ...agent.value, pending_count: null }
    agentBriefingState.value = 'error'
    // A detailed-view refresh still retries its independently available
    // resources when the agent refresh endpoint itself is temporarily down.
    if (refreshIncludesDetails) await loadDetailedLedgerData({ force: true })
    if (silent) {
      clearAgentMessage()
    } else {
      setAgentMessage('error', err.message)
      ElMessage.error(err.message)
    }
  } finally {
    agentLoading.value = false
  }
}

async function refreshAfterAgentAction() {
  await Promise.allSettled([loadDashboard(), loadAgentBriefing()])
  if (isDetailedView.value) await loadDetailedLedgerData({ force: true })
}

function validateEstimateMinutes(value) {
  const minutes = Number(value)
  return Number.isInteger(minutes) && minutes >= 15 && minutes <= 10080 ? minutes : null
}

function openEstimateAction(action) {
  if (!isExecutableAction(action) || action.action_type !== 'set_task_estimate' || hasAgentActionLoading()) return
  estimateAction.value = action
  // Keep this empty so the user supplies the value instead of accepting a client guess.
  estimateMinutes.value = null
  estimateDialogVisible.value = true
}

function closeEstimateAction() {
  if (isEstimateActionLoading.value) return
  estimateDialogVisible.value = false
  estimateAction.value = null
  estimateMinutes.value = null
}

async function submitEstimateAction() {
  if (!estimateAction.value) return
  const minutes = validateEstimateMinutes(estimateMinutes.value)
  if (minutes === null) {
    ElMessage.warning('请输入 15 到 10080 分钟的整数，步长为 15 分钟。')
    return
  }
  if (await executeAction(estimateAction.value, minutes)) closeEstimateAction()
}

async function executeAction(action, estimatedMinutes = null) {
  if (!action || !isExecutableAction(action)) {
    if (action && ['set_task_estimate', 'start_task', 'adjust_priority'].includes(action.action_type) && !action.suggestion_id) {
      const message = '当前没有建议编号，无法执行这项操作。'
      setAgentMessage('error', message)
      ElMessage.warning(message)
    }
    return false
  }
  if (action.action_type === 'set_task_estimate' && validateEstimateMinutes(estimatedMinutes) === null) return false

  const key = actionActionKey(action)
  if (isAnyActionLoading(key)) return false
  setActionLoading(key, 'execute')
  clearAgentMessage()
  try {
    const payload = { idempotency_key: idempotencyKeyFor({ id: key }) }
    if (action.action_type === 'set_task_estimate') payload.estimated_minutes = validateEstimateMinutes(estimatedMinutes)
    // The server owns the target and proposed change. The client sends only the
    // bounded override allowed by the contract plus the idempotency key.
    const result = await agentApi.accept(action.suggestion_id, payload)
    if (!isExecutedResult(result)) {
      const message = result?.receipt?.message || '动作状态未确认，安排尚未确定是否更新。'
      setAgentMessage('error', message)
      ElMessage.error(message)
      return false
    }
    const message = result?.receipt?.message || '动作已执行。'
    setAgentMessage('success', message)
    ElMessage.success(message)
    await refreshAfterAgentAction()
    return true
  } catch (err) {
    setAgentMessage('error', err.message)
    ElMessage.error(err.message)
    return false
  } finally {
    clearActionLoading(key)
  }
}

function planDeltaActionKey(delta) {
  return `plan-delta:${String(delta?.id || '')}`
}

function reminderActionKey(reminder) {
  return `reminder:${String(reminder?.reminder_id || reminder?.ui_key || '')}`
}

function isDismissibleReminder(reminder) {
  return Boolean(
    reminder?.dismissible
      && reminder?.reminder_id
      && (!reminder.status || reminder.status === 'active'),
  )
}

function sourceRefNavigable(ref) {
  const item = normalizedNavigationSourceRef(normalizeSourceRef(ref))
  if (!item) return false
  const sourceType = item.source_type
  if (![
    'task', 'material', 'study_plan', 'study_plan_item', 'task_collection',
    'material_collection', 'study_plan_collection', 'action_receipt', 'capacity',
  ].includes(sourceType)) return false
  if (sourceType.endsWith('_collection') || sourceType === 'capacity') return item.source_id !== null
  return item.source_id !== null && Boolean(item.navigation_key)
}

function isNavigableReminder(reminder) {
  const refs = actionSourceRefs(reminder)
  if (refs.some(sourceRefNavigable)) return true
  return sourceRefNavigable({
    source_type: reminder?.source_type,
    source_id: reminder?.source_id,
    navigation_key: reminder?.source_navigation_key,
  })
}

function announceSourceUnavailable(message) {
  const text = safeText(message, '当前来源没有可用的安全入口。')
  setAgentMessage('warning', text)
  ElMessage.warning(text)
}

function normalizeResolvedSource(item) {
  const raw = objectOrEmpty(item)
  const sourceRef = normalizeSourceRef(raw.source_ref || raw.ref)
  const target = validatedSourceNavigationTarget({ items: [raw] }, sourceRef)
  const available = Boolean(raw.available) && Boolean(target)
  const fallbackLabel = sourceRefDisplayLabel(sourceRef)
  return {
    key: sourceRefKey(sourceRef),
    source_ref: sourceRef,
    available,
    target,
    label: safeText(raw.label, fallbackLabel),
    message: safeText(raw.message || raw.reason, available ? '已确认安全来源入口。' : '暂时没有可用的来源入口。'),
  }
}

function uniqueSourceRefs(refs) {
  const result = []
  const seen = new Set()
  for (const raw of refs || []) {
    const ref = normalizeSourceRef(raw)
    if (!sourceRefNavigable(ref)) continue
    const key = sourceRefKey(ref)
    if (seen.has(key)) continue
    seen.add(key)
    result.push(ref)
  }
  return result
}

async function resolveSourceRefs(refs, { silent = false } = {}) {
  const candidates = uniqueSourceRefs(refs).filter((ref) => {
    const key = sourceRefKey(ref)
    // A click can race the initial warm-up.  Allowing a second bounded lookup
    // keeps the click authoritative and avoids treating an in-flight request
    // as an unavailable source.
    return !sourceNavigation.value[key]
  })
  if (!candidates.length) return true
  const loading = { ...sourceNavigationLoading.value }
  candidates.forEach((ref) => { loading[sourceRefKey(ref)] = true })
  sourceNavigationLoading.value = loading
  const requestRefs = candidates.map(({ source_type, source_id, navigation_key }) => ({
    source_type,
    source_id,
    ...(navigation_key ? { navigation_key } : {}),
  }))
  try {
    const response = await agentApi.resolveSourceRefs(requestRefs)
    const items = listValue(response?.items || response)
    const resolved = {}
    items.forEach((item) => {
      const normalized = normalizeResolvedSource(item)
      if (normalized.key && normalized.source_ref.source_type && normalized.source_ref.source_id !== null) resolved[normalized.key] = normalized
    })
    const next = { ...sourceNavigation.value }
    candidates.forEach((ref) => {
      const key = sourceRefKey(ref)
      next[key] = resolved[key] || {
        key,
        source_ref: ref,
        available: false,
        target: null,
        label: sourceRefDisplayLabel(ref),
        message: '暂时没有可用的来源入口。',
      }
    })
    sourceNavigation.value = next
    return true
  } catch (err) {
    const next = { ...sourceNavigation.value }
    candidates.forEach((ref) => {
      const key = sourceRefKey(ref)
      next[key] = {
        key,
        source_ref: ref,
        available: false,
        target: null,
        label: sourceRefDisplayLabel(ref),
        message: silent ? '来源入口服务暂不可用。' : `无法确认来源入口：${err.message}`,
      }
    })
    sourceNavigation.value = next
    if (!silent) announceSourceUnavailable(`无法确认来源入口：${err.message}`)
    return false
  } finally {
    const nextLoading = { ...sourceNavigationLoading.value }
    candidates.forEach((ref) => { delete nextLoading[sourceRefKey(ref)] })
    sourceNavigationLoading.value = nextLoading
  }
}

async function navigateResolvedSourceRefs(refs) {
  const candidates = uniqueSourceRefs(refs)
  if (!candidates.length) {
    announceSourceUnavailable('当前内容没有可识别的来源入口。')
    return false
  }
  await resolveSourceRefs(candidates)
  const entry = candidates
    .map((ref) => sourceNavigation.value[sourceRefKey(ref)])
    .find((item) => item?.available && item.target)
  if (!entry) {
    const first = candidates.map((ref) => sourceNavigation.value[sourceRefKey(ref)]).find(Boolean)
  announceSourceUnavailable(first?.message || '暂时没有可用的来源入口。')
    return false
  }
  await router.push(entry.target)
  return true
}

async function navigateSourceRef(ref) {
  if (!sourceRefNavigable(ref)) {
    announceSourceUnavailable('该来源类型或来源编号不受支持，页面不会自行拼接地址。')
    return false
  }
  return navigateResolvedSourceRefs([ref])
}

function navigateReminder(reminder) {
  return navigateResolvedSourceRefs(actionSourceRefs(reminder))
}

async function dismissReminder(reminder) {
  if (!isDismissibleReminder(reminder)) return
  const key = reminderActionKey(reminder)
  if (isAnyActionLoading(key)) return
  setActionLoading(key, 'dismiss')
  clearAgentMessage()
  try {
    const result = await agentApi.dismissReminder(reminder.reminder_id, { reason: '用户忽略站内提醒' })
    const status = String(result?.status || '').toLowerCase()
    if (status !== 'dismissed') {
      const message = result?.receipt?.message || '提醒忽略状态未确认，页面未将其标记为已忽略。'
      setAgentMessage('error', message)
      ElMessage.error(message)
      return
    }
    const message = result?.receipt?.message || '提醒已忽略。'
    setAgentMessage('success', message)
    ElMessage.success(message)
    await refreshAfterAgentAction()
  } catch (err) {
    setAgentMessage('error', err.message)
    ElMessage.error(err.message)
  } finally {
    clearActionLoading(key)
  }
}

function planDeltaAccepted(result) {
  const status = String(result?.status || result?.suggestion?.status || '').toLowerCase()
  const outcome = String(result?.receipt?.outcome || '').toLowerCase()
  return ['accepted', 'executed'].includes(status) || ['accepted', 'executed'].includes(outcome)
}

async function acceptPlanDelta(delta) {
  if (!delta?.id || delta.status !== 'pending') return
  const key = planDeltaActionKey(delta)
  if (isAnyActionLoading(key)) return
  setActionLoading(key, 'accept')
  clearAgentMessage()
  try {
    const result = await agentApi.acceptPlanDelta(delta.id, { idempotency_key: idempotencyKeyFor({ id: key }) })
    if (!planDeltaAccepted(result)) {
      const message = result?.receipt?.message || '计划差异尚未确认，原计划保持不变。'
      setAgentMessage('error', message)
      ElMessage.error(message)
      return
    }
    const message = result?.receipt?.message || '计划差异已确认，学习安排已更新。'
    setAgentMessage('success', message)
    ElMessage.success(message)
    await refreshAfterAgentAction()
  } catch (err) {
    setAgentMessage('error', err.message)
    ElMessage.error(err.message)
  } finally {
    clearActionLoading(key)
  }
}

async function dismissPlanDelta(delta) {
  if (!delta?.id || delta.status !== 'pending') return
  const key = planDeltaActionKey(delta)
  if (isAnyActionLoading(key)) return
  setActionLoading(key, 'dismiss')
  clearAgentMessage()
  try {
    await agentApi.dismiss(delta.id, {
      reason: '用户暂不重排计划',
    })
    const message = '已忽略这条计划差异，原计划保持不变。'
    setAgentMessage('success', message)
    ElMessage.success(message)
    await refreshAfterAgentAction()
  } catch (err) {
    setAgentMessage('error', err.message)
    ElMessage.error(err.message)
  } finally {
    clearActionLoading(key)
  }
}

async function acceptSuggestion(suggestion) {
  if (!suggestion.id) {
    const message = '当前没有建议编号，无法执行这项建议。'
    setAgentMessage('error', message)
    ElMessage.warning(message)
    return
  }
  if (isAnyActionLoading(suggestion.id)) return
  const priority = normalizePriority(selectedPriorities.value[suggestion.id], proposedPriority(suggestion))
  setActionLoading(suggestion.id, 'accept')
  clearAgentMessage()
  try {
    const result = await agentApi.accept(suggestion.id, { priority, idempotency_key: idempotencyKeyFor(suggestion) })
    if (!isExecutedResult(result)) {
      const message = result?.receipt?.message || '建议状态未确认，任务安排尚未确定是否更新。'
      setAgentMessage('error', message)
      ElMessage.error(message)
      return
    }
    const receipt = result?.receipt?.message || '建议已接受，任务安排已更新。'
    setAgentMessage('success', receipt)
    ElMessage.success(receipt)
    await refreshAfterAgentAction()
  } catch (err) {
    setAgentMessage('error', err.message)
    ElMessage.error(err.message)
  } finally {
    clearActionLoading(suggestion.id)
  }
}

async function dismissSuggestion(suggestion) {
  if (!suggestion.id || isAnyActionLoading(suggestion.id)) return
  setActionLoading(suggestion.id, 'dismiss')
  clearAgentMessage()
  try {
    await agentApi.dismiss(suggestion.id, { reason: '用户暂不调整' })
    setAgentMessage('success', '已忽略这条建议。')
    ElMessage.success('已忽略这条建议。')
    await refreshAfterAgentAction()
  } catch (err) {
    setAgentMessage('error', err.message)
    ElMessage.error(err.message)
  } finally {
    clearActionLoading(suggestion.id)
  }
}

async function loadDashboard() {
  loading.value = true
  dashboardState.value = 'loading'
  error.value = ''
  try {
    const normalized = normalizeDashboard(await dashboardApi.get())
    if (!normalized) {
      dashboard.value = emptyDashboard()
      upcomingTasks.value = []
      overdueTasks.value = []
      recentMaterials.value = []
      dashboardState.value = 'invalid'
      error.value = '学习记录返回的计数或列表格式无效，页面未显示猜测数据。'
      return
    }
    dashboard.value = normalized
    upcomingTasks.value = normalized.upcoming_tasks
    overdueTasks.value = normalized.overdue_tasks
    recentMaterials.value = normalized.recent_materials
    dashboardState.value = 'ready'
  } catch (err) {
    dashboard.value = emptyDashboard()
    upcomingTasks.value = []
    overdueTasks.value = []
    recentMaterials.value = []
    dashboardState.value = 'error'
    error.value = err.message
  } finally {
    loading.value = false
  }
}

watch(isDetailedView, (detailed, wasDetailed) => {
  if (detailed && !wasDetailed) void loadDetailedLedgerData()
})

onMounted(async () => {
  loadDashboard()
  await refreshAgent(true)
  // A stored detailed-view preference is a direct entry to the detailed
  // experience, not a reason to load its resources in concise mode first.
  if (isDetailedView.value) await loadDetailedLedgerData()
})
</script>

<style scoped>
.dashboard-action { margin: 0 0 22px; }
.streak-chip { display: inline-flex; align-items: center; gap: 7px; flex: 0 0 auto; padding: 9px 14px; color: #8a5a1f; background: #fff6e2; border: 1px solid #f1dfba; border-radius: 99px; font-size: 12.5px; font-weight: 650; }
.streak-chip strong { color: #b05e12; font-size: 14px; }
.streak-flame { font-size: 14px; }
.concise-flow-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(280px, .75fr); gap: 16px; min-width: 0; margin: 0 0 18px; }
.agent-center-card { margin-bottom: 22px; border: 0 !important; border-radius: 16px !important; box-shadow: 0 8px 28px rgba(35, 45, 75, .05) !important; }
.agent-center-card :deep(.el-card__body) { padding: 22px; }
.detailed-data-status { min-height: 1.5em; margin: 12px 0 2px; padding: 9px 11px; color: #526078; background: #f8f9fc; border: 1px solid #e6eaf1; border-radius: 8px; font-size: 12px; line-height: 1.55; }
.detailed-data-status.is-loading { color: #4655b2; background: #f3f5ff; border-color: #dce1fb; }
.detailed-data-status.is-error { color: #8a5a1f; background: #fffaf0; border-color: #f1dfba; }
.detailed-data-status.is-ready { color: #356052; background: #f3faf6; border-color: #cfe5d7; }
.agent-center-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.agent-kicker { color: #5964ed; font-size: 10px; font-weight: 700; letter-spacing: .16em; }
.agent-title-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.agent-title-row h2 { margin: 0; color: #263247; font-size: 18px; }
.agent-description { margin: 8px 0 0; color: #667085; font-size: 12px; line-height: 1.6; }
.agent-message { margin-top: 18px; }
.learning-ledger-index { margin-top: 18px; padding: 13px; color: var(--ledger-ink, #1e2a44); background: var(--ledger-paper, #fffefb); border: 1px solid var(--ledger-line, #d9e0ea); border-left: 3px solid var(--ledger-indigo, #5964ed); border-radius: 4px; }
.ledger-index-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.ledger-index-heading > div { display: grid; gap: 3px; min-width: 0; }
.ledger-index-kicker { color: var(--ledger-indigo, #5964ed); font-size: 10px; font-weight: 700; letter-spacing: .12em; line-height: 1.3; }
.ledger-index-heading strong { color: var(--ledger-ink, #1e2a44); font-size: 14px; line-height: 1.4; }
.ledger-index-heading > span { flex: 0 1 auto; color: var(--ledger-amber-text, #946020); font-size: 12px; line-height: 1.5; text-align: right; }
.ledger-index-tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 11px; }
.ledger-index-tab { display: grid; min-width: 0; min-height: 44px; align-content: center; gap: 3px; padding: 8px 10px; color: var(--ledger-ink, #1e2a44); text-decoration: none; background: var(--ledger-paper, #fffefb); border: 1px solid #dfe2ee; border-radius: 3px; box-shadow: inset 0 2px 0 #d9d7ff; }
a.ledger-index-tab:hover { color: var(--ledger-ink, #1e2a44); background: #f7f8ff; border-color: #bfc5f4; }
a.ledger-index-tab:focus-visible { outline: 3px solid rgba(89, 100, 237, .42); outline-offset: 3px; }
.ledger-index-tab-label, .ledger-index-tab-status { min-width: 0; overflow-wrap: anywhere; }
.ledger-index-tab-label { font-size: 12px; font-weight: 700; line-height: 1.35; }
.ledger-index-tab-status { color: var(--ledger-muted, #667085); font-size: 12px; line-height: 1.5; }
.ledger-index-tab-disabled { color: #667085; background: #faf9f6; border-color: #e8e2d8; box-shadow: inset 0 2px 0 #eadfc9; }
.ledger-index-tab-disabled .ledger-index-tab-status { color: #a0a8b6; }
.decision-desk-section, .inbox-section, .today-section, .risk-center-card { scroll-margin-top: 88px; }
.briefing-loading { margin-top: 20px; padding: 28px 12px 8px; color: #667085; text-align: center; font-size: 12px; }
.decision-desk-section { margin-top: 20px; padding: 18px; background: #fffdf8; border: 1px solid #f1ead9; border-top: 3px solid #5964ed; border-radius: 13px; box-shadow: 0 8px 20px rgba(85, 74, 48, .04); }
.decision-desk-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.decision-desk-kicker { color: #5964ed; font-size: 10px; font-weight: 700; letter-spacing: .14em; }
.decision-desk-heading h3 { margin: 7px 0 0; color: #263247; font-size: 18px; line-height: 1.3; }
.decision-desk-heading p { margin: 6px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }
.decision-desk-limit { flex: 0 0 auto; padding: 4px 7px; color: #8d713b; background: #fff8e9; border: 1px solid #f3dfb4; border-radius: 999px; font-size: 12px; line-height: 1.5; }
.decision-queue { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.decision-card { display: grid; grid-template-columns: 58px minmax(0, 1fr); min-width: 0; padding: 13px 14px 14px; background: #fffefb; border: 1px solid #eee5d5; border-top: 2px solid #d7d3ff; border-radius: 10px; }
.decision-card-critical { border-top-color: #c94c4c; }
.decision-card-high { border-top-color: #c9822e; }
.decision-card-medium { border-top-color: #5964ed; }
.decision-card-normal { border-top-color: #aeb4c0; }
.decision-card-rail { display: flex; min-height: 100%; align-items: center; flex-direction: column; padding-right: 12px; border-right: 1px solid #eee5d5; }
.decision-source-stamp { padding: 4px 5px; color: #5964ed; background: #f1f0ff; border: 1px solid #d9d7ff; border-radius: 3px; font-size: 11px; font-weight: 700; letter-spacing: .04em; line-height: 1.25; text-align: center; white-space: nowrap; transform: rotate(-1deg); }
.decision-rail-line { width: 1px; min-height: 24px; flex: 1; margin: 7px 0 5px; background: #d9d7ff; }
.decision-rail-arrow { color: #5964ed; font-size: 15px; line-height: 1; }
.decision-card-main { min-width: 0; padding-left: 13px; }
.decision-card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.decision-card-context { display: flex; min-width: 0; align-items: baseline; flex-wrap: wrap; gap: 6px; }
.decision-order { color: #667085; font-size: 12px; font-variant-numeric: tabular-nums; letter-spacing: .08em; }
.decision-reason { color: #667085; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.decision-priority { flex: 0 0 auto; padding: 3px 6px; border: 1px solid; border-radius: 999px; font-size: 12px; font-weight: 700; line-height: 1.5; }
.decision-priority-critical { color: #a13d38; background: #fff1ef; border-color: #f3c7c1; }
.decision-priority-high { color: #946020; background: #fff7e8; border-color: #f3dfb4; }
.decision-priority-medium { color: #4d56b8; background: #f2f1ff; border-color: #d9d7ff; }
.decision-priority-normal { color: #667085; background: #f5f6f8; border-color: #e4e7ec; }
.decision-card-main h4 { margin: 9px 0 0; overflow-wrap: anywhere; color: #263247; font-size: 14px; line-height: 1.45; }
.decision-description { min-height: 38px; margin: 6px 0 0; color: #667085; font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.decision-next-step { display: flex; align-items: baseline; flex-wrap: wrap; gap: 7px; margin-top: 11px; padding-top: 9px; border-top: 1px dashed #eee5d5; }
.decision-next-step > span { color: #8d713b; font-size: 12px; font-weight: 700; letter-spacing: .05em; }
.decision-next-step strong { color: #344054; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.decision-source-group { display: flex; min-width: 0; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.decision-source-label { flex: 0 0 auto; color: #667085; font-size: 12px; font-weight: 600; }
.decision-source-button { max-width: 100%; padding: 8px 10px; color: var(--ledger-link, #4650c9); text-align: left; overflow-wrap: anywhere; background: #f7f8ff; border: 1px solid #d9d7ff; border-radius: 999px; cursor: pointer; font: inherit; font-size: 12px; line-height: 1.5; }
.decision-source-button:hover:not(:disabled) { background: #eeedff; border-color: #bfc2ff; }
.decision-source-button:focus-visible { outline: 2px solid #5964ed; outline-offset: 2px; }
.decision-source-button:disabled { color: #a0a8b6; background: #f6f7f9; border-color: #e7e9ee; cursor: not-allowed; }
.decision-queue-empty { display: grid; gap: 4px; margin-top: 16px; padding: 16px; color: #667085; background: #fffefb; border: 1px dashed #eadfc9; border-radius: 9px; font-size: 13px; line-height: 1.65; }
.decision-queue-empty strong { color: #667085; font-size: 12px; }
.decision-queue-invalid strong { color: #946020; }
.decision-queue-unavailable strong { color: #667085; }
.briefing-section { margin-top: 20px; padding-top: 18px; border-top: 1px solid #f0f2f6; }
.detail-view-nudge { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 20px; padding: 13px 14px; color: #536177; background: #f7f8fc; border: 1px solid #dde2ec; border-left: 3px solid #5964ed; border-radius: 8px; }
.detail-view-nudge > div { display: grid; gap: 4px; min-width: 0; }
.detail-view-nudge strong { color: #344054; font-size: 12px; }
.detail-view-nudge span { color: #667085; font-size: 13px; line-height: 1.65; }
.detail-view-nudge .el-button { flex: 0 0 auto; min-height: 44px; }
.concise-list-note { margin: 10px 0 0; color: var(--ledger-muted, #667085); font-size: 13px; line-height: 1.6; }
.concise-ledger-invite { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin: 18px 0 0; padding: 16px 18px; color: var(--ledger-ink, #1e2a44); background: var(--ledger-paper, #fffefb); border: 1px solid var(--ledger-line, #d9e0ea); border-left: 3px solid var(--ledger-indigo, #5964ed); border-radius: 6px; }
.concise-ledger-invite > div { display: grid; gap: 4px; min-width: 0; }
.concise-ledger-kicker { color: var(--ledger-link, #4650c9); font-size: 10px; font-weight: 750; letter-spacing: .12em; }
.concise-ledger-invite strong { font-size: 14px; line-height: 1.45; }
.concise-ledger-invite p { max-width: 72ch; margin: 0; color: var(--ledger-muted, #667085); font-size: 13px; line-height: 1.65; }
.concise-ledger-invite .el-button { flex: 0 0 auto; min-height: 44px; }
.briefing-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.briefing-section-heading h3 { margin: 0; color: #344054; font-size: 14px; }
.briefing-section-heading span { display: block; margin-top: 4px; color: #667085; font-size: 12px; line-height: 1.5; }
.inbox-count-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.inbox-count { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; padding: 12px 13px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 10px; }
.inbox-count span { color: #667085; font-size: 12px; }
.inbox-count strong { color: #344054; font-size: 18px; }
.inbox-count.ready { border-color: #d9f0e4; }
.inbox-count.review { border-color: #f8e8c5; }
.inbox-count.failed { border-color: #f4dada; }
.inbox-sources { display: grid; gap: 7px; margin-top: 14px; }
.inbox-sources-label { color: #667085; font-size: 12px; font-weight: 600; }
.inbox-source-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%; min-height: 44px; padding: 9px 10px; color: #5964ed; text-align: left; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 8px; cursor: pointer; }
.inbox-source-row:hover { background: #f5f6ff; border-color: #dfe2ff; }
.inbox-source-row:focus-visible { outline: 2px solid #9da4ff; outline-offset: 1px; }
.inbox-source-row > span:first-child { min-width: 0; overflow-wrap: anywhere; }
.briefing-inline-empty { padding: 16px 4px 2px; color: #667085; font-size: 12px; line-height: 1.7; }
.today-actions-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.today-action-card { display: flex; min-width: 0; flex-direction: column; padding: 14px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 10px; }
.today-action-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.today-action-title-wrap { min-width: 0; }
.today-action-title-wrap h4 { margin: 0; color: #344054; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.today-action-title-wrap span { display: block; margin-top: 3px; color: #667085; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.today-action-reason { min-height: 40px; margin: 10px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }
.today-action-meta { display: grid; gap: 4px; margin-top: 10px; color: #667085; font-size: 12px; line-height: 1.5; }
.today-sort-basis { margin-top: 10px; padding-top: 9px; color: #667085; border-top: 1px solid #f0f2f6; font-size: 13px; line-height: 1.6; }
.today-sort-basis strong { display: block; margin-bottom: 2px; color: #667085; font-weight: 600; }
.evidence-source-list { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; margin-top: 9px; color: #667085; font-size: 12px; line-height: 1.5; }
.evidence-source-list.compact { margin-top: 7px; }
.evidence-source-label { flex: 0 0 auto; color: #667085; font-weight: 600; }
.evidence-source-button { max-width: 100%; min-height: 44px; padding: 8px 10px; color: var(--ledger-link, #4650c9); text-align: left; overflow-wrap: anywhere; background: #f7f8ff; border: 1px solid #e4e6ff; border-radius: 999px; cursor: pointer; font: inherit; line-height: 1.5; }
.evidence-source-button:hover:not(:disabled) { background: #eef0ff; border-color: #cfd3ff; }
.evidence-source-button:focus-visible { outline: 2px solid #5964ed; outline-offset: 2px; }
.evidence-source-button:disabled { color: #a0a8b6; background: #f6f7f9; border-color: #e7e9ee; cursor: not-allowed; }
.evidence-source-more, .evidence-source-unavailable { color: #667085; }
.evidence-source-unavailable { margin-top: 8px; font-size: 12px; line-height: 1.5; }
.history-evidence-list { margin-top: 10px; padding-top: 9px; border-top: 1px solid #f0f2f6; }
.today-action-controls { display: flex; align-items: center; min-height: 28px; flex-wrap: wrap; gap: 7px; margin-top: auto; padding-top: 12px; }
.today-action-controls .el-button + .el-button { margin-left: 0; }
.muted-action { color: #667085; font-size: 12px; line-height: 1.5; }
.capacity-action-list { display: grid; gap: 8px; margin-top: 14px; }
.capacity-action-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 13px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 10px; }
.capacity-action-control { display: flex; align-items: center; flex-shrink: 0; gap: 7px; }
.capacity-action-control .el-button + .el-button { margin-left: 0; }
.recent-results-list { display: grid; gap: 8px; margin-top: 14px; }
.recent-result-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 10px 12px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 9px; }
.recent-result-receipt { margin-top: 5px; color: #667085; font-size: 13px; line-height: 1.6; }
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
.activity-marker { z-index: 1; flex: 0 0 9px; width: 9px; height: 9px; margin-top: 14px; background: #5964ed; border: 2px solid #eef0ff; border-radius: 50%; box-sizing: content-box; }
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
.plan-delta-list { display: grid; gap: 12px; margin-top: 14px; }
.plan-delta-card { padding: 15px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 12px; }
.plan-delta-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.plan-delta-heading h4 { margin: 0; color: #344054; font-size: 14px; line-height: 1.5; }
.plan-delta-trigger { margin: 11px 0 0; color: #667085; font-size: 12px; line-height: 1.7; }
.plan-delta-trigger strong { color: #5964ed; font-weight: 600; }
.plan-delta-change-grid { display: grid; grid-template-columns: minmax(0, 1fr) 22px minmax(0, 1fr); gap: 8px; align-items: stretch; margin-top: 12px; }
.plan-delta-change { min-width: 0; padding: 11px 12px; border: 1px solid #edf0f8; border-radius: 9px; }
.plan-delta-change.before { background: #fffdf8; border-color: #f5ead1; }
.plan-delta-change.after { background: #f8fffb; border-color: #dcefe5; }
.plan-delta-change-label { display: block; margin-bottom: 5px; color: #667085; font-size: 12px; font-weight: 600; }
.plan-delta-change ul { display: grid; gap: 4px; margin: 0; padding-left: 16px; color: #667085; font-size: 13px; line-height: 1.6; }
.plan-delta-arrow { display: grid; place-items: center; color: #667085; font-size: 17px; }
.plan-delta-empty { color: #667085; font-size: 12px; }
.plan-delta-protected { display: flex; gap: 8px; margin-top: 11px; padding-top: 10px; color: #667085; border-top: 1px solid #f0f2f6; font-size: 13px; line-height: 1.65; }
.plan-delta-protected .plan-delta-change-label { flex: 0 0 auto; margin-bottom: 0; color: #35aa81; }
.plan-delta-explanation { margin: 10px 0 0; color: #667085; font-size: 13px; line-height: 1.65; }
.plan-delta-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 13px; }
.plan-delta-actions .el-button + .el-button { margin-left: 0; }
.estimate-dialog-help { margin: 0 0 18px; color: #667085; font-size: 12px; line-height: 1.7; }
.estimate-input-wrap { display: flex; align-items: center; gap: 8px; }
.estimate-input-wrap .el-input-number { width: 190px; }
.unit-label { color: #667085; font-size: 12px; }
.agent-suggestions { display: grid; gap: 12px; margin-top: 20px; }
.agent-suggestion-card { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 16px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 12px; }
.suggestion-main { min-width: 0; flex: 1; }
.suggestion-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.suggestion-heading h3 { margin: 0; color: #344054; font-size: 14px; line-height: 1.5; }
.suggestion-source { margin-top: 4px; color: #667085; font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.suggestion-explanation { margin: 10px 0 0; color: #667085; font-size: 12px; line-height: 1.7; }
.suggestion-meta { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 11px; color: #667085; font-size: 12px; line-height: 1.5; }
.suggestion-actions { display: flex; align-items: flex-end; flex-direction: column; gap: 12px; flex-shrink: 0; }
.priority-control { display: flex; align-items: center; gap: 9px; }
.priority-label { color: #667085; font-size: 12px; }
.suggestion-buttons { display: flex; gap: 8px; }
.suggestion-buttons .el-button + .el-button { margin-left: 0; }
.agent-empty-state { padding: 28px 12px 8px; color: #667085; text-align: center; font-size: 12px; line-height: 1.7; }
.agent-empty-title { margin-bottom: 4px; color: #667085; font-size: 13px; font-weight: 600; }
.dashboard-subsection { margin-top: 18px; padding-top: 18px; border-top: 1px solid #f0f2f6; }
.subsection-title { margin-bottom: 4px; color: #e45656; font-size: 12px; font-weight: 700; }
.clickable-row { cursor: pointer; }
.clickable-row:hover .row-title { color: #5964ed; }
.clickable-row:focus-visible { border-radius: 8px; }
.risk-center-card { margin-bottom: 22px; border: 0 !important; border-radius: 16px !important; box-shadow: 0 8px 28px rgba(35, 45, 75, .05) !important; }
.risk-center-card :deep(.el-card__body) { padding: 22px; }
.risk-center-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.risk-title-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.risk-title-row h2 { margin: 0; color: #263247; font-size: 18px; }
.risk-description { margin: 8px 0 0; color: #667085; font-size: 12px; line-height: 1.6; }
.capacity-message { margin-top: 18px; }
.capacity-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 20px; }
.capacity-metric { min-width: 0; padding: 15px; background: #fbfcff; border: 1px solid #edf0f8; border-radius: 12px; }
.capacity-label { color: #667085; font-size: 12px; }
.capacity-value { margin-top: 9px; color: #263247; font-size: 20px; font-weight: 700; line-height: 1.3; overflow-wrap: anywhere; }
.capacity-note { margin-top: 6px; color: #667085; font-size: 13px; line-height: 1.6; }
.capacity-basis { display: flex; gap: 8px; margin-top: 16px; padding-top: 14px; color: #667085; border-top: 1px solid #f0f2f6; font-size: 13px; line-height: 1.7; }
.capacity-basis-label { flex: 0 0 auto; color: #667085; font-weight: 600; }
.capacity-empty-state { padding: 28px 12px 8px; color: #667085; text-align: center; font-size: 12px; }

@media (prefers-reduced-motion: reduce) {
  :global(html) { scroll-behavior: auto; }
}

@media (max-width: 900px) {
  .decision-source-button, .evidence-source-button { min-height: 44px; padding: 9px 11px; }
}

@media (max-width: 720px) {
  .concise-flow-grid { grid-template-columns: minmax(0, 1fr); }
  .agent-center-heading, .agent-suggestion-card { flex-direction: column; }
  .agent-center-heading .el-button { align-self: flex-start; }
  .decision-queue { grid-template-columns: minmax(0, 1fr); }
  .today-actions-grid { grid-template-columns: minmax(0, 1fr); }
  .capacity-action-row { align-items: flex-start; flex-direction: column; }
  .capacity-action-control { width: 100%; }
  .suggestion-actions { align-items: stretch; width: 100%; }
  .priority-control { justify-content: space-between; }
  .suggestion-buttons { justify-content: flex-end; }
  .risk-center-heading { flex-direction: column; }
  .risk-center-heading .el-button { align-self: flex-start; }
  .capacity-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .plan-delta-change-grid { grid-template-columns: minmax(0, 1fr); }
  .plan-delta-arrow { transform: rotate(90deg); }
  .weekly-review-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .weekly-history-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .rhythm-history-windows, .rhythm-history-change-list { grid-template-columns: minmax(0, 1fr); }
  .weekly-next-action-card, .reminder-card { align-items: flex-start; flex-direction: column; }
  .weekly-next-action-control, .reminder-control { width: 100%; justify-content: flex-start; }
  .detail-view-nudge { align-items: flex-start; flex-direction: column; }
  .detail-view-nudge .el-button { width: 100%; }
  .concise-ledger-invite { align-items: stretch; flex-direction: column; }
  .concise-ledger-invite .el-button { width: 100%; }
}

@media (max-width: 560px) {
  .ledger-index-tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ledger-index-heading { align-items: flex-start; flex-direction: column; gap: 5px; }
  .ledger-index-heading > span { text-align: left; }
  .decision-desk-section { padding: 15px 13px; }
  .decision-desk-heading { flex-direction: column; gap: 9px; }
  .decision-desk-limit { align-self: flex-start; }
  .decision-card { grid-template-columns: 50px minmax(0, 1fr); padding: 12px 11px 13px; }
  .decision-card-rail { padding-right: 9px; }
  .decision-card-main { padding-left: 10px; }
  .decision-source-stamp { font-size: 11px; }
  .inbox-count-grid { grid-template-columns: minmax(0, 1fr); }
  .inbox-count { padding: 10px 12px; }
  .recent-result-row { align-items: flex-start; }
  .capacity-metrics { grid-template-columns: minmax(0, 1fr); }
  .capacity-basis { align-items: flex-start; flex-direction: column; gap: 2px; }
  .weekly-review-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .weekly-history-heading { align-items: flex-start; flex-direction: column; }
  .weekly-history-tags { justify-content: flex-start; }
  .weekly-review-notes, .briefing-subheading { align-items: flex-start; flex-direction: column; gap: 2px; }
}
</style>
