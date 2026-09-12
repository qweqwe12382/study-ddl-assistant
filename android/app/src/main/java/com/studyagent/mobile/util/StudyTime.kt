package com.studyagent.mobile.util

import java.time.Duration
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

object StudyTime {
    val chinaZone: ZoneId = ZoneId.of("Asia/Shanghai")
    private val dateTimeFormatter = DateTimeFormatter.ofPattern("M月d日 HH:mm", Locale.CHINA)
    private val shortDateFormatter = DateTimeFormatter.ofPattern("M月d日", Locale.CHINA)

    fun today(): LocalDate = LocalDate.now(chinaZone)

    fun weekday(): Int = today().dayOfWeek.value

    fun formatDateTime(value: String?): String =
        parse(value)?.format(dateTimeFormatter) ?: "时间待补充"

    fun formatDate(value: String?): String =
        parse(value)?.format(shortDateFormatter) ?: "日期待补充"

    fun dateOf(value: String?): LocalDate? = parse(value)?.toLocalDate()

    /**
     * Returns the absolute instant represented by an API deadline. Formatting continues to use
     * China time, while consumers such as Calendar receive the same instant in milliseconds.
     */
    fun epochMillis(value: String?): Long? = parse(value)?.let { timestamp ->
        runCatching { timestamp.toInstant().toEpochMilli() }.getOrNull()
    }

    fun countdown(value: String?): String {
        val target = parse(value) ?: return "时间待补充"
        val now = OffsetDateTime.now(chinaZone)
        val minutes = Duration.between(now, target).toMinutes()
        return when {
            minutes < 0 -> "已到期"
            minutes < 60 -> "$minutes 分钟后"
            minutes < 24 * 60 -> "${minutes / 60} 小时后"
            else -> "${minutes / (24 * 60)} 天后"
        }
    }

    private fun parse(value: String?): OffsetDateTime? {
        if (value.isNullOrBlank()) return null
        return try {
            OffsetDateTime.parse(value).atZoneSameInstant(chinaZone).toOffsetDateTime()
        } catch (_: DateTimeParseException) {
            null
        }
    }
}
