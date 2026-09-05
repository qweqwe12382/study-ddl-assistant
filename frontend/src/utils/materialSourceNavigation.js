function plainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

function cleanText(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

const NAVIGATION_KEY = /^[a-f0-9]{32}$/
const KEYED_SOURCE_TYPES = new Set(['task', 'material', 'study_plan', 'study_plan_item', 'action_receipt'])
const FIXED_COLLECTION_TARGETS = Object.freeze({
  'task_collection:weekly_overdue': { path: '/tasks', query: { view: 'weekly_overdue' } },
  'task_collection:weekly_estimate_variance': { path: '/tasks', query: { view: 'weekly_estimate_variance' } },
  'material_collection:current_inbox': { path: '/materials', query: { view: 'current_inbox' } },
  'material_collection:failed_materials': { path: '/materials', query: { view: 'failed_materials' } },
  'material_collection:review_materials': { path: '/materials', query: { view: 'review_materials' } },
  'study_plan_collection:weekly_plan_delays': { path: '/study-plans', query: { view: 'weekly_plan_delays' } },
  'capacity:next_7_days': { path: '/tasks', query: { view: 'capacity_next_7_days' } },
})

export function navigationKey(value) {
  return typeof value === 'string' && NAVIGATION_KEY.test(value) ? value : null
}

export function sourceRefRequiresNavigationKey(sourceType) {
  return KEYED_SOURCE_TYPES.has(cleanText(sourceType)?.toLowerCase())
}

export function normalizedNavigationSourceRef(ref) {
  if (!plainObject(ref)) return null
  const sourceType = cleanText(ref.source_type || ref.type)?.toLowerCase() || ''
  const rawId = ref.source_id ?? ref.id
  const numericId = positiveMaterialId(rawId)
  const planItemId = typeof rawId === 'string' && /^([1-9][0-9]{0,9}):([^\u0000-\u001f]{1,80})$/.test(rawId) ? rawId : null
  const fixedId = typeof rawId === 'string' && FIXED_COLLECTION_TARGETS[`${sourceType}:${rawId}`] ? rawId : null
  const sourceId = sourceType === 'study_plan_item' ? planItemId : sourceType.endsWith('_collection') || sourceType === 'capacity' ? fixedId : numericId
  const key = navigationKey(ref.navigation_key)
  if (!sourceType || sourceId === null) return null
  if (sourceRefRequiresNavigationKey(sourceType) && !key) return null
  return {
    source_type: sourceType,
    source_id: sourceId,
    ...(key ? { navigation_key: key } : {}),
    ...(cleanText(ref.source_name || ref.name) ? { source_name: cleanText(ref.source_name || ref.name) } : {}),
  }
}

export function navigationSourceCacheKey(ref) {
  const item = normalizedNavigationSourceRef(ref)
  if (!item) return ''
  return `${item.source_type}:${String(item.source_id)}:${item.navigation_key || 'fixed'}`
}

export function positiveMaterialId(value) {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value > 0 && value <= 9_999_999_999 ? value : null
  }
  if (typeof value !== 'string' || !/^[1-9][0-9]{0,9}$/.test(value)) return null
  const id = Number(value)
  return Number.isSafeInteger(id) ? id : null
}

export function dashboardMaterialSourceContext(source) {
  const materialId = positiveMaterialId(source?.material_id)
  const noMaterialId = source?.material_id === null
  const materialName = cleanText(source?.material_name)
  const sourceAvailable = source?.source_available
  const key = navigationKey(source?.material_navigation_key)

  if (materialId !== null && sourceAvailable === true && materialName && key) {
    return {
      state: 'available',
      materialId,
      navigationKey: key,
      title: '已关联资料',
      label: materialName,
      detail: '这份资料当前可打开。',
    }
  }
  if (noMaterialId && sourceAvailable === false && materialName) {
    return {
      state: 'deleted',
      materialId: null,
      title: '历史来源已删除',
      label: materialName,
      detail: '保留历史名称，当前没有可打开的资料。',
    }
  }
  if (noMaterialId && sourceAvailable === false && !materialName) {
    return {
      state: 'missing',
      materialId: null,
      title: '未关联资料',
      label: null,
      detail: '可在任务中补充关联资料。',
    }
  }
  if (materialId !== null && sourceAvailable === true && materialName && !key) {
    return {
      state: 'identity_missing',
      materialId: null,
      navigationKey: null,
      title: '资料身份待确认',
      label: materialName,
      detail: '暂不能确认来源，请从资料库查看。',
    }
  }
  return {
    state: 'contradictory',
    materialId: null,
    title: '资料状态暂无法确认',
    label: null,
    detail: '不会根据不完整或矛盾的数据提供资料入口。',
  }
}

