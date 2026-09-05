import { navigationKey } from './materialSourceNavigation.js'

function positiveRevision(value) {
  return Number.isSafeInteger(value) && value >= 1 ? value : null
}

export function editBaseline(entity) {
  const id = Number.isSafeInteger(entity?.id) && entity.id > 0 ? entity.id : null
  const key = navigationKey(entity?.navigation_key)
  const revision = positiveRevision(entity?.revision)
  return id !== null && key && revision !== null ? { id, navigation_key: key, revision } : null
}

export function editRequestConfig(baseline) {
  const safe = editBaseline(baseline)
  if (!safe) return null
  return { headers: { 'If-Match': `"${safe.navigation_key}:${safe.revision}"` } }
}

export function isEditConflict(error) {
  return error?.code === 'EDIT_CONFLICT'
}

export function isEntityGone(error, entityErrorCode) {
  return error?.status === 404 && error?.code === entityErrorCode
}

export function extractionPreviewBaseline(material, result) {
  const opened = editBaseline(material)
  const resultId = Number.isSafeInteger(result?.material_id) && result.material_id > 0 ? result.material_id : null
  const resultKey = navigationKey(result?.material_navigation_key)
  const resultRevision = positiveRevision(result?.material_revision)
  if (!opened || resultId !== opened.id || resultKey !== opened.navigation_key || resultRevision === null) return null
  return { id: resultId, navigation_key: resultKey, revision: resultRevision }
}

export function preconditionMessage() {
  return '当前内容还没有可确认的版本，请重新打开后再试。'
}
