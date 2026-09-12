<template>
  <div class="materials-page">
    <div class="page-intro">
      <div>
        <h1>资料库</h1>
        <p>保存课件和通知，确认截止时间后加入任务。</p>
      </div>
      <div class="page-actions">
        <el-button v-if="isDetailedView" class="material-manual-action" @click="openCreate">手动添加</el-button>
        <el-button class="material-paste-action" @click="openPasteNotice">粘贴通知</el-button>
        <el-button class="material-upload-action" type="primary" @click="openUpload">上传文件</el-button>
      </div>
    </div>

    <div v-if="error && isDetailedView" class="material-load-error mb-18" role="alert">
      <el-alert :title="error" type="error" show-icon :closable="false" />
      <el-button type="primary" plain :loading="loading || materialsLoading" @click="loadData">重新读取资料</el-button>
    </div>
    <EditConflictCard :visible="Boolean(materialConflict) && !dialogVisible && !detailDialogVisible && !extractionDialogVisible" :title="materialConflictTitle" :message="materialConflictMessage" :latest-fields="materialConflict?.latestFields || []" @view-latest="viewLatestMaterial" @discard="discardMaterialDraft" />
    <div v-if="deepLinkLabel" class="material-deep-link mb-18" role="status">
      <el-alert :title="deepLinkEmpty && !materialNavigationMismatch ? `${deepLinkLabel}；当前筛选无结果。` : deepLinkLabel" type="info" show-icon :closable="false" />
      <el-button v-if="deepLinkEmpty" link type="primary" @click="clearRouteFilters">清除定位筛选</el-button>
    </div>
    <div v-if="loading || materialsLoading" class="sr-only" role="status" aria-live="polite">正在加载资料列表…</div>

    <section class="material-search" role="search" aria-label="查找与筛选资料">
      <div class="material-inbox-search">
        <el-input v-model="keyword" placeholder="搜索文件名、摘要或正文" clearable aria-label="搜索资料文件名、摘要或正文" />
        <button v-if="isConciseView" type="button" class="material-filter-toggle" :aria-expanded="materialFiltersOpen" aria-controls="material-filter-options" @click="materialFiltersOpen = !materialFiltersOpen">
          {{ materialFiltersOpen ? '收起筛选' : '筛选' }}<span v-if="activeMaterialFilterCount">{{ activeMaterialFilterCount }}</span>
        </button>
        <p v-if="materialsSummaryReady" class="material-search-count" role="status">{{ filteredMaterials.length }} 份资料</p>
      </div>
      <div v-show="isDetailedView || materialFiltersOpen" id="material-filter-options" class="material-filter-controls">
        <label>
          <span>课程</span>
          <el-select v-model="courseFilter" clearable placeholder="全部课程" aria-label="按课程筛选资料">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </label>
        <label>
          <span>资料类型</span>
          <el-select v-model="materialTypeFilter" clearable placeholder="全部类型" aria-label="按资料类型筛选">
            <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </label>
        <label>
          <span>处理状态</span>
          <el-select v-model="processingStatusFilter" clearable placeholder="全部状态" aria-label="按资料处理状态筛选">
            <el-option label="已处理" value="processed" />
            <el-option label="处理失败" value="failed" />
            <el-option label="待处理" value="pending" />
          </el-select>
        </label>
        <label>
          <span>标签</span>
          <el-input v-model="tagFilter" placeholder="输入标签" clearable aria-label="按标签筛选资料" />
        </label>
      </div>
      <div v-if="hasUserMaterialFilters" class="material-filter-summary">
        <p>{{ materialFilterSummary }}</p>
        <el-button link aria-label="清除资料搜索和筛选条件" @click="resetMaterialFilters">清除筛选</el-button>
      </div>
    </section>

    <MaterialInboxFocus
      v-if="isConciseView"
      class="material-inbox-section"
      :state="materialInboxState"
      :materials="inboxMaterials"
      :busy-material-ids="retryingMaterialIds"
      :filtered-empty="hasActiveMaterialFilter && !filteredMaterials.length"
      @retry-load="loadData"
      @retry-material="retryMaterial"
      @extract-material="openExtraction"
      @detail-material="openDetail"
      @upload-material="openUpload"
      @show-all="showDetailedMaterials"
    />

    <details v-if="isDetailedView" class="material-flow">
      <summary class="material-flow-toggle"><span>资料如何变成任务</span><span>识别后，由你确认创建</span></summary>
      <div class="material-flow-heading">
        <div>
          <h2 id="material-flow-heading">从资料到截止任务</h2>
        </div>
          <p v-if="isDetailedView" class="material-flow-heading-note">识别只提供候选，正式任务仍由你确认</p>
      </div>
      <ol class="material-flow-list">
        <li class="material-flow-item">
          <article class="material-flow-card material-flow-card--intake">
            <div class="material-flow-label">
              <span class="material-flow-index" aria-hidden="true">01</span>
              <span>保存资料</span>
            </div>
            <h3 v-if="isDetailedView">先把资料保存好</h3>
            <p v-if="isDetailedView" class="material-flow-action"><strong>你要做</strong> 上传文件，或手动补充文件名、正文和标签。</p>
            <p class="material-flow-state" :class="`is-${materialIntakeState.tone}`" aria-live="polite">{{ materialIntakeState.label }}</p>
            <p v-if="isDetailedView" class="material-flow-boundary"><strong>这里会发生什么</strong> 这一步只保存资料；处理失败时，需要你重试或补充正文。</p>
          </article>
        </li>
        <li class="material-flow-item">
          <article class="material-flow-card material-flow-card--recognition">
            <div class="material-flow-label">
              <span class="material-flow-index" aria-hidden="true">02</span>
              <span>智能识别</span>
            </div>
            <h3 v-if="isDetailedView">从正文中找出截止任务候选</h3>
            <p v-if="isDetailedView" class="material-flow-action"><strong>你要做</strong> 打开已处理资料，选择识别方式，查看日期、任务名和来源。</p>
            <p class="material-flow-state" :class="`is-${extractionFlowState.tone}`" aria-live="polite">{{ extractionFlowState.label }}</p>
            <div v-if="isDetailedView && extractionFlowStatuses.length" class="material-flow-statuses" role="list" aria-label="智能识别状态统计">
              <span v-for="status in extractionFlowStatuses" :key="status.key" class="material-flow-status" :class="`is-${status.tone}`" role="listitem">
                <span>{{ status.label }}</span><strong>{{ status.count }}</strong>
              </span>
            </div>
            <p v-if="isDetailedView" class="material-flow-boundary"><strong>确认边界</strong> 识别结果只是候选，不会自动写入正式任务。</p>
          </article>
        </li>
        <li class="material-flow-item">
          <article class="material-flow-card material-flow-card--confirmation">
            <div class="material-flow-label">
              <span class="material-flow-index" aria-hidden="true">03</span>
            <span>确认后创建任务</span>
            </div>
            <h3 v-if="isDetailedView">核对后，再加入任务清单</h3>
            <p v-if="isDetailedView" class="material-flow-action"><strong>你要做</strong> 逐条核对日期、任务名称、预计用时和来源原文，再勾选候选。</p>
            <p class="material-flow-state" :class="`is-${confirmationFlowState.tone}`" aria-live="polite">{{ confirmationFlowState.label }}</p>
            <div v-if="isDetailedView && confirmationFlowStatuses.length" class="material-flow-statuses" role="list" aria-label="人工确认状态统计">
              <span v-for="status in confirmationFlowStatuses" :key="status.key" class="material-flow-status" :class="`is-${status.tone}`" role="listitem">
                <span>{{ status.label }}</span><strong>{{ status.count }}</strong>
              </span>
            </div>
            <p v-if="isDetailedView" class="material-flow-boundary"><strong>确认边界</strong> 只有点击“确认并创建任务”，候选才会成为正式任务。</p>
          </article>
        </li>
      </ol>
    </details>

    <el-card v-if="isDetailedView" class="table-card" shadow="never" v-loading="loading || materialsLoading" :aria-busy="loading || materialsLoading">
      <div class="table-toolbar">
        <div class="material-toolbar-heading">
          <h2 id="materials-heading" tabindex="-1">我的资料 <el-tag v-if="materialsSummaryReady" size="small" effect="plain">{{ materials.length }}</el-tag></h2>
        </div>
      </div>
      <div class="table-wrap">
        <el-table :data="filteredMaterials" :empty-text="tableEmptyText" :row-class-name="materialRowClassName" aria-labelledby="materials-heading">
          <el-table-column label="文件名称" min-width="220">
            <template #default="{ row }">
              <div class="row-title material-table-name">{{ row.original_filename }}</div>
              <div class="row-meta material-table-meta">{{ row.file_type || '未知格式' }}</div>
              <div v-for="snippet in row.match_snippets || []" :key="snippet" class="match-snippet">{{ snippet }}</div>
            </template>
          </el-table-column>
          <el-table-column label="所属课程" min-width="150">
            <template #default="{ row }"><div class="material-table-course">{{ courseName(row.course_id) }}</div></template>
          </el-table-column>
          <el-table-column label="资料类型" width="140">
            <template #default="{ row }">{{ row.material_type || '未分类' }}</template>
          </el-table-column>
          <el-table-column label="标签" min-width="180">
            <template #default="{ row }">
              <el-tag v-for="tag in row.tags || []" :key="tag" size="small" effect="plain" class="tag-gap">{{ tag }}</el-tag>
              <span v-if="!row.tags?.length" class="muted">暂无</span>
            </template>
          </el-table-column>
          <el-table-column label="处理状态" width="120">
            <template #default="{ row }"><el-tag size="small" :type="statusType(row.processing_status)">{{ statusLabel(row.processing_status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="识别状态" width="120">
            <template #default="{ row }"><el-tag size="small" :type="extractionStatusType(row.extraction_status)">{{ extractionStatusLabel(row.extraction_status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :aria-label="`查看资料详情：${row.original_filename}`" @click="openDetail(row)">详情</el-button>
              <el-button v-if="row.processing_status === 'processed' && row.extracted_text" link type="success" :aria-label="`${extractionActionLabel(row)}：${row.original_filename}`" @click="openExtraction(row)">{{ extractionActionLabel(row) }}</el-button>
              <el-button v-if="row.processing_status === 'failed'" link type="warning" :loading="retryingMaterialIds.includes(row.id)" :disabled="retryingMaterialIds.includes(row.id)" :aria-label="`重试解析资料：${row.original_filename}`" @click="retryMaterial(row)">重试</el-button>
              <el-button link type="primary" :aria-label="`编辑资料：${row.original_filename}`" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" :aria-label="`删除资料：${row.original_filename}`" @click="removeMaterial(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑资料' : '新增资料'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="92px" class="dialog-form">
        <el-form-item label="文件名称" required>
          <el-input v-model="form.original_filename" placeholder="例如：数据结构实验一.pdf" />
        </el-form-item>
        <el-form-item label="所属课程">
          <el-select v-model="form.course_id" clearable placeholder="选择课程" style="width: 100%">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件格式">
          <el-input v-model="form.file_type" placeholder="pdf / docx / txt / png" />
        </el-form-item>
        <el-form-item label="资料类型">
          <el-select v-model="form.material_type" clearable placeholder="选择资料类型" style="width: 100%">
            <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tagsText" placeholder="多个标签用逗号分隔" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="填写资料摘要或备注" />
        </el-form-item>
        <el-form-item label="提取文本">
          <el-input v-model="form.extracted_text" type="textarea" :rows="5" placeholder="解析失败时，可在这里手动补充正文" />
        </el-form-item>
      </el-form>
      <EditConflictCard :visible="Boolean(materialConflict) && dialogVisible" :title="materialConflictTitle" :message="materialConflictMessage" :latest-fields="materialConflict?.latestFields || []" @view-latest="viewLatestMaterial" @discard="discardMaterialDraft" />
      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveMaterial">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传课程资料" width="620px" destroy-on-close>
      <el-form label-width="92px" class="dialog-form">
        <el-form-item label="所属课程">
          <el-select v-model="uploadCourseId" clearable placeholder="可选，稍后也可以编辑" style="width: 100%">
            <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="资料类型">
          <el-select v-model="uploadMaterialType" clearable placeholder="可选" style="width: 100%">
            <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件" required>
          <el-upload
            v-model:file-list="uploadFileList"
            drag
            multiple
            :auto-upload="false"
            :limit="uploadPolicy.max_upload_files"
            :before-upload="validateUploadFile"
            :on-exceed="handleUploadExceed"
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.gif,.bmp,.webp"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到这里，或 <em>点击选择</em></div>
            <template #tip><div class="el-upload__tip">支持 PDF、DOCX、TXT、MD 和常见图片，单个文件不超过 {{ uploadPolicy.max_upload_size_mb }} MB。</div></template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="form-actions">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="uploading" @click="submitUpload">开始上传并解析</el-button>
        </div>
      </template>
    </el-dialog>

    <PasteNoticeDialog
      :visible="pasteNoticeVisible"
      :draft="pasteNoticeDraft"
      :submitting="pastingNotice"
      :error="pasteNoticeError"
      :duplicate="pasteNoticeDuplicate"
      @close="closePasteNotice"
      @show-existing="showExistingPastedNotice"
      @submit="submitPastedNotice"
    />
    <ConfirmedTasksDialog
      :visible="confirmedTasksVisible"
      :refs="extractionResult?.confirmed_task_refs || []"
      @close="confirmedTasksVisible = false"
      @navigate="openConfirmedTaskTarget"
      @open-task-list="openTaskListFromConfirmation"
    />

    <el-dialog v-model="detailDialogVisible" title="资料详情" width="680px" destroy-on-close>
      <template v-if="detailMaterial">
        <div class="detail-grid">
          <div><span>文件名</span><strong>{{ detailMaterial.original_filename }}</strong></div>
          <div><span>格式</span><strong>{{ (detailMaterial.file_type || '未知').toUpperCase() }}</strong></div>
          <div><span>大小</span><strong>{{ formatFileSize(detailMaterial.file_size) }}</strong></div>
          <div><span>状态</span><el-tag size="small" :type="statusType(detailMaterial.processing_status)">{{ statusLabel(detailMaterial.processing_status) }}</el-tag></div>
          <div><span>智能识别</span><el-tag size="small" :type="extractionStatusType(detailMaterial.extraction_status)">{{ extractionStatusLabel(detailMaterial.extraction_status) }}</el-tag></div>
        </div>
        <el-alert v-if="detailMaterial.processing_error" :title="detailMaterial.processing_error" type="warning" show-icon class="detail-alert" />
        <div class="detail-section">
            <div class="detail-label">解析后的正文</div>
          <pre v-if="detailMaterial.extracted_text" class="text-preview">{{ detailMaterial.extracted_text }}</pre>
            <div v-else class="empty-state">暂无解析正文，可以编辑资料后手动补充。</div>
        </div>
        <div class="detail-actions">
          <el-button v-if="!detailMaterial.extracted_text" type="primary" plain @click="openEditFromDetail(detailMaterial)">编辑并补充正文</el-button>
          <el-button v-if="detailMaterial.stored_path" @click="downloadMaterial(detailMaterial)">下载原文件</el-button>
          <el-button v-if="detailMaterial.processing_status === 'processed' && detailMaterial.extracted_text" type="success" :aria-label="`${extractionActionLabel(detailMaterial)}：${detailMaterial.original_filename}`" @click="openExtraction(detailMaterial)">{{ extractionActionLabel(detailMaterial) }}</el-button>
          <el-button v-if="detailMaterial.processing_status === 'failed'" type="warning" @click="retryMaterial(detailMaterial)">重新解析</el-button>
        </div>
        <EditConflictCard :visible="Boolean(materialConflict) && detailDialogVisible" :title="materialConflictTitle" :message="materialConflictMessage" :latest-fields="materialConflict?.latestFields || []" @view-latest="viewLatestMaterial" @discard="discardMaterialDraft" />
      </template>
    </el-dialog>

    <el-dialog v-model="extractionDialogVisible" :title="extractionDialogTitle()" width="900px" destroy-on-close>
      <el-alert v-if="extractionError" :title="extractionError" type="error" show-icon :closable="false" class="detail-alert" role="alert" />
      <div v-if="!extractionResult && !materialConflict" v-loading="extractionLoading" class="provider-picker">
        <el-alert
          title="资料上传或重试后，默认会先用本地规则识别；当前没有可用结果，请选择本次识别方式。外部 AI 只在本次操作中调用，确认结果后才会创建正式任务。"
          type="info"
          show-icon
          :closable="false"
          class="detail-alert"
        />
        <el-radio-group v-model="extractionProvider" class="provider-options" aria-label="选择智能识别方式">
          <el-radio
            v-for="provider in extractionPolicy.providers"
            :key="provider.id"
            :value="provider.id"
            :disabled="!provider.available"
            border
            class="provider-option"
          >
            <span class="provider-option-content">
              <strong>{{ provider.label }}</strong>
              <span>{{ provider.description }}</span>
              <small v-if="provider.model">当前模型：{{ provider.model }}</small>
              <small v-else-if="provider.id === 'openai-compatible' && !provider.available">未配置 LLM_API_KEY / LLM_MODEL</small>
            </span>
          </el-radio>
        </el-radio-group>
        <el-alert
          v-if="selectedExtractionProvider?.sends_data_externally"
          title="隐私提示：本次识别会将文件名和解析后的正文发送到已配置的外部 AI 服务。"
          type="warning"
          show-icon
          :closable="false"
          class="provider-warning"
        />
      </div>
      <template v-if="extractionResult">
        <el-alert
          v-if="!materialConflict"
          :title="extractionResult.status === 'confirmed' ? `已创建 ${extractionResult.confirmed_task_ids?.length || 0} 条任务。你可以直接查看刚创建的任务。` : extractionResult.needs_review ? '结果包含待确认信息，请核对日期、任务名称和来源原文；确认后才会创建正式任务。' : '结果已通过基础校验，请确认后才会创建正式任务。'"
          :type="extractionResult.status === 'confirmed' ? 'success' : extractionResult.needs_review ? 'warning' : 'success'"
          show-icon
          class="detail-alert"
        />
        <div class="extraction-meta">
          <span>课程识别：<strong>{{ extractionResult.course_name || '未识别' }}</strong></span>
          <span>识别方式：<strong>{{ providerDisplayName(extractionResult.provider) }}</strong></span>
        </div>
        <div class="extraction-editors">
          <div class="extraction-editor-group">
            <el-select v-model="extractionCourseId" clearable placeholder="确认所属课程" aria-label="确认智能识别结果所属课程" style="width: 220px">
              <el-option v-for="course in courses" :key="course.id" :label="course.name" :value="course.id" />
            </el-select>
          </div>
          <div class="extraction-editor-group">
            <el-select v-model="extractionMaterialType" clearable placeholder="资料类型" aria-label="确认智能识别结果资料类型" style="width: 180px">
              <el-option v-for="type in materialTypes" :key="type" :label="type" :value="type" />
            </el-select>
          </div>
          <div class="extraction-editor-group">
            <el-input v-model="extractionTagsText" placeholder="标签，用逗号分隔" aria-label="确认智能识别结果标签" style="width: 260px" />
          </div>
        </div>
        <section class="extraction-evidence-card" aria-label="字段来源说明">
          <button
            type="button"
            class="extraction-evidence-toggle"
            :aria-expanded="extractionEvidenceExpanded"
            aria-controls="extraction-evidence-details"
            @click="extractionEvidenceExpanded = !extractionEvidenceExpanded"
          >
            <span>字段来源说明</span>
            <span class="extraction-evidence-toggle-state">{{ extractionEvidenceExpanded ? '收起' : '展开' }}</span>
          </button>
          <p class="extraction-evidence-summary">
            <span>课程、资料类型和标签的识别来源</span>
            <span v-if="extractionEvidenceRevisionCount" class="field-evidence-note">{{ extractionEvidenceRevisionCount }} 项当前值已由用户修订</span>
          </p>
          <div v-if="extractionEvidenceExpanded" id="extraction-evidence-details" class="extraction-evidence-details" role="region" aria-label="字段来源详情">
            <div class="extraction-evidence-help">这里只展示与当前值匹配的系统依据；修改字段后，原始来源不会被当作当前值。</div>
            <div v-for="(field, index) in extractionEvidenceCardItems" :key="`${field.label}-${index}`" class="extraction-evidence-field">
              <div class="extraction-evidence-heading">
                <span class="field-evidence-value">{{ field.label }}</span>
                <span class="field-evidence-source">{{ field.sourceLabel }}</span>
              </div>
              <span v-if="field.revised" class="field-evidence-note">当前值已由用户修订，原始识别来源保留</span>
              <span v-for="(snippet, snippetIndex) in field.snippets" :key="`${field.label}-${snippetIndex}-${snippet}`" class="field-evidence-snippet">{{ snippet }}</span>
            </div>
            <div v-if="!extractionEvidenceCardItems.length" class="field-evidence-source">来源待确认</div>
          </div>
        </section>
        <div class="table-wrap extraction-table-wrap extraction-desktop-table">
          <el-table :data="extractionTasks" empty-text="暂未识别到任务" aria-label="智能识别任务结果">
          <el-table-column label="确认" width="70">
            <template #default="{ row }"><el-checkbox v-model="row.selected" :aria-label="`选择智能识别任务：${row.name || '未命名任务'}`" /></template>
          </el-table-column>
          <el-table-column label="任务名称" min-width="210">
            <template #default="{ row }"><el-input v-model="row.name" size="small" :aria-label="`任务名称：${row.name || '未命名任务'}`" /></template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }"><el-input v-model="row.task_type" size="small" :aria-label="`任务类型：${row.name || '未命名任务'}`" /></template>
          </el-table-column>
          <el-table-column label="截止时间" width="205">
            <template #default="{ row }">
              <el-date-picker v-model="row.due_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" size="small" placeholder="待补充" :aria-label="`截止时间：${row.name || '未命名任务'}`" />
            </template>
          </el-table-column>
          <el-table-column label="预计用时" width="145">
            <template #default="{ row }">
              <el-input-number
                v-model="row.estimated_minutes"
                :min="15"
                :max="10080"
                :step="15"
                size="small"
                controls-position="right"
                placeholder="可留空"
                class="extraction-duration-input"
                :aria-label="`预计用时：${row.name || '未命名任务'}`"
              />
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="100">
            <template #default="{ row }">{{ `${Math.round((row.confidence || 0) * 100)}%` }}</template>
          </el-table-column>
          <el-table-column label="来源 / 提示" min-width="230">
            <template #default="{ row }">
              <div class="row-meta">{{ row.source_quote || '无来源原文' }}</div>
              <el-tag v-for="warning in row.warnings || []" :key="warning" size="small" type="warning" class="tag-gap extraction-warning-tag">{{ extractionWarningLabel(warning) }}</el-tag>
            </template>
          </el-table-column>
          </el-table>
        </div>
        <ExtractionCandidatesEditor :tasks="extractionTasks" />
        <el-alert
          v-if="!extractionTasks.length"
          title="这份资料暂未识别出可确认的任务。可编辑资料补充正文或修正内容后，再重新识别。"
          type="info"
          show-icon
          :closable="false"
          class="detail-alert"
        />
      </template>
      <EditConflictCard :visible="Boolean(materialConflict) && extractionDialogVisible" :title="materialConflictTitle" :message="materialConflictMessage" :latest-fields="materialConflict?.latestFields || []" @view-latest="viewLatestMaterial" @discard="discardMaterialDraft" />
      <template #footer>
        <div class="form-actions">
          <el-button @click="extractionDialogVisible = false">取消</el-button>
          <el-button v-if="!extractionResult && !materialConflict" type="primary" :loading="extractionLoading" :disabled="!selectedExtractionProvider?.available || extractionLoading" @click="runExtraction">开始智能识别</el-button>
          <el-button v-if="extractionResult && !extractionTasks.length" type="primary" plain @click="editExtractionMaterial">编辑资料并补充正文</el-button>
          <el-button v-if="extractionResult && extractionTasks.length && extractionResult.status !== 'confirmed'" type="primary" :loading="extractionSaving" :disabled="extractionSaving || Boolean(materialConflict)" @click="confirmExtraction">确认并创建任务</el-button>
          <el-button v-if="extractionResult?.status === 'confirmed'" type="primary" @click="openCreatedTasks">查看刚创建的任务</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import {
  ElAlert,
  ElCard,
  ElCheckbox,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElRadio,
  ElRadioGroup,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElUpload,
} from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { coursesApi, materialsApi } from '../api'
import EditConflictCard from '../components/EditConflictCard.vue'
import MaterialInboxFocus from '../components/MaterialInboxFocus.vue'
import { useViewMode } from '../composables/useViewMode'
import { navigationKey } from '../utils/materialSourceNavigation'
import { extractionWarningLabel } from '../utils/extractionWarning'
import { editBaseline, editRequestConfig, extractionPreviewBaseline, isEditConflict, isEntityGone, preconditionMessage } from '../utils/editPrecondition'
import { buildPastedNotice, localReferenceDateTime } from '../utils/pasteNotice'

const PasteNoticeDialog = defineAsyncComponent(() => import('../components/PasteNoticeDialog.vue'))
const ConfirmedTasksDialog = defineAsyncComponent(() => import('../components/ConfirmedTasksDialog.vue'))
const ExtractionCandidatesEditor = defineAsyncComponent(() => import('../components/ExtractionCandidatesEditor.vue'))

const materialTypes = ['课程大纲', '课堂讲义', '教材或阅读材料', '作业要求', '实验资料', '复习资料', '其他']
const extractionEvidenceSourceLabels = Object.freeze({
  filename: '来源：文件名',
  text: '来源：资料正文',
  both: '来源：文件名与资料正文',
  rule_inference: '来源：本地规则推断',
  unconfirmed: '来源待确认',
})
const extractionEvidenceSources = new Set(Object.keys(extractionEvidenceSourceLabels))
const extractionFlowStatusMeta = Object.freeze({
  not_started: { label: '未识别', tone: 'neutral' },
  ready: { label: '待确认', tone: 'ready' },
  needs_review: { label: '待确认', tone: 'review' },
  confirmed: { label: '已确认', tone: 'confirmed' },
  failed: { label: '识别失败', tone: 'failed' },
  unknown: { label: '状态待确认', tone: 'unknown' },
})
const extractionFlowStatusOrder = Object.freeze(['not_started', 'ready', 'needs_review', 'confirmed', 'failed', 'unknown'])
const processingFlowStatusMeta = Object.freeze({
  pending: { label: '待处理', tone: 'neutral' },
  processing: { label: '处理中', tone: 'ready' },
  processed: { label: '已处理', tone: 'confirmed' },
  failed: { label: '处理失败', tone: 'failed' },
  unknown: { label: '状态待确认', tone: 'unknown' },
})
const loading = ref(false)
const materialsLoading = ref(false)
const materialsLoaded = ref(false)
const saving = ref(false)
const error = ref('')
const keyword = ref('')
const courseFilter = ref(null)
const materialTypeFilter = ref('')
const processingStatusFilter = ref('')
const tagFilter = ref('')
const dialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const extractionDialogVisible = ref(false)
const editingId = ref(null)
const editingBaseline = ref(null)
const materialConflict = ref(null)
const materialConflictTitle = computed(() => materialConflict.value?.state === 'missing'
  ? '这份资料已不存在'
  : materialConflict.value?.state === 'replacement'
    ? '这个编号已换成另一份资料'
    : materialConflict.value?.state === 'invalid'
      ? '无法确认这份识别预览'
      : '这份内容刚被其他页面更新了')
const materialConflictMessage = computed(() => materialConflict.value?.state === 'missing'
  ? '本次没有覆盖内容，当前草稿仍保留。可查看最新状态，或放弃草稿后重新选择。'
  : materialConflict.value?.state === 'replacement'
    ? '本次没有覆盖新资料，当前草稿仍保留。请放弃草稿后重新选择资料。'
    : materialConflict.value?.state === 'invalid'
      ? '这份预览缺少可验证的信息，未应用预览。请查看最新状态，再重新打开资料。'
      : '本次未覆盖新内容，当前草稿仍保留。先查看最新内容，再决定是否放弃这次修改。')
const courses = ref([])
const materials = ref([])
const uploadFileList = ref([])
const uploadCourseId = ref(null)
const uploadMaterialType = ref('')
const uploading = ref(false)
const pasteNoticeVisible = ref(false)
const pastingNotice = ref(false)
const pasteNoticeError = ref('')
const pasteNoticeDuplicate = ref(false)
const pasteNoticeDraft = reactive({ title: '', text: '', sourceTime: '' })
const confirmedTasksVisible = ref(false)
const retryingMaterialIds = ref([])
const detailMaterial = ref(null)
const extractionMaterial = ref(null)
const extractionBaseline = ref(null)
const extractionResult = ref(null)
const extractionTasks = ref([])
const extractionLoading = ref(false)
const extractionSaving = ref(false)
const extractionError = ref('')
const extractionProvider = ref('local-rules')
const extractionPolicy = ref({
  default_provider: 'local-rules',
  providers: [
    {
      id: 'local-rules',
      label: '本地规则',
      description: '在本机使用关键词和日期规则，不发送资料正文。',
      available: true,
      sends_data_externally: false,
      model: null,
    },
  ],
})
const extractionCourseId = ref(null)
const extractionMaterialType = ref('')
const extractionTagsText = ref('')
const extractionEvidenceExpanded = ref(false)
const courseEvidenceView = computed(() => buildFieldEvidenceView('course_name'))
const materialTypeEvidenceView = computed(() => buildFieldEvidenceView('material_type'))
const tagEvidenceView = computed(buildTagEvidenceView)
const extractionEvidenceCardItems = computed(() => {
  const fields = [
    { label: '课程', view: courseEvidenceView.value },
    { label: '资料类型', view: materialTypeEvidenceView.value },
  ].map(({ label, view }) => ({
    label,
    sourceLabel: view.sourceLabel,
    snippets: view.snippets,
    revised: view.revised,
  }))
  const tagView = tagEvidenceView.value
  const tagFields = tagView.items.map((item) => ({
    label: `标签“${item.value}”`,
    sourceLabel: item.sourceLabel,
    snippets: item.snippets,
    revised: false,
  }))
  if (!tagFields.length || tagView.showPending) {
    tagFields.push({
      label: '标签',
      sourceLabel: '来源待确认',
      snippets: [],
      revised: tagView.revised,
    })
  }
  return [...fields, ...tagFields]
})
const extractionEvidenceRevisionCount = computed(() => extractionEvidenceCardItems.value.filter((field) => field.revised).length)
const uploadPolicy = ref({ max_upload_size_mb: 20, max_upload_files: 10, extensions: [] })
const form = reactive(emptyForm())
const route = useRoute()
const router = useRouter()
const { isConciseView, isDetailedView, setViewMode } = useViewMode()
const materialFiltersOpen = ref(false)
let materialRequestId = 0
let initialized = false

const filteredMaterials = computed(() => {
  const filters = routeFilters.value
  return materials.value.filter((material) => {
    const viewMatch = !filters.view
      || (filters.view === 'current_inbox' && (['ready', 'needs_review', 'failed'].includes(material.extraction_status) || material.processing_status === 'failed'))
      || (filters.view === 'failed_materials' && (material.processing_status === 'failed' || material.extraction_status === 'failed'))
      || (filters.view === 'review_materials' && material.extraction_status === 'needs_review')
    return viewMatch && (!filters.materialId || (material.id === filters.materialId && (!filters.navigationKeyProvided || Boolean(filters.navigationKey) && navigationKey(material.navigation_key) === filters.navigationKey)))
  })
})

function positiveRouteId(value) {
  const id = Number(value)
  return Number.isInteger(id) && id > 0 ? id : null
}

const routeFilters = computed(() => ({
  materialId: positiveRouteId(route.query.material_id),
  navigationKey: navigationKey(route.query.navigation_key),
  navigationKeyProvided: Object.prototype.hasOwnProperty.call(route.query, 'navigation_key'),
  view: ['current_inbox', 'failed_materials', 'review_materials'].includes(route.query.view) ? route.query.view : '',
}))
const materialNavigationMismatch = computed(() => {
  const filters = routeFilters.value
  return Boolean(filters.materialId && filters.navigationKeyProvided && materialsSummaryReady.value
    && (!filters.navigationKey || !materials.value.some((material) => material.id === filters.materialId && navigationKey(material.navigation_key) === filters.navigationKey)))
})

const deepLinkLabel = computed(() => {
  const filters = routeFilters.value
  if (filters.materialId && materialNavigationMismatch.value) return `这个来源已失效，未打开同编号的新资料；可清除定位后重新选择。`
  if (filters.materialId) return filters.navigationKey ? `已按来源记录定位资料：资料 #${filters.materialId}` : `已定位资料：资料 #${filters.materialId}`
  if (filters.view === 'current_inbox') return '已打开筛选视图：当前资料'
  if (filters.view === 'failed_materials') return '已打开筛选视图：处理失败的资料'
  if (filters.view === 'review_materials') return '已打开筛选视图：待确认资料'
  return ''
})
const hasRouteFilters = computed(() => Boolean(routeFilters.value.materialId || routeFilters.value.view))
const deepLinkEmpty = computed(() => materialsSummaryReady.value && hasRouteFilters.value && filteredMaterials.value.length === 0)

function materialRowClassName({ row }) {
  return row.id === routeFilters.value.materialId && (!routeFilters.value.navigationKeyProvided || Boolean(routeFilters.value.navigationKey) && navigationKey(row.navigation_key) === routeFilters.value.navigationKey) ? 'source-focused-row' : ''
}

const materialsSummaryReady = computed(() => materialsLoaded.value
  && !loading.value
  && !materialsLoading.value
  && !error.value)
const materialInboxState = computed(() => {
  if (error.value) return 'error'
  if (loading.value || materialsLoading.value) return 'loading'
  if (!materialsLoaded.value) return 'pending'
  return 'ready'
})
const inboxMaterials = computed(() => filteredMaterials.value.map((material) => ({
  ...material,
  course_name: courseName(material.course_id),
  source_focused: material.id === routeFilters.value.materialId && (!routeFilters.value.navigationKeyProvided || Boolean(routeFilters.value.navigationKey) && navigationKey(material.navigation_key) === routeFilters.value.navigationKey),
})))
const flowMaterials = computed(() => filteredMaterials.value)
const activeMaterialFilterCount = computed(() => [
  courseFilter.value,
  materialTypeFilter.value,
  processingStatusFilter.value,
  tagFilter.value.trim(),
].filter(Boolean).length)
const hasUserMaterialFilters = computed(() => Boolean(keyword.value.trim() || activeMaterialFilterCount.value))
const materialFilterSummary = computed(() => [
  keyword.value.trim() ? `搜索“${keyword.value.trim()}”` : '',
  courseFilter.value ? courseName(courseFilter.value) : '',
  materialTypeFilter.value,
  processingStatusFilter.value ? statusLabel(processingStatusFilter.value) : '',
  tagFilter.value.trim() ? `标签“${tagFilter.value.trim()}”` : '',
].filter(Boolean).join('，'))
const hasActiveMaterialFilter = computed(() => Boolean(
  keyword.value.trim()
  || courseFilter.value
  || materialTypeFilter.value
  || processingStatusFilter.value
  || tagFilter.value.trim()
  || routeFilters.value.materialId
  || routeFilters.value.view,
))

function flowStatusKey(value, statusMeta) {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(statusMeta, value) ? value : 'unknown'
}

function summarizeFlowStatuses(rows, field, statusMeta, statusOrder) {
  const counts = Object.fromEntries(statusOrder.map((status) => [status, 0]))
  rows.forEach((row) => {
    const status = flowStatusKey(row?.[field], statusMeta)
    counts[status] += 1
  })
  return statusOrder
    .filter((status) => counts[status] > 0)
    .map((status) => ({ key: status, count: counts[status], ...statusMeta[status] }))
}

function flowStatusCount(statuses, key) {
  return statuses.find((status) => status.key === key)?.count || 0
}

const processingFlowStatusOrder = Object.freeze(['pending', 'processing', 'processed', 'failed', 'unknown'])
const processingFlowStatuses = computed(() => {
  if (!materialsSummaryReady.value) return []
  return summarizeFlowStatuses(flowMaterials.value, 'processing_status', processingFlowStatusMeta, processingFlowStatusOrder)
})
const extractionFlowStatuses = computed(() => {
  if (!materialsSummaryReady.value) return []
  return summarizeFlowStatuses(flowMaterials.value, 'extraction_status', extractionFlowStatusMeta, extractionFlowStatusOrder)
})
const confirmationFlowStatuses = computed(() => extractionFlowStatuses.value.filter((status) => ['ready', 'needs_review', 'confirmed', 'unknown'].includes(status.key)))

const materialIntakeState = computed(() => {
  if (!materialsSummaryReady.value) {
    return { label: error.value ? '资料列表暂不可用' : loading.value || materialsLoading.value ? '正在读取资料列表…' : '等待资料列表', tone: 'unknown' }
  }
  if (!flowMaterials.value.length) {
    return { label: hasActiveMaterialFilter.value ? '当前筛选没有匹配资料' : '还没有资料', tone: 'neutral' }
  }
  const failed = flowStatusCount(processingFlowStatuses.value, 'failed')
  const pending = flowStatusCount(processingFlowStatuses.value, 'pending')
    + flowStatusCount(processingFlowStatuses.value, 'processing')
  const unknown = flowStatusCount(processingFlowStatuses.value, 'unknown')
  if (failed) return { label: `当前列表 ${flowMaterials.value.length} 份资料 · ${failed} 份处理失败`, tone: 'failed' }
  if (pending) return { label: `当前列表 ${flowMaterials.value.length} 份资料 · ${pending} 份待处理`, tone: 'review' }
  if (unknown) return { label: `当前列表 ${flowMaterials.value.length} 份资料 · ${unknown} 份状态待确认`, tone: 'unknown' }
  return { label: `当前列表 ${flowMaterials.value.length} 份资料`, tone: 'ready' }
})

const extractionFlowState = computed(() => {
  if (!materialsSummaryReady.value) {
    return { label: error.value ? '资料列表暂不可用' : loading.value || materialsLoading.value ? '正在读取资料列表…' : '等待资料列表', tone: 'unknown' }
  }
  if (!flowMaterials.value.length) {
    return { label: hasActiveMaterialFilter.value ? '当前筛选没有可识别资料' : '还没有可识别资料', tone: 'neutral' }
  }
  const needsReview = flowStatusCount(extractionFlowStatuses.value, 'needs_review')
  const ready = flowStatusCount(extractionFlowStatuses.value, 'ready')
  const notStarted = flowStatusCount(extractionFlowStatuses.value, 'not_started')
  const failed = flowStatusCount(extractionFlowStatuses.value, 'failed')
  const confirmed = flowStatusCount(extractionFlowStatuses.value, 'confirmed')
  const unknown = flowStatusCount(extractionFlowStatuses.value, 'unknown')
  if (needsReview) return { label: `${needsReview} 份结果待确认`, tone: 'review' }
  if (ready) return { label: `${ready} 份结果待确认`, tone: 'ready' }
  if (notStarted) return { label: `${notStarted} 份资料尚未识别`, tone: 'neutral' }
  if (failed) return { label: `${failed} 份资料识别失败`, tone: 'failed' }
  if (confirmed) return { label: `${confirmed} 份识别结果已确认`, tone: 'confirmed' }
  if (unknown) return { label: `${unknown} 份识别状态待确认`, tone: 'unknown' }
  return { label: '识别状态待确认', tone: 'unknown' }
})

const confirmationFlowState = computed(() => {
  if (!materialsSummaryReady.value) {
    return { label: error.value ? '资料列表暂不可用' : loading.value || materialsLoading.value ? '正在读取资料列表…' : '等待资料列表', tone: 'unknown' }
  }
  if (!flowMaterials.value.length) {
    return { label: hasActiveMaterialFilter.value ? '当前筛选没有待确认资料' : '还没有待确认结果', tone: 'neutral' }
  }
  const ready = flowStatusCount(extractionFlowStatuses.value, 'ready')
  const needsReview = flowStatusCount(extractionFlowStatuses.value, 'needs_review')
  const confirmed = flowStatusCount(extractionFlowStatuses.value, 'confirmed')
  const failed = flowStatusCount(extractionFlowStatuses.value, 'failed')
  const notStarted = flowStatusCount(extractionFlowStatuses.value, 'not_started')
  const unknown = flowStatusCount(extractionFlowStatuses.value, 'unknown')
  if (ready + needsReview) return { label: `待人工确认 ${ready + needsReview} 份候选`, tone: 'review' }
  if (failed) return { label: `${failed} 份识别失败，暂不能确认`, tone: 'failed' }
  if (notStarted) return { label: `${notStarted} 份资料尚未产生识别结果`, tone: 'neutral' }
  if (unknown) return { label: `${unknown} 份状态待确认`, tone: 'unknown' }
  if (confirmed) return { label: `${confirmed} 份结果已确认`, tone: 'confirmed' }
  return { label: '确认状态尚未确定', tone: 'unknown' }
})

const tableEmptyText = computed(() => {
  if (loading.value || materialsLoading.value) return '正在读取资料列表…'
  if (error.value) return '暂时无法读取资料列表，请稍后重试。'
  if (!materialsLoaded.value) return '等待资料列表。'
  if (hasActiveMaterialFilter.value) return '没有符合当前筛选的资料，可清除筛选后再试。'
  return '还没有资料记录，先上传或手动添加一份课程资料。'
})

const selectedExtractionProvider = computed(() => {
  return extractionPolicy.value.providers.find((provider) => provider.id === extractionProvider.value)
})

function emptyForm() {
  return {
    original_filename: '',
    course_id: null,
    file_type: '',
    material_type: '',
    tagsText: '',
    summary: '',
    extracted_text: '',
    originalExtractedText: '',
  }
}

function resetForm() {
  Object.assign(form, emptyForm())
  editingId.value = null
  editingBaseline.value = null
}

function courseName(courseId) {
  return courses.value.find((course) => course.id === courseId)?.name || '未归类课程'
}

function openCreate() {
  materialConflict.value = null
  resetForm()
  dialogVisible.value = true
}

function openUpload() {
  uploadFileList.value = []
  uploadCourseId.value = null
  uploadMaterialType.value = ''
  uploadDialogVisible.value = true
}

function openPasteNotice() {
  pasteNoticeError.value = ''
  pasteNoticeDuplicate.value = false
  if (!pasteNoticeDraft.sourceTime) pasteNoticeDraft.sourceTime = localReferenceDateTime()
  pasteNoticeVisible.value = true
}

function closePasteNotice() {
  if (pastingNotice.value) return
  pasteNoticeVisible.value = false
}

function clearPastedNoticeDraft() {
  pasteNoticeDraft.title = ''
  pasteNoticeDraft.text = ''
  pasteNoticeDraft.sourceTime = ''
  pasteNoticeError.value = ''
  pasteNoticeDuplicate.value = false
}

async function submitPastedNotice() {
  if (pastingNotice.value) return
  pasteNoticeError.value = ''
  pasteNoticeDuplicate.value = false
  const notice = buildPastedNotice(pasteNoticeDraft)
  if (notice.error) {
    pasteNoticeError.value = notice.error
    return
  }
  pastingNotice.value = true
  try {
    const file = new File([notice.content], notice.filename, { type: 'text/plain;charset=utf-8' })
    const uploaded = await materialsApi.upload([file], null, '课程通知', notice.sourceTime)
    const savedMaterial = Array.isArray(uploaded) ? uploaded[0] : null
    if (!editBaseline(savedMaterial)) throw new Error('通知已保存，但未能读取可确认的资料版本。请在资料库中重新打开。')
    materials.value = [savedMaterial, ...materials.value.filter((material) => material.id !== savedMaterial.id)]
    materialsLoaded.value = true
    clearPastedNoticeDraft()
    pasteNoticeVisible.value = false
    await openExtraction(savedMaterial)
  } catch (err) {
    if (err?.status === 409 && err?.code === 'DUPLICATE_FILE') {
      pasteNoticeDuplicate.value = true
      pasteNoticeError.value = ''
      return
    }
    pasteNoticeError.value = err?.message || '保存通知失败，请稍后重试。填写的内容已保留。'
  } finally {
    pastingNotice.value = false
  }
}

async function showExistingPastedNotice() {
  try {
    const existingMaterials = await materialsApi.list()
    materials.value = Array.isArray(existingMaterials) ? existingMaterials : []
    materialsLoaded.value = true
    keyword.value = ''
    setViewMode('detailed')
    pasteNoticeVisible.value = false
    await router.push({ path: '/materials' })
    ElMessage.info('已打开全部资料；重复通知的原文件名可能不同，请在资料清单中查找。')
  } catch (err) {
    pasteNoticeError.value = err?.message || '无法读取已有资料。草稿仍保留，可稍后重试。'
  }
}

async function removeRouteQuery(keys) {
  const query = { ...route.query }
  keys.forEach((key) => { delete query[key] })
  await router.replace({ path: route.path, query, hash: route.hash })
}

function clearRouteFilters() {
  return removeRouteQuery(['material_id', 'navigation_key', 'view'])
}

function resetMaterialFilters() {
  keyword.value = ''
  courseFilter.value = null
  materialTypeFilter.value = ''
  processingStatusFilter.value = ''
  tagFilter.value = ''
}

function handleActionQuery(action) {
  if (action === 'paste-notice') {
    openPasteNotice()
  } else if (action === 'upload') {
    openUpload()
  } else return
  removeRouteQuery(['action']).catch((err) => ElMessage.error(err?.message || '无法清除资料操作参数'))
}

function openDetail(material) {
  materialConflict.value = null
  detailMaterial.value = material
  detailDialogVisible.value = true
}

function openEditFromDetail(material) {
  detailDialogVisible.value = false
  openEdit(material)
}

async function showDetailedMaterials() {
  setViewMode('detailed')
  await nextTick()
  const heading = document.getElementById('materials-heading')
  heading?.focus({ preventScroll: true })
  heading?.scrollIntoView({ behavior: 'auto', block: 'start' })
}

async function focusMaterialDeepLink() {
  if (!routeFilters.value.materialId || !materialsSummaryReady.value) return
  await nextTick()
  await new Promise((resolve) => requestAnimationFrame(resolve))
  await new Promise((resolve) => setTimeout(resolve, 120))
  const target = document.querySelector(isConciseView.value ? '.inbox-item.is-focused' : '.source-focused-row')
  if (!(target instanceof HTMLElement)) return
  target.setAttribute('tabindex', '-1')
  target.scrollIntoView({ behavior: 'auto', block: 'center' })
  target.focus({ preventScroll: true })
}

const statusLabels = { pending: '待处理', processing: '处理中', processed: '已处理', failed: '处理失败' }
function statusLabel(status) { return statusLabels[status] || '状态待确认' }
function statusType(status) { return { processed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }[status] || 'info' }
const extractionStatusLabels = { not_started: '未识别', ready: '待确认', needs_review: '待确认', confirmed: '已确认', failed: '识别失败' }
function extractionStatusLabel(status) { return extractionStatusLabels[status] || '状态待确认' }
function extractionStatusType(status) { return { confirmed: 'success', ready: 'info', needs_review: 'warning', failed: 'danger' }[status] || 'info' }
function hasSavedExtractionResult(material) {
  return Boolean(material?.extraction_result) && !['not_started', 'failed'].includes(material?.extraction_status)
}

function extractionActionLabel(material) {
  if (hasSavedExtractionResult(material)) {
    if (['ready', 'needs_review'].includes(material.extraction_status)) return '查看并确认截止任务'
    if (material.extraction_status === 'confirmed') return '查看已确认任务'
    return '查看截止任务识别结果'
  }
  return '识别截止任务'
}

function extractionDialogTitle() {
  if (extractionResult.value) {
    return extractionResult.value.status === 'confirmed' ? '已确认的截止任务结果' : '查看并确认截止任务'
  }
  return extractionActionLabel(extractionMaterial.value)
}

function formatFileSize(size) {
  if (!size) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
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

function validateUploadFile(file) {
  const maxBytes = uploadPolicy.value.max_upload_size_mb * 1024 * 1024
  if (file.size > maxBytes) {
    ElMessage.warning(`“${file.name}”超过 ${uploadPolicy.value.max_upload_size_mb} MB 限制`)
    return false
  }
  return true
}

function handleUploadExceed() {
  ElMessage.warning(`一次最多选择 ${uploadPolicy.value.max_upload_files} 个文件`)
}

function openEdit(material) {
  const baseline = editBaseline(material)
  if (!baseline) {
    ElMessage.warning(preconditionMessage())
    return
  }
  materialConflict.value = null
  Object.assign(form, {
    original_filename: material.original_filename,
    course_id: material.course_id,
    file_type: material.file_type || '',
    material_type: material.material_type || '',
    tagsText: (material.tags || []).join(', '),
    summary: material.summary || '',
    extracted_text: material.extracted_text || '',
    originalExtractedText: material.extracted_text || '',
  })
  editingId.value = material.id
  editingBaseline.value = baseline
  dialogVisible.value = true
}

function editExtractionMaterial() {
  if (!extractionMaterial.value) return
  extractionDialogVisible.value = false
  openEdit(extractionMaterial.value)
}

async function loadData() {
  materialsLoaded.value = false
  loading.value = true
  error.value = ''
  materials.value = []
  try {
    const [courseData, policy, providerPolicy] = await Promise.all([
      coursesApi.list(),
      materialsApi.uploadPolicy(),
      materialsApi.extractionPolicy(),
    ])
    courses.value = courseData
    uploadPolicy.value = policy
    extractionPolicy.value = providerPolicy
    await loadMaterials()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function loadMaterials() {
  const requestId = ++materialRequestId
  materialsLoading.value = true
  materialsLoaded.value = false
  error.value = ''
  materials.value = []
  try {
    const result = await materialsApi.list({
      q: keyword.value,
      course_id: courseFilter.value,
      material_type: materialTypeFilter.value,
      processing_status: processingStatusFilter.value,
      tag: tagFilter.value,
    })
    if (requestId === materialRequestId) {
      materials.value = result
      materialsLoaded.value = true
    }
  } catch (err) {
    if (requestId === materialRequestId) {
      materialsLoaded.value = false
      error.value = err.message
    }
  } finally {
    if (requestId === materialRequestId) materialsLoading.value = false
  }
}

async function saveMaterial() {
  if (!form.original_filename.trim()) {
    ElMessage.warning('请填写文件名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      original_filename: form.original_filename.trim(),
      course_id: form.course_id,
      file_type: form.file_type.trim() || null,
      material_type: form.material_type || null,
      tags: form.tagsText.split(',').map((tag) => tag.trim()).filter(Boolean),
      summary: form.summary.trim() || null,
    }
    if (!editingId.value || form.extracted_text.trim() !== form.originalExtractedText.trim()) {
      payload.extracted_text = form.extracted_text.trim() || null
    }
    if (editingId.value) {
      const config = editRequestConfig(editingBaseline.value)
      if (!config) {
        ElMessage.warning(preconditionMessage())
        return
      }
      await materialsApi.update(editingId.value, payload, config)
      ElMessage.success('资料已更新')
    } else {
      await materialsApi.create(payload)
      ElMessage.success('资料已添加')
    }
    dialogVisible.value = false
    await loadData()
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'MATERIAL_NOT_FOUND')) {
      materialConflict.value = { baseline: editingBaseline.value, state: isEntityGone(err, 'MATERIAL_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    ElMessage.error(err.message)
  } finally {
    saving.value = false
  }
}

async function submitUpload() {
  const files = uploadFileList.value.map((item) => item.raw).filter(Boolean)
  if (!files.length) {
    ElMessage.warning('请先选择文件')
    return
  }
  uploading.value = true
  try {
    const uploaded = await materialsApi.upload(files, uploadCourseId.value, uploadMaterialType.value)
    const failed = uploaded.filter((material) => material.processing_status === 'failed').length
    ElMessage[failed ? 'warning' : 'success'](failed ? `${uploaded.length} 个文件已保存，其中 ${failed} 个解析失败，可重试` : `已上传并处理 ${uploaded.length} 个文件`)
    uploadDialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    uploading.value = false
  }
}

async function retryMaterial(material) {
  const baseline = editBaseline(material)
  const config = editRequestConfig(baseline)
  if (!config) {
    ElMessage.warning(preconditionMessage())
    return
  }
  if (retryingMaterialIds.value.includes(material.id)) return
  retryingMaterialIds.value = [...retryingMaterialIds.value, material.id]
  try {
    const updated = await materialsApi.retry(material.id, config)
    Object.assign(material, updated)
    ElMessage[updated.processing_status === 'processed' ? 'success' : 'warning'](updated.processing_status === 'processed' ? '资料已重新解析' : updated.processing_error || '重新解析失败')
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'MATERIAL_NOT_FOUND')) {
      materialConflict.value = { baseline, state: isEntityGone(err, 'MATERIAL_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    ElMessage.error(err.message)
  } finally {
    retryingMaterialIds.value = retryingMaterialIds.value.filter((id) => id !== material.id)
  }
}

async function openExtraction(material) {
  if (!editBaseline(material)) {
    ElMessage.warning(preconditionMessage())
    return
  }
  if (!material.extracted_text) {
    ElMessage.warning('资料没有可用正文，请先补充或重新解析')
    return
  }
  materialConflict.value = null
  detailDialogVisible.value = false
  extractionMaterial.value = material
  extractionBaseline.value = null
  extractionDialogVisible.value = true
  extractionResult.value = null
  extractionTasks.value = []
  extractionError.value = ''
  extractionEvidenceExpanded.value = false
  extractionProvider.value = extractionPolicy.value.default_provider || 'local-rules'
  extractionCourseId.value = material.course_id || null
  extractionMaterialType.value = material.material_type || ''
  extractionTagsText.value = (material.tags || []).join(', ')
  try {
    if (material.extraction_result && !['not_started', 'failed'].includes(material.extraction_status)) {
      applyExtractionResult(await materialsApi.extraction(material.id), material)
    }
  } catch (err) {
    if (isEntityGone(err, 'MATERIAL_NOT_FOUND')) {
      materialConflict.value = { baseline: editBaseline(material), state: 'missing' }
      return
    }
    extractionError.value = err.message || '读取识别结果失败，请重试'
  }
}

function providerDisplayName(providerId) {
  return extractionPolicy.value.providers.find((provider) => provider.id === providerId)?.label || providerId || '本地规则'
}

function pendingEvidenceView(revised = false) {
  return {
    sourceLabel: '来源待确认',
    snippets: [],
    revised,
    items: [],
    showPending: true,
  }
}

function safeEvidenceEntry(entry) {
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return null
  if (typeof entry.value !== 'string') return null
  const value = entry.value.trim()
  if (!value || value.length > 120 || !extractionEvidenceSources.has(entry.source)) return null
  if (!Array.isArray(entry.snippets) || entry.snippets.length > 2) return null
  const snippets = []
  for (const snippet of entry.snippets) {
    if (typeof snippet !== 'string') return null
    const normalizedSnippet = snippet.trim()
    if (!normalizedSnippet || normalizedSnippet.length > 180) return null
    snippets.push(normalizedSnippet)
  }
  return { value, source: entry.source, snippets }
}

function safeEvidenceText(value) {
  if (typeof value !== 'string') return ''
  const normalized = value.trim()
  return normalized && normalized.length <= 120 ? normalized : ''
}

function extractionFieldEvidence() {
  const result = extractionResult.value
  const evidence = result && typeof result === 'object' && !Array.isArray(result) ? result.field_evidence : null
  return evidence && typeof evidence === 'object' && !Array.isArray(evidence) ? evidence : null
}

function selectedCourseEvidenceText() {
  const hasSelectedCourse = extractionCourseId.value !== null
    && extractionCourseId.value !== undefined
    && extractionCourseId.value !== ''
  if (!hasSelectedCourse) return ''
  const selectedCourse = courses.value.find((course) => course.id === extractionCourseId.value)
  return safeEvidenceText(selectedCourse?.name)
}

function buildFieldEvidenceView(field) {
  const evidence = safeEvidenceEntry(extractionFieldEvidence()?.[field])
  if (!evidence) return pendingEvidenceView()

  const recognizedValue = safeEvidenceText(extractionResult.value?.[field])
  if (!recognizedValue || evidence.value !== recognizedValue) return pendingEvidenceView()

  let revised = false
  if (field === 'course_name') {
    const selectedCourseValue = selectedCourseEvidenceText()
    const hasSelectedCourse = extractionCourseId.value !== null
      && extractionCourseId.value !== undefined
      && extractionCourseId.value !== ''
    revised = hasSelectedCourse && (!selectedCourseValue || selectedCourseValue !== recognizedValue)
  } else if (field === 'material_type') {
    const currentValue = safeEvidenceText(extractionMaterialType.value)
    revised = currentValue !== recognizedValue
  }

  return {
    sourceLabel: revised ? '来源待确认' : extractionEvidenceSourceLabels[evidence.source],
    snippets: revised ? [] : evidence.snippets,
    revised,
    items: [],
    showPending: revised || evidence.source === 'unconfirmed',
  }
}

function safeExtractionTags(value) {
  if (!Array.isArray(value)) return null
  const tags = []
  for (const tag of value) {
    if (typeof tag !== 'string') return null
    const normalized = tag.trim()
    if (!normalized || normalized.length > 120) return null
    tags.push(normalized)
  }
  return tags
}

function currentExtractionTags() {
  if (typeof extractionTagsText.value !== 'string') return []
  return extractionTagsText.value.split(',').map((tag) => tag.trim()).filter(Boolean)
}

function haveSameTagSet(left, right) {
  const normalizedLeft = [...new Set(left)].sort()
  const normalizedRight = [...new Set(right)].sort()
  return normalizedLeft.length === normalizedRight.length
    && normalizedLeft.every((tag, index) => tag === normalizedRight[index])
}

function buildTagEvidenceView() {
  const evidence = extractionFieldEvidence()
  if (!evidence || !Array.isArray(evidence.tags)) return pendingEvidenceView()
  const originalTags = safeExtractionTags(extractionResult.value?.tags)
  if (!originalTags) return pendingEvidenceView()

  const entries = []
  for (const entry of evidence.tags) {
    const safeEntry = safeEvidenceEntry(entry)
    // Treat the whole field as pending if one entry is malformed, so no
    // untrusted sibling value can be presented as a trustworthy source.
    if (!safeEntry) return pendingEvidenceView()
    if (originalTags.includes(safeEntry.value)) entries.push(safeEntry)
  }

  const currentTags = currentExtractionTags()
  const items = entries
    .filter((entry) => currentTags.includes(entry.value))
    .map((entry) => ({
      value: entry.value,
      sourceLabel: extractionEvidenceSourceLabels[entry.source],
      snippets: entry.source === 'unconfirmed' ? [] : entry.snippets,
    }))
  const currentTagsWithEvidence = new Set(items.map((item) => item.value))
  const showPending = currentTags.length === 0
    || currentTags.some((tag) => !currentTagsWithEvidence.has(tag))
    || entries.some((entry) => entry.source === 'unconfirmed' && currentTags.includes(entry.value))
  return {
    sourceLabel: '',
    snippets: [],
    revised: !haveSameTagSet(originalTags, currentTags),
    items,
    showPending,
  }
}

function applyExtractionResult(result, material = extractionMaterial.value) {
  const previewBaseline = extractionPreviewBaseline(material, result)
  if (!previewBaseline) {
    const openedBaseline = editBaseline(material)
    const replacement = result?.material_id !== openedBaseline?.id
      || (navigationKey(result?.material_navigation_key) && result.material_navigation_key !== openedBaseline?.navigation_key)
    materialConflict.value = {
      baseline: openedBaseline,
      state: replacement ? 'replacement' : 'invalid',
      latestFields: [{
        label: '识别预览',
        value: replacement
          ? '这份预览属于另一份资料，未应用预览。'
          : '无法确认这份预览属于当前资料，未应用预览。',
      }],
    }
    extractionResult.value = null
    extractionTasks.value = []
    extractionBaseline.value = null
    return false
  }
  extractionResult.value = result
  extractionTasks.value = result.tasks.map((task) => ({ ...task, due_at: toLocalDateTimeInput(task.due_at) }))
  extractionMaterialType.value = result.material_type || material?.material_type || ''
  extractionTagsText.value = (result.tags || material?.tags || []).join(', ')
  extractionBaseline.value = previewBaseline
  if (material) {
    Object.assign(material, {
      revision: previewBaseline.revision,
      extraction_status: result.status,
      extraction_result: result,
      extraction_provider: result.provider,
      material_type: result.material_type || material.material_type,
      tags: result.tags || material.tags,
    })
  }
  return true
}

async function runExtraction() {
  const provider = selectedExtractionProvider.value
  if (!extractionMaterial.value || !provider?.available) {
    ElMessage.warning('所选智能识别方式当前不可用')
    return
  }
  if (provider.sends_data_externally) {
    try {
      await ElMessageBox.confirm(
        '本次智能识别会将当前资料的文件名和解析正文发送到后端配置的外部 AI 服务。是否继续？',
        '确认本次外部 AI 调用',
        { type: 'warning', confirmButtonText: '同意并继续', cancelButtonText: '取消' },
      )
    } catch (err) {
      if (err === 'cancel' || err === 'close') return
      ElMessage.error(err?.message || '外部 AI 调用确认失败')
      return
    }
  }
  extractionError.value = ''
  const config = editRequestConfig(editBaseline(extractionMaterial.value))
  if (!config) {
    ElMessage.warning(preconditionMessage())
    return
  }
  extractionLoading.value = true
  try {
    const result = await materialsApi.extract(extractionMaterial.value.id, provider.id, config)
    applyExtractionResult(result)
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'MATERIAL_NOT_FOUND')) {
      materialConflict.value = { baseline: editBaseline(extractionMaterial.value), state: isEntityGone(err, 'MATERIAL_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    extractionError.value = err.message || '智能识别失败，请重试'
  } finally {
    extractionLoading.value = false
  }
}

async function confirmExtraction() {
  const selectedTasks = extractionTasks.value.filter((task) => task.selected)
  if (!extractionMaterial.value || !selectedTasks.length) {
    ElMessage.warning('请至少勾选一条任务')
    return
  }
  const tasksPayload = []
  for (const task of selectedTasks) {
    const rawEstimate = task.estimated_minutes
    if (rawEstimate === '' || rawEstimate === null || rawEstimate === undefined) {
      if (task.remaining_minutes !== null && task.remaining_minutes !== undefined) {
        ElMessage.warning(`“${task.name || '任务'}”填写了剩余用时，请先补充预计用时`)
        return
      }
      tasksPayload.push({ ...task, estimated_minutes: null })
      continue
    }
    const estimate = Number(rawEstimate)
    if (!Number.isInteger(estimate) || estimate < 15 || estimate > 10080) {
      ElMessage.warning(`“${task.name || '任务'}”的预计用时应为 15 到 10080 分钟的整数`)
      return
    }
    if (task.remaining_minutes !== null && task.remaining_minutes !== undefined && (task.estimated_minutes === null || Number(task.remaining_minutes) > estimate)) {
      ElMessage.warning(`“${task.name || '任务'}”的剩余用时不能大于预计用时`)
      return
    }
    tasksPayload.push({ ...task, estimated_minutes: estimate })
  }
  const config = editRequestConfig(extractionBaseline.value)
  if (!config) {
    ElMessage.warning('确认前请重新打开这份资料，检查最新识别结果。')
    return
  }
  extractionSaving.value = true
  try {
    const result = await materialsApi.confirmExtraction(extractionMaterial.value.id, {
      tasks: tasksPayload,
      course_id: extractionCourseId.value,
      material_type: extractionMaterialType.value || null,
      tags: extractionTagsText.value.split(',').map((tag) => tag.trim()).filter(Boolean),
    }, config)
    Object.assign(extractionMaterial.value, {
      extraction_status: result.status,
      extraction_result: result,
      material_type: result.material_type || extractionMaterialType.value || extractionMaterial.value.material_type,
      tags: result.tags || extractionMaterial.value.tags,
    })
    extractionResult.value = { ...extractionResult.value, ...result }
    ElMessage.success(`已确认并创建 ${result.confirmed_task_ids.length} 条任务`)
    await loadData()
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'MATERIAL_NOT_FOUND')) {
      materialConflict.value = { baseline: extractionBaseline.value, state: isEntityGone(err, 'MATERIAL_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    ElMessage.error(err.message)
  } finally {
    extractionSaving.value = false
  }
}

async function openCreatedTasks() {
  confirmedTasksVisible.value = true
}

async function openConfirmedTaskTarget(target) {
  confirmedTasksVisible.value = false
  extractionDialogVisible.value = false
  await router.push(target)
}

async function openTaskListFromConfirmation() {
  confirmedTasksVisible.value = false
  extractionDialogVisible.value = false
  await router.push('/tasks')
}

function downloadMaterial(material) {
  window.open(materialsApi.fileUrl(material.id), '_blank', 'noopener,noreferrer')
}

async function removeMaterial(material) {
  const baseline = editBaseline(material)
  const config = editRequestConfig(baseline)
  if (!config) {
    ElMessage.warning(preconditionMessage())
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除“${material.original_filename}”吗？`, '删除资料', { type: 'warning' })
    await materialsApi.remove(material.id, config)
    ElMessage.success('资料已删除')
    await loadData()
  } catch (err) {
    if (isEditConflict(err) || isEntityGone(err, 'MATERIAL_NOT_FOUND')) {
      materialConflict.value = { baseline, state: isEntityGone(err, 'MATERIAL_NOT_FOUND') ? 'missing' : 'changed' }
      return
    }
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  }
}

async function viewLatestMaterial() {
  const id = materialConflict.value?.baseline?.id
  if (!id) return
  try {
    const latest = await materialsApi.list()
    const material = Array.isArray(latest) ? latest.find((item) => item.id === id) : null
    if (!material) {
      materialConflict.value = { ...materialConflict.value, state: 'missing', latestFields: [{ label: '最新状态', value: '这份资料已不存在，不能继续覆盖。' }] }
      ElMessage.warning('这份资料已不存在；你的修改仍保留。')
      return
    }
    if (editBaseline(material)?.navigation_key !== materialConflict.value?.baseline?.navigation_key) {
      materialConflict.value = { ...materialConflict.value, state: 'replacement', latestFields: [{ label: '最新状态', value: '这个编号现在对应另一份资料，不能继续覆盖。' }] }
      ElMessage.warning('这个编号现在对应另一份资料；你的修改仍保留。')
      return
    }
    materialConflict.value = { ...materialConflict.value, latestFields: [
      { label: '文件名', value: material.original_filename || '未命名资料' },
      { label: '所属课程', value: courseName(material.course_id) },
      { label: '文件格式', value: material.file_type || '未填写' },
      { label: '资料类型', value: material.material_type || '未分类' },
      { label: '标签', value: Array.isArray(material.tags) && material.tags.length ? material.tags.join('、') : '未添加' },
      { label: '摘要', value: material.summary || '未填写摘要' },
      { label: '正文', value: material.extracted_text || '暂无正文' },
    ] }
    ElMessage.info('已读取最新内容；你的修改仍保留。')
  } catch (err) { ElMessage.error(err.message) }
}

async function discardMaterialDraft() {
  try {
    await ElMessageBox.confirm('这会放弃当前未提交的修改，并重新读取资料。是否继续？', '放弃本次修改', { type: 'warning', confirmButtonText: '放弃并重读', cancelButtonText: '保留修改' })
  } catch { return }
  materialConflict.value = null
  dialogVisible.value = false
  extractionDialogVisible.value = false
  detailDialogVisible.value = false
  extractionMaterial.value = null
  extractionBaseline.value = null
  resetForm()
  await loadData()
}

let searchTimer
watch([keyword, courseFilter, materialTypeFilter, processingStatusFilter, tagFilter], () => {
  if (!initialized) return
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadMaterials, 250)
})

watch(() => route.query.q, (value) => {
  const routeKeyword = typeof value === 'string' ? value : ''
  if (keyword.value !== routeKeyword) keyword.value = routeKeyword
})

watch([inboxMaterials, isDetailedView, materialsSummaryReady], () => {
  focusMaterialDeepLink()
})

watch(() => route.query.action, handleActionQuery)

onMounted(() => {
  keyword.value = typeof route.query.q === 'string' ? route.query.q : ''
  handleActionQuery(route.query.action)
  loadData().finally(() => { initialized = true })
})
</script>

<style scoped>
.mb-18 { margin-bottom: 18px; }
.tag-gap { margin: 2px 4px 2px 0; }
.extraction-warning-tag { max-width: 100%; height: auto; line-height: 1.45; vertical-align: top; white-space: normal; }
.extraction-warning-tag :deep(.el-tag__content) { overflow-wrap: anywhere; white-space: normal; }
.muted { color: #667085; font-size: 12px; }
.material-load-error,
.material-deep-link {
  display: flex;
  align-items: center;
  gap: 10px;
}
.material-load-error :deep(.el-alert),
.material-deep-link :deep(.el-alert) { flex: 1 1 auto; min-width: 0; }
.material-load-error :deep(.el-alert__content),
.material-deep-link :deep(.el-alert__content) { min-width: 0; }
.material-load-error :deep(.el-alert__title),
.material-deep-link :deep(.el-alert__title) { white-space: normal; overflow-wrap: anywhere; }
.material-load-error :deep(.el-button),
.material-deep-link :deep(.el-button) { flex: 0 0 auto; min-height: 44px; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 22px; padding: 4px 0 18px; }
.detail-grid > div { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; min-width: 0; color: #7f8a9c; font-size: 13px; }
.detail-grid strong { min-width: 0; color: #344054; font-weight: 600; overflow-wrap: anywhere; }
.detail-alert { margin-bottom: 18px; }
.detail-alert :deep(.el-alert__content) { min-width: 0; }
.detail-alert :deep(.el-alert__title) { white-space: normal; overflow-wrap: anywhere; }
.detail-label { margin-bottom: 8px; color: #667085; font-size: 13px; font-weight: 600; }
.detail-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.text-preview { max-height: 280px; overflow: auto; margin: 0; padding: 14px; color: #475467; background: #f8fafc; border: 1px solid #edf0f5; border-radius: 8px; font: 13px/1.7 "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; white-space: pre-wrap; }
.extraction-meta { display: flex; gap: 28px; margin-bottom: 16px; color: #667085; font-size: 13px; }
.extraction-meta strong { color: #344054; }
.extraction-editors { display: flex; gap: 10px; margin-bottom: 16px; }
.provider-picker { min-height: 230px; }
.provider-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; width: 100%; }
.provider-option { width: 100%; height: auto; min-height: 112px; margin: 0; padding: 16px; white-space: normal; }
.provider-option-content { display: flex; flex-direction: column; gap: 7px; line-height: 1.5; }
.provider-option-content strong { color: #344054; font-size: 15px; }
.provider-option-content span { color: #667085; }
.provider-option-content small { color: #667085; }
.provider-warning { margin-top: 16px; }
.material-filters { flex-wrap: wrap; justify-content: flex-end; }
.extraction-table-wrap { padding: 0; }
.extraction-editor-group { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.extraction-evidence-card { display: grid; gap: 8px; min-width: 0; margin: 0 0 16px; padding: 12px; color: #667085; background: #f1f7f3; border: 1px solid #c8ddd1; border-radius: 9px; font-size: 13px; line-height: 1.5; }
.extraction-evidence-toggle { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; min-height: 44px; padding: 5px 0; color: #344054; text-align: left; background: transparent; border: 0; cursor: pointer; font: inherit; font-size: 13px; font-weight: 700; line-height: 1.5; }
.extraction-evidence-toggle:hover { color: var(--ledger-link); }
.extraction-evidence-toggle:focus-visible { outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 50%, transparent); outline-offset: 3px; }
.extraction-evidence-toggle-state { flex: 0 0 auto; color: var(--ledger-link); font-size: 12px; font-weight: 600; }
.extraction-evidence-summary { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 4px 12px; margin: 0; color: #667085; overflow-wrap: anywhere; }
.extraction-evidence-details { display: grid; gap: 8px; min-width: 0; }
.extraction-evidence-help { color: #667085; overflow-wrap: anywhere; }
.extraction-evidence-field { display: grid; gap: 4px; min-width: 0; padding-top: 8px; border-top: 1px solid #c8ddd1; }
.extraction-evidence-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; }
.field-evidence-source { color: #667085; font-weight: 600; overflow-wrap: anywhere; }
.field-evidence-value { color: #344054; font-weight: 600; overflow-wrap: anywhere; }
.field-evidence-note { color: #b54708; overflow-wrap: anywhere; }
.field-evidence-snippet { max-width: 100%; padding: 4px 6px; color: #475467; background: #f8fafc; border-left: 2px solid #c8ddd1; border-radius: 0 4px 4px 0; overflow-wrap: anywhere; word-break: break-word; white-space: pre-wrap; }
.match-snippet { max-width: 100%; margin-top: 5px; color: var(--ledger-link); font-size: 13px; font-weight: 500; line-height: 1.5; overflow-wrap: anywhere; white-space: normal; }
.extraction-duration-input { width: 125px; }
.source-focused-row td { background: #f1f7f3 !important; }

@media (max-width: 680px) {
  .extraction-desktop-table { display: none; }
  .extraction-editors :deep(.el-input__wrapper),
  .extraction-editors :deep(.el-select__wrapper) { min-height: 44px; }
  .provider-options { grid-template-columns: 1fr; }
  .extraction-editors { flex-direction: column; }
  .extraction-editor-group { width: 100%; }
  .extraction-editors :deep(.el-select), .extraction-editors :deep(.el-input) { width: 100% !important; }
  .extraction-evidence-heading { align-items: flex-start; flex-direction: column; gap: 2px; }
}

.materials-page {
  --materials-ink: var(--ledger-ink, #20392f);
  --materials-paper: var(--ledger-paper, #ffffff);
  --materials-indigo: var(--ledger-indigo, #327864);
  --materials-amber: var(--ledger-amber, #c9822e);
  --materials-amber-text: var(--ledger-amber-text, #946020);
  --materials-coral: var(--ledger-coral, #c94c4c);
  --materials-line: var(--ledger-line, #dbe4de);
  --materials-muted: var(--ledger-muted, #607268);
  min-width: 0;
}

.materials-page h1,
.materials-page h2,
.materials-page h3 {
  overflow-wrap: anywhere;
}

.materials-page .page-actions {
  min-width: 0;
}

.materials-page .page-actions :deep(.el-button) {
  min-height: 44px;
  max-width: 100%;
  min-width: 44px;
  overflow-wrap: anywhere;
  text-align: center;
  white-space: normal;
}

.material-upload-action {
  min-width: 112px;
}

.material-search {
  min-width: 0;
  margin-bottom: 18px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--materials-line);
}

.material-inbox-search {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.material-search-count {
  flex: 0 0 auto;
  margin: 0;
  color: var(--materials-muted);
  font-size: 12px;
}

.material-filter-toggle {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 44px;
  padding: 9px 12px;
  color: var(--materials-indigo);
  background: var(--materials-paper);
  border: 1px solid var(--materials-line);
  border-radius: 8px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.material-filter-toggle:hover,
.material-filter-toggle[aria-expanded="true"] {
  background: #edf5f0;
  border-color: var(--materials-indigo);
}

.material-filter-toggle span {
  display: grid;
  place-items: center;
  min-width: 20px;
  min-height: 20px;
  padding: 0 4px;
  color: #fff;
  background: var(--materials-indigo);
  border-radius: 6px;
  font-size: 11px;
}

.material-filter-toggle:focus-visible,
.material-flow-toggle:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--materials-indigo) 38%, transparent);
  outline-offset: 3px;
}

.material-filter-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}

.material-filter-summary p {
  min-width: 0;
  margin: 0;
  color: var(--materials-muted);
  font-size: 12px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.material-filter-summary :deep(.el-button) { flex: 0 0 auto; min-height: 44px; margin: -8px 0; }

.material-inbox-search :deep(.el-input) {
  flex: 1 1 auto;
  width: 100%;
}

.material-inbox-search :deep(.el-input__wrapper) {
  min-height: 44px;
}

.material-inbox-section {
  margin-bottom: 18px;
}

#materials-heading:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--ledger-indigo) 36%, transparent);
  outline-offset: 4px;
}

.materials-page :deep(.el-dialog .el-button) {
  min-height: 44px;
  max-width: 100%;
  overflow-wrap: anywhere;
  white-space: normal;
}

.material-flow {
  min-width: 0;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--materials-line);
}

.material-flow-toggle {
  min-height: 40px;
  color: var(--materials-ink);
  cursor: pointer;
  font-size: 13px;
  line-height: 40px;
}

.material-flow-toggle span + span {
  margin-left: 20px;
  color: var(--materials-muted);
  font-size: 12px;
}

.material-flow-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 18px;
  min-width: 0;
  margin: 14px 0 11px;
}

.material-flow-eyebrow,
.material-toolbar-kicker {
  margin: 0 0 4px;
  color: var(--materials-muted);
  font-family: Bahnschrift, "Arial Narrow", "Microsoft YaHei", sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.material-flow-heading h2 {
  margin: 0;
  color: var(--materials-ink);
  font-size: 16px;
  letter-spacing: .01em;
}

.material-flow-heading-note {
  max-width: 360px;
  margin: 0;
  color: var(--materials-muted);
  font-size: 12px;
  line-height: 1.5;
  text-align: right;
}

.material-flow-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.material-flow-item {
  position: relative;
  min-width: 0;
}

.material-flow-item:not(:last-child)::after {
  content: none;
}

.material-flow-card {
  box-sizing: border-box;
  height: 100%;
  min-width: 0;
  padding: 8px 14px 8px 0;
  color: var(--materials-ink);
  border-right: 1px solid var(--materials-line);
}

.material-flow-item:last-child .material-flow-card { border-right: 0; }

.material-flow-label {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  min-width: 0;
  color: var(--materials-ink);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .03em;
}

.material-flow-index {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: 24px;
  height: 24px;
  color: var(--materials-indigo);
  background: #edf5f0;
  border-radius: 4px;
  font-family: inherit;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  letter-spacing: .08em;
}

.material-flow-card h3 {
  margin: 14px 0 7px;
  color: var(--materials-ink);
  font-size: 15px;
  line-height: 1.35;
}

.material-flow-action,
.material-flow-boundary {
  overflow-wrap: anywhere;
}

.material-flow-action {
  min-height: 40px;
  margin: 0;
  color: var(--materials-muted);
  font-size: 13px;
  line-height: 1.65;
}

.material-flow-action strong,
.material-flow-boundary strong {
  margin-right: 4px;
  color: var(--materials-ink);
  font-size: 12px;
  font-weight: 700;
}

.material-flow-state {
  display: flex;
  align-items: baseline;
  min-width: 0;
  min-height: 18px;
  margin: 12px 0 0;
  color: var(--materials-ink);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.material-flow-state.is-ready { color: var(--materials-indigo); }
.material-flow-state.is-review { color: var(--materials-amber-text); }
.material-flow-state.is-failed { color: var(--materials-coral); }
.material-flow-state.is-unknown { color: var(--materials-muted); }

.material-flow-statuses {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  margin-top: 8px;
}

.material-flow-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 3px 7px;
  color: var(--materials-ink);
  border: 1px solid rgba(30, 42, 68, .22);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.35;
}

.material-flow-status strong { font-variant-numeric: tabular-nums; }
.material-flow-status.is-ready { color: var(--materials-indigo); border-color: color-mix(in srgb, var(--ledger-indigo) 38%, transparent); }
.material-flow-status.is-review { color: var(--materials-amber-text); border-color: rgba(201, 130, 46, .46); }
.material-flow-status.is-confirmed { color: var(--materials-ink); border-color: rgba(30, 42, 68, .32); }
.material-flow-status.is-failed { color: var(--materials-coral); border-color: rgba(201, 76, 76, .42); }
.material-flow-status.is-unknown { color: var(--materials-muted); border-color: rgba(102, 112, 133, .38); }

.material-flow-boundary {
  min-height: 37px;
  margin: 12px 0 0;
  padding-top: 10px;
  color: var(--materials-muted);
  border-top: 1px solid var(--materials-line);
  font-size: 13px;
  line-height: 1.55;
}

.material-toolbar-heading {
  min-width: 0;
}

.material-toolbar-heading h2 {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
}

.material-toolbar-heading p {
  margin: 6px 0 0;
  color: var(--materials-muted);
  font-size: 13px;
  line-height: 1.45;
}

.material-toolbar-filter-label {
  align-self: center;
  flex: 0 0 auto;
  color: var(--materials-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .03em;
}

.material-filter-controls {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  margin-top: 13px;
}

.material-filter-controls label {
  display: grid;
  gap: 5px;
  min-width: 0;
  color: var(--materials-muted);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
}

.material-filter-controls :deep(.el-input),
.material-filter-controls :deep(.el-select) {
  min-width: 0;
  width: 100%;
}

.material-filter-controls :deep(.el-input__wrapper),
.material-filter-controls :deep(.el-select__wrapper) { min-height: 44px; }

.material-filter-controls :deep(.el-input__wrapper:focus-within),
.material-filter-controls :deep(.el-select__wrapper:focus-within) {
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--ledger-indigo) 28%, transparent);
}

.material-table-course {
  min-width: 0;
  overflow-wrap: anywhere;
}

.material-table-name,
.material-table-meta,
.material-table-course {
  white-space: normal;
  overflow-wrap: anywhere;
}

.material-table-meta { font-size: 12px; }

@media (max-width: 680px) {
  .material-inbox-search {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
  }

  .material-search-count { grid-column: 1 / -1; }

  .material-inbox-search :deep(.el-input) {
    flex-basis: auto;
    width: 100%;
  }

  .material-load-error,
  .material-deep-link {
    align-items: stretch;
    flex-direction: column;
  }

  .material-load-error :deep(.el-button),
  .material-deep-link :deep(.el-button) { width: 100%; }

  .material-flow-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .material-flow-heading-note {
    max-width: none;
    text-align: left;
  }

  .material-flow-list {
    grid-template-columns: minmax(0, 1fr);
  }

  .material-flow-item:not(:last-child)::after {
    display: none;
  }

  .material-flow-card {
    padding: 12px 0;
    border-right: 0;
    border-bottom: 1px solid var(--materials-line);
  }

  .material-flow-item:last-child .material-flow-card { border-bottom: 0; }
  .material-flow-toggle { line-height: 1.6; padding: 8px 0; }
  .material-flow-toggle span + span { display: block; margin: 2px 0 0 16px; }

  .material-filters {
    align-items: stretch;
    gap: 8px;
  }

  .material-toolbar-filter-label {
    width: 100%;
  }

  .material-filter-controls {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
    gap: 8px;
  }

  .material-filter-controls :deep(.el-input),
  .material-filter-controls :deep(.el-select) {
    width: 100% !important;
    flex: 1 1 auto;
  }
}

</style>
