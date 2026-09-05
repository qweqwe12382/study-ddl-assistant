import http from './http'

export const healthApi = {
  check: () => http.get('/health'),
}

export const authApi = {
  me: () => http.get('/auth/me'),
  register: (payload) => http.post('/auth/register', payload),
  login: (payload) => http.post('/auth/login', payload),
  demoLogin: () => http.post('/auth/demo-login'),
  logout: () => http.post('/auth/logout'),
}

export const coursesApi = {
  list: () => http.get('/courses'),
  create: (payload) => http.post('/courses', payload),
  update: (id, payload) => http.patch(`/courses/${id}`, payload),
  remove: (id) => http.delete(`/courses/${id}`),
}

export const academicCalendarApi = {
  overview: (week = 1, includePastExams = false) => http.get('/academic-calendar/overview', {
    params: { week, include_past_exams: includePastExams },
  }),
  previewIntegration: (payload) => http.post('/academic-calendar/integrations/preview', payload),
  createNjustCaptcha: () => http.post('/academic-calendar/integrations/njust/captcha', undefined, { timeout: 15000 }),
  previewNjustIntegration: (payload) => http.post('/academic-calendar/integrations/njust/preview', payload, { timeout: 40000 }),
  discardNjustSession: (sessionId) => http.delete(`/academic-calendar/integrations/njust/session/${encodeURIComponent(sessionId)}`),
  syncIntegration: (payload) => http.post('/academic-calendar/integrations/sync', payload),
  createClassSession: (payload) => http.post('/academic-calendar/class-sessions', payload),
  updateClassSession: (id, payload, config) => http.patch(`/academic-calendar/class-sessions/${id}`, payload, config),
  removeClassSession: (id, config) => http.delete(`/academic-calendar/class-sessions/${id}`, config),
  createExam: (payload) => http.post('/academic-calendar/exams', payload),
  updateExam: (id, payload, config) => http.patch(`/academic-calendar/exams/${id}`, payload, config),
  removeExam: (id, config) => http.delete(`/academic-calendar/exams/${id}`, config),
}

export const materialsApi = {
  list: (filters = {}) => {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== ''),
    )
    return http.get('/materials', { params })
  },
  uploadPolicy: () => http.get('/materials/upload-policy'),
  create: (payload) => http.post('/materials', payload),
  upload: (files, courseId = null, materialType = null) => {
    const formData = new window.FormData()
    files.forEach((file) => formData.append('files', file))
    if (courseId) formData.append('course_id', courseId)
    if (materialType) formData.append('material_type', materialType)
    return http.post('/materials/upload', formData)
  },
  retry: (id, config) => http.post(`/materials/${id}/retry`, undefined, config),
  extractionPolicy: () => http.get('/materials/extraction-policy'),
  extract: (id, provider = 'local-rules', config = {}) => http.post(`/materials/${id}/extract`, { provider }, { ...config, timeout: 120000 }),
  extraction: (id) => http.get(`/materials/${id}/extraction`),
  confirmExtraction: (id, payload, config) => http.post(`/materials/${id}/extraction/confirm`, payload, config),
  fileUrl: (id) => `${(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')}/materials/${id}/file`,
  update: (id, payload, config) => http.patch(`/materials/${id}`, payload, config),
  remove: (id, config) => http.delete(`/materials/${id}`, config),
}

export const tasksApi = {
  list: () => http.get('/tasks'),
  create: (payload) => http.post('/tasks', payload),
  update: (id, payload, config) => http.patch(`/tasks/${id}`, payload, config),
  complete: (id, config) => http.post(`/tasks/${id}/complete`, undefined, config),
  remove: (id, config) => http.delete(`/tasks/${id}`, config),
}

export const dashboardApi = {
  get: () => http.get('/dashboard'),
}

export const agentApi = {
  refresh: () => http.post('/agent/refresh'),
  briefing: () => http.get('/agent/briefing'),
  // M8.5 keeps the review data read-only and optional.  The dashboard first
  // consumes the unified briefing; this endpoint lets a newer backend expose
  // the same contract without making the existing page depend on it.
  weeklyReview: () => http.get('/agent/weekly-review'),
  learningTrends: () => http.get('/agent/learning-trends'),
  learningRhythmHistory: () => http.get('/agent/learning-rhythm-history'),
  // The activity feed is a read-only, optional view. Keep its endpoint
  // centralized here so a backend contract change does not spread through
  // the dashboard component.
  activity: (params = {}) => http.get('/agent/activity', { params }),
  // M8.6 reads only persisted snapshots; an unavailable/empty response is
  // rendered as "no history" rather than reconstructed in the browser.
  weeklyReviewHistory: (params = {}) => http.get('/agent/weekly-reviews', { params }),
  // Navigation targets are resolved by the server from typed source refs. The
  // client never turns an arbitrary source id into a route on its own.
  resolveSourceRefs: (sourceRefs) => http.post('/agent/source-navigation/resolve', { source_refs: sourceRefs }),
  reminderPreferences: () => http.get('/agent/reminder-preferences'),
  updateReminderPreferences: (payload) => http.patch('/agent/reminder-preferences', payload),
  capacity: () => http.get('/agent/capacity'),
  completeTask: (taskId, payload = {}, config) => http.post(`/agent/tasks/${encodeURIComponent(taskId)}/complete`, payload, config),
  calibration: (courseId = null) => {
    const params = {}
    if (courseId !== null && courseId !== undefined && courseId !== '') params.course_id = courseId
    return http.get('/agent/calibration', { params })
  },
  resetCalibration: (courseId, payload = {}) => http.post(`/agent/calibration/${encodeURIComponent(courseId)}/reset`, payload),
  planDeltas: () => http.get('/agent/plan-deltas'),
  acceptPlanDelta: (suggestionId, payload = {}) => http.post(`/agent/plan-deltas/${encodeURIComponent(suggestionId)}/accept`, payload),
  accept: (id, payload) => http.post(`/agent/suggestions/${encodeURIComponent(id)}/accept`, payload),
  dismiss: (id, payload = {}) => http.post(`/agent/suggestions/${encodeURIComponent(id)}/dismiss`, payload),
  dismissReminder: (id, payload = {}) => http.post(`/agent/reminders/${encodeURIComponent(id)}/dismiss`, payload),
}

export const studyPreferencesApi = {
  get: () => http.get('/study-preferences'),
  update: (payload) => http.put('/study-preferences', payload),
  reset: () => http.post('/study-preferences/reset'),
}

export const studyPlansApi = {
  list: (courseId = null, includeArchived = false) => {
    const params = {}
    if (courseId) params.course_id = courseId
    if (includeArchived) params.include_archived = true
    return http.get('/study-plans', { params })
  },
  get: (id) => http.get(`/study-plans/${id}`),
  generate: (payload) => http.post('/study-plans/generate', payload),
  update: (id, payload, config) => http.patch(`/study-plans/${id}`, payload, config),
  archive: (id, config) => http.post(`/study-plans/${id}/archive`, undefined, config),
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

export const exportsApi = {
  tasksCsvUrl: () => `${apiBaseUrl}/exports/tasks.csv`,
  tasksCalendarUrl: () => `${apiBaseUrl}/exports/tasks.ics`,
  materialsMarkdownUrl: () => `${apiBaseUrl}/exports/materials.md`,
  studyPlanMarkdownUrl: (id) => `${apiBaseUrl}/exports/study-plans/${id}.md`,
}

export const resetApi = {
  all: () => http.post('/dev/reset'),
}

export const settingsApi = {
  getLlm: () => http.get('/settings/llm'),
  updateLlm: (payload) => http.put('/settings/llm', payload),
}
