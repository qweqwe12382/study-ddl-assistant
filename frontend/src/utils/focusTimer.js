/** Pure helpers for the focus timer page. */

export const FOCUS_PRESET_MINUTES = [15, 25, 45]

const MIN_RECORDABLE_MINUTES = 15
const MAX_ACTUAL_MINUTES = 10080

export const CUSTOM_MINUTES_MIN = 15
export const CUSTOM_MINUTES_MAX = 240

/** Measure active time from a clock, independent of delayed render callbacks. */
export function activeElapsedSeconds(accumulatedSeconds, startedAtMs, nowMs, targetSeconds) {
  const elapsed = Math.max(0, accumulatedSeconds) + Math.max(0, nowMs - startedAtMs) / 1000
  return Math.min(Math.max(0, targetSeconds), elapsed)
}

/** Clamp a custom focus duration to the supported 15-240 range, or null. */
export function normalizeCustomMinutes(value) {
  const parsed = typeof value === 'number' ? Math.floor(value) : Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed < CUSTOM_MINUTES_MIN || parsed > CUSTOM_MINUTES_MAX) return null
  return parsed
}

export function formatClock(totalSeconds) {
  const safe = Number.isFinite(totalSeconds) && totalSeconds > 0 ? Math.floor(totalSeconds) : 0
  const minutes = Math.floor(safe / 60)
  const seconds = safe % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

/** Whole minutes elapsed in the current focus session. */
export function sessionMinutes(elapsedSeconds) {
  const safe = Number.isFinite(elapsedSeconds) && elapsedSeconds > 0 ? Math.floor(elapsedSeconds) : 0
  return Math.floor(safe / 60)
}

/** The API accepts actual minutes of at least 15; shorter sessions are not recordable. */
export function isRecordable(elapsedSeconds) {
  return sessionMinutes(elapsedSeconds) >= MIN_RECORDABLE_MINUTES
}

/** Total actual minutes after merging one more focus session into the task record. */
export function mergeActualMinutes(existingMinutes, sessionMinutesValue) {
  const existing = Number.isFinite(existingMinutes) && existingMinutes > 0 ? Math.floor(existingMinutes) : 0
  const session = Number.isFinite(sessionMinutesValue) && sessionMinutesValue > 0 ? Math.floor(sessionMinutesValue) : 0
  return Math.min(existing + session, MAX_ACTUAL_MINUTES)
}

/** Label used on the record actions, e.g. "完成并记录 25 分钟". */
export function recordLabel(minutes) {
  return `${Math.floor(Number.isFinite(minutes) && minutes > 0 ? minutes : 0)} 分钟`
}
