import axios from 'axios'
import { resolveApiBaseUrl } from '../utils/apiBaseUrl'

const http = axios.create({
  baseURL: resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL, window.location.hostname, import.meta.env.DEV),
  timeout: 10000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

function readCookie(name) {
  if (typeof document === 'undefined') return ''
  const prefix = `${encodeURIComponent(name)}=`
  const entry = document.cookie.split('; ').find((item) => item.startsWith(prefix))
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : ''
}

http.interceptors.request.use((config) => {
  if (typeof window !== 'undefined' && config.data instanceof window.FormData && config.headers) {
    // Let the browser add the multipart boundary. Keeping the JSON header here
    // makes FastAPI treat the upload body as an invalid request.
    if (typeof config.headers.delete === 'function') config.headers.delete('Content-Type')
    else delete config.headers['Content-Type']
  }
  const method = String(config.method || 'get').toLowerCase()
  if (['post', 'put', 'patch', 'delete'].includes(method) && config.headers) {
    const csrfToken = readCookie('study_csrf')
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken
  }
  return config
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new Error('请求超时，请稍后重试'))
    }
    if (!error.response) {
      return Promise.reject(new Error('无法连接后端服务，请确认服务已启动'))
    }
    const validationDetails = error.response?.data?.error?.details
    const detailMessage = Array.isArray(validationDetails)
      ? validationDetails.map((item) => `${item.loc?.at(-1) || '字段'}：${item.msg}`).join('；')
      : ''
    let message =
      detailMessage || error.response?.data?.error?.message || error.response?.data?.detail || '请求失败，请检查后端服务'
    const requestId = error.response?.headers?.['x-request-id']
    if (requestId && error.response.status >= 500) message += `（请求 ID：${requestId}）`
    const apiError = new Error(message)
    apiError.code = error.response?.data?.error?.code || error.code
    apiError.status = error.response.status
    if (apiError.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new window.CustomEvent('study-auth-expired'))
    }
    return Promise.reject(apiError)
  },
)

export default http
