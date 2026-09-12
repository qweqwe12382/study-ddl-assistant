/** Pure helpers for storing a pasted course notification as a text material. */

export const MAX_PASTE_NOTICE_CHARACTERS = 20_000

function localDateTimePart(value) {
  return String(value).padStart(2, '0')
}

/** Shanghai wall-clock datetime input value, deliberately without a timezone suffix. */
export function localReferenceDateTime(value = new Date()) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(value).reduce((result, item) => {
    if (item.type !== 'literal') result[item.type] = item.value
    return result
  }, {})
  return `${parts.year}-${localDateTimePart(parts.month)}-${localDateTimePart(parts.day)}T${localDateTimePart(parts.hour)}:${localDateTimePart(parts.minute)}:${localDateTimePart(parts.second)}`
}

export function pasteNoticeFilename(title) {
  const cleanTitle = typeof title === 'string' ? title.trim().replace(/[\\/:*?"<>|]/g, ' ') : ''
  return `${(cleanTitle || '课程通知').slice(0, 120)}.txt`
}

export function validLocalReferenceDateTime(value) {
  if (typeof value !== 'string') return false
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value)
  if (!match) return false
  const [, yearText, monthText, dayText, hourText, minuteText, secondText = '0'] = match
  const [year, month, day, hour, minute, second] = [yearText, monthText, dayText, hourText, minuteText, secondText].map(Number)
  if (year < 1 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59 || second > 59) return false
  // This is a Shanghai wall-clock value. Validate the calendar directly so
  // DST rules or the computer's local timezone cannot alter the result.
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const daysByMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return day <= daysByMonth[month - 1]
}

/** Validate the student-facing draft before creating the in-memory UTF-8 file. */
export function buildPastedNotice({ title, text, sourceTime }) {
  const content = typeof text === 'string' ? text.trim() : ''
  if (!content) return { error: '请粘贴通知正文' }
  if (content.length > MAX_PASTE_NOTICE_CHARACTERS) return { error: `通知正文不能超过 ${MAX_PASTE_NOTICE_CHARACTERS.toLocaleString('zh-CN')} 字` }
  if (!validLocalReferenceDateTime(sourceTime)) {
    return { error: '请填写通知的参考时间' }
  }
  return {
    filename: pasteNoticeFilename(title),
    content,
    sourceTime,
  }
}