// The resolver response is untrusted at the UI boundary.  A material source
// may navigate only to its own fixed material detail query, never to a route
// or query assembled from the response.
export function validatedMaterialTarget(response, materialId, requestedNavigationKey) {
  const requestedRef = normalizedNavigationSourceRef({
    source_type: 'material', source_id: materialId, navigation_key: requestedNavigationKey,
  })
  if (!requestedRef) return null
  return validatedSourceNavigationTarget(response, requestedRef)
}

export function validatedSourceNavigationTarget(response, requestedRef) {
  const expected = normalizedNavigationSourceRef(requestedRef)
  if (!expected) return null
  if (!plainObject(response) || !Array.isArray(response.items) || response.items.length !== 1) return null

  const item = response.items[0]
  if (!plainObject(item) || item.available !== true || !plainObject(item.source_ref)) return null
  const returned = normalizedNavigationSourceRef(item.source_ref)
  if (!returned || returned.source_type !== expected.source_type || String(returned.source_id) !== String(expected.source_id)) return null
  if (sourceRefRequiresNavigationKey(expected.source_type) && returned.navigation_key !== expected.navigation_key) return null
  if (!plainObject(item.target) || !plainObject(item.target.query)) return null

  const query = item.target.query
  const queryKeys = Object.keys(query)
  const requestedId = String(expected.source_id)
  if (expected.source_type === 'material') {
    if (item.target.path !== '/materials' || queryKeys.length !== 2 || positiveMaterialId(query.material_id) === null || String(query.material_id) !== requestedId || query.navigation_key !== expected.navigation_key) return null
    return { path: '/materials', query: { material_id: requestedId, navigation_key: query.navigation_key } }
  }
  if (expected.source_type === 'task') {
    if (item.target.path !== '/tasks' || queryKeys.length !== 2 || positiveMaterialId(query.task_id) === null || String(query.task_id) !== requestedId || query.navigation_key !== expected.navigation_key) return null
    return { path: '/tasks', query: { task_id: requestedId, navigation_key: query.navigation_key } }
  }
  if (expected.source_type === 'study_plan') {
    if (item.target.path !== '/study-plans' || queryKeys.length !== 2 || positiveMaterialId(query.plan_id) === null || String(query.plan_id) !== requestedId || query.navigation_key !== expected.navigation_key) return null
    return { path: '/study-plans', query: { plan_id: requestedId, navigation_key: query.navigation_key } }
  }
  if (expected.source_type === 'study_plan_item') {
    const match = /^([1-9][0-9]{0,9}):(.*)$/.exec(requestedId)
    if (!match || !match[2] || item.target.path !== '/study-plans' || queryKeys.length !== 3 || positiveMaterialId(query.plan_id) === null || String(query.plan_id) !== match[1] || query.item_id !== match[2] || query.navigation_key !== expected.navigation_key) return null
    return { path: '/study-plans', query: { plan_id: match[1], item_id: match[2], navigation_key: query.navigation_key } }
  }
  if (expected.source_type === 'action_receipt') {
    if (item.target.path === '/tasks' && queryKeys.length === 2 && positiveMaterialId(query.task_id) !== null && navigationKey(query.navigation_key)) return { path: '/tasks', query: { task_id: String(query.task_id), navigation_key: query.navigation_key } }
    if (item.target.path === '/study-plans' && queryKeys.length === 2 && positiveMaterialId(query.plan_id) !== null && navigationKey(query.navigation_key)) return { path: '/study-plans', query: { plan_id: String(query.plan_id), navigation_key: query.navigation_key } }
  }
  const fixed = FIXED_COLLECTION_TARGETS[`${expected.source_type}:${requestedId}`]
  if (fixed && item.target.path === fixed.path && queryKeys.length === 1 && query.view === fixed.query.view) return fixed
  return null
}
