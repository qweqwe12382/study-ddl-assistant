export function formatDateTime(value) {
  if (!value) return '未设置'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatDate(value) {
  if (!value) return '未设置'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' }).format(date)
}

export function toDateInputValue(value = new Date()) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) return ''
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function isOverdue(task) {
  return task.status !== 'completed' && task.due_at && new Date(task.due_at).getTime() < Date.now()
}

export function statusLabel(status) {
  return {
    not_started: '未开始',
    in_progress: '进行中',
    completed: '已完成',
    overdue: '已逾期',
  }[status] || status
}

export function statusType(status) {
  return {
    not_started: 'info',
    in_progress: 'warning',
    completed: 'success',
    overdue: 'danger',
  }[status] || 'info'
}
