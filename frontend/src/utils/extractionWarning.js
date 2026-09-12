const warningLabels = Object.freeze({
  AMBIGUOUS_TASK_ASSOCIATION: '原文可能对应多个任务，请核对原文',
  AMBIGUOUS_TASK_DATE: '截止日期有歧义，请核对原文',
  CONDITIONAL_AUDIENCE: '可能只适用于部分同学，请核对原文',
  DATE_CONFLICT_WITH_SOURCE: '识别日期与原文不一致，请核对原文',
  DATE_IN_PAST: '识别到的日期已过去，请核对原文',
  DATE_UPDATED_FROM_SOURCE: '原文有改期，请核对新日期',
  DATE_YEAR_INFERRED: '原文未写年份，请核对原文',
  DEADLINE_PENDING: '截止时间尚未确定，请核对原文',
  INVALID_DATE: '日期格式不明确，请核对原文',
  INVALID_TIME: '时间格式不明确，请核对原文',
  LOW_CONFIDENCE: '识别把握较低，请核对原文',
  MISSING_DUE_DATE: '未识别到截止时间，可核对后补充',
  MULTIPLE_DATES_IN_SOURCE: '原文出现多个日期，请确认对应截止时间',
  NO_TASK_CANDIDATE: '原文含日期但未识别到明确任务，请核对原文',
  SOURCE_QUOTE_NOT_FOUND: '未能在原文中找到这段依据，请核对原文',
  TIME_DEFAULTED_TO_END_OF_DAY: '原文未写具体时间，暂按当天结束处理，请核对原文',
  VAGUE_DUE_DATE: '截止日期描述不明确，请核对原文',
})

export function extractionWarningLabel(value) {
  const code = typeof value === 'string' ? value.trim() : ''
  return Object.hasOwn(warningLabels, code) ? warningLabels[code] : '请核对原文'
}
