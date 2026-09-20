import { ElMessage } from 'element-plus'
import http from '../api/http'

export async function downloadFile(url, filename) {
  let objectUrl
  try {
    const content = await http.get(url, { responseType: 'blob' })
    objectUrl = window.URL.createObjectURL(content)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename || new window.URL(url, window.location.href).pathname.split('/').pop() || 'download'
    document.body.appendChild(link)
    link.click()
    link.remove()
    return true
  } catch (error) {
    ElMessage.error(error?.message || '下载失败，请稍后重试。')
    return false
  } finally {
    // Keep the blob alive until the browser has started saving the file.
    if (objectUrl) window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 60000)
  }
}
