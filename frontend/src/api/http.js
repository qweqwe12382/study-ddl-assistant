import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  if (typeof window !== 'undefined' && config.data instanceof window.FormData && config.headers) {
    // Let the browser add the multipart boundary. Keeping the JSON header here
    // makes FastAPI treat the upload body as an invalid request.
    if (typeof config.headers.delete === 'function') config.headers.delete('Content-Type')
    else delete config.headers['Content-Type']
  }
  return config
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const validationDetails = error.response?.data?.error?.details
    const detailMessage = Array.isArray(validationDetails)
      ? validationDetails.map((item) => `${item.loc?.at(-1) || '字段'}：${item.msg}`).join('；')
      : ''
    const message =
      detailMessage || error.response?.data?.error?.message || error.response?.data?.detail || '请求失败，请检查后端服务'
    return Promise.reject(new Error(message))
  },
)

export default http
