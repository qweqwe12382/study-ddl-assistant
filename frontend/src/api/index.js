import http from './http'

export const healthApi = {
  check: () => http.get('/health'),
}

export const coursesApi = {
  list: () => http.get('/courses'),
  create: (payload) => http.post('/courses', payload),
  update: (id, payload) => http.patch(`/courses/${id}`, payload),
  remove: (id) => http.delete(`/courses/${id}`),
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
  retry: (id) => http.post(`/materials/${id}/retry`),
  extract: (id) => http.post(`/materials/${id}/extract`),
  extraction: (id) => http.get(`/materials/${id}/extraction`),
  confirmExtraction: (id, payload) => http.post(`/materials/${id}/extraction/confirm`, payload),
  fileUrl: (id) => `${(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')}/materials/${id}/file`,
  update: (id, payload) => http.patch(`/materials/${id}`, payload),
  remove: (id) => http.delete(`/materials/${id}`),
}

export const tasksApi = {
  list: () => http.get('/tasks'),
  create: (payload) => http.post('/tasks', payload),
  update: (id, payload) => http.patch(`/tasks/${id}`, payload),
  complete: (id) => http.post(`/tasks/${id}/complete`),
  remove: (id) => http.delete(`/tasks/${id}`),
}

export const dashboardApi = {
  get: () => http.get('/dashboard'),
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
  update: (id, payload) => http.patch(`/study-plans/${id}`, payload),
  archive: (id) => http.post(`/study-plans/${id}/archive`),
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
