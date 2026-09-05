/** Semester week arithmetic for the schedule page. */

const MIN_WEEK = 1
const MAX_WEEK = 30
const DAY_MS = 24 * 60 * 60 * 1000

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function toLocalDateOnly(value) {
  if (value instanceof Date) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate())
  }
  if (typeof value === 'string' && DATE_PATTERN.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day)
  }
  return null
}

/**
 * Current semester week (1-30) given the first day of week 1, or null when the
 * date is invalid or the day falls outside the 30-week semester window.
 * `startDate` follows the calendar adapter's contract: the Monday of week 1;
 * a mid-week start simply makes that partial week week 1.
 */
export function computeCurrentWeek(startDate, today = new Date()) {
  const start = toLocalDateOnly(startDate)
  const today0 = toLocalDateOnly(today)
  if (!start || !today0 || Number.isNaN(start.getTime()) || Number.isNaN(today0.getTime())) return null
  const dayDiff = Math.floor((today0.getTime() - start.getTime()) / DAY_MS)
  if (dayDiff < 0) return null
  const week = Math.floor(dayDiff / 7) + 1
  if (week > MAX_WEEK) return null
  return Math.max(MIN_WEEK, week)
}
