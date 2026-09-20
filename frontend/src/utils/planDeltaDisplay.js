const planFieldLabels = Object.freeze({
  id: '计划项 ID',
  title: '标题',
  date: '日期',
  content: '内容',
  minutes: '时长',
  status: '状态',
  source_task_ids: '关联任务 ID',
  source_material_ids: '关联资料 ID',
  exam_date: '考试日期',
  daily_minutes: '每日学习时间',
  total_minutes: '计划总时长',
  completed_minutes: '已完成时长',
  item_count: '学习单元数',
  items: '学习单元',
  task_count: '关联任务数',
  material_count: '关联资料数',
})

function objectOrEmpty(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function listValue(value) {
  return Array.isArray(value) ? value : []
}

function readableValue(value) {
  if (value === null || value === undefined || value === '') return '未设置'
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : ''
}

function readableIds(value) {
  if (!Array.isArray(value)) return ''
  const ids = value
    .filter((item) => typeof item === 'string' || typeof item === 'number')
    .map((item) => String(item))
  return ids.length ? ids.join('、') : '无'
}

export function planFieldLabel(key) {
  return planFieldLabels[key] || key
}

export function planValueLabel(value, key = '') {
  if (key === 'source_task_ids' || key === 'source_material_ids') return readableIds(value) || '未设置'
  if (key.endsWith('_minutes') || key === 'daily_minutes' || key === 'minutes') {
    const readable = readableValue(value)
    return readable === '未设置' ? readable : `${readable} 分钟`
  }
  if (Array.isArray(value)) return `${value.length} 项`
  return readableValue(value) || '已更新'
}

export function planItemLines(value, itemId) {
  const data = objectOrEmpty(value)
  const lines = []
  const resolvedId = itemId ?? data.id
  const id = readableValue(resolvedId)
  if (id && id !== '未设置') lines.push(`${planFieldLabel('id')}：${id}`)

  for (const key of ['title', 'date', 'content', 'minutes', 'status', 'source_task_ids', 'source_material_ids']) {
    if (!Object.prototype.hasOwnProperty.call(data, key)) continue
    const label = planValueLabel(data[key], key)
    if (label) lines.push(`${planFieldLabel(key)}：${label}`)
  }
  return lines.length ? lines : ['计划项内容待确认']
}

export function planStateLines(value) {
  if (value === null || value === undefined || value === '') return []
  if (typeof value === 'string' || typeof value === 'number') return [String(value)]
  if (Array.isArray(value)) return value.flatMap((item) => planItemLines(item))

  const data = objectOrEmpty(value)
  if (Array.isArray(data.items)) return data.items.flatMap((item) => planItemLines(item))
  return Object.entries(data)
    .filter(([key]) => !['navigation_key', 'source_task_refs', 'source_material_refs'].includes(key))
    .flatMap(([key, item]) => {
      if (typeof item === 'object' && item !== null && !Array.isArray(item)) return []
      return [`${planFieldLabel(key)}：${planValueLabel(item, key)}`]
    })
}

export function normalizePlanDeltaLines(item) {
  const data = objectOrEmpty(item)
  const currentPayload = objectOrEmpty(data.current_payload)
  const proposedPayload = objectOrEmpty(data.proposed_payload)
  const changes = listValue(data.changes || data.diff || data.plan_changes || proposedPayload.changes)
  if (changes.length) {
    const before = []
    const after = []
    for (const change of changes) {
      const current = objectOrEmpty(change)
      const itemId = current.item_id
      before.push(...planItemLines(current.before ?? current.current ?? current.from, itemId))
      after.push(...planItemLines(current.after ?? current.proposed ?? current.to, itemId))
    }
    return { before, after }
  }
  return {
    before: planStateLines(data.before || data.current || data.current_plan || data.before_plan || currentPayload),
    after: planStateLines(data.after || data.proposed || data.proposed_plan || data.after_plan || proposedPayload),
  }
}
