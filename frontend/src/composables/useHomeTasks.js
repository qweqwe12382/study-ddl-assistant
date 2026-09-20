import { ref } from 'vue'
import { coursesApi, tasksApi } from '../api'
import { editBaseline, editRequestConfig } from '../utils/editPrecondition'

export function useHomeTasks() {
  const tasks = ref([])
  const courses = ref([])
  const state = ref('loading')
  const message = ref('')
  const error = ref('')
  const completing = ref(false)
  let requestId = 0

  async function load() {
    const request = ++requestId
    state.value = 'loading'
    const [taskResult, courseResult] = await Promise.allSettled([tasksApi.list(), coursesApi.list()])
    if (request !== requestId) return
    courses.value = courseResult.status === 'fulfilled' && Array.isArray(courseResult.value) ? courseResult.value : []
    if (taskResult.status === 'fulfilled' && Array.isArray(taskResult.value)) {
      tasks.value = taskResult.value
      state.value = 'ready'
    } else {
      tasks.value = []
      state.value = 'error'
      error.value = '任务暂时无法读取，请重试。仍可先记下新任务。'
    }
  }

  async function complete(task) {
    if (completing.value) return false
    const config = editRequestConfig(editBaseline(task))
    error.value = ''
    message.value = ''
    if (!config) { error.value = '任务信息已变化，请刷新后重试。'; return false }
    completing.value = true
    try {
      const updated = await tasksApi.complete(task.id, config)
      if (updated?.id !== task.id || updated?.navigation_key !== task.navigation_key || updated?.status !== 'completed') throw new Error('完成状态尚未确认，请刷新任务列表查看。')
      tasks.value = tasks.value.map(item => item.id === task.id ? updated : item)
      message.value = `已完成「${task.name}」`
      return true
    } catch (err) {
      error.value = err?.code === 'EDIT_CONFLICT' || err?.status === 404
        ? '这项任务已在其他页面变更，本次未修改。请刷新后再试。'
        : err?.message || '未能完成，请重试。'
      return false
    } finally { completing.value = false }
  }

  async function retry() { error.value = ''; await load() }
  return { tasks, courses, state, message, error, completing, load, complete, retry }
}
