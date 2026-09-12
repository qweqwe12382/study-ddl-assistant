package com.studyagent.mobile.util

import com.studyagent.mobile.data.TaskItem
import java.lang.Math.addExact

/**
 * A deadline marker prepared for a calendar editor. It is deliberately not a calendar record:
 * the user still reviews reminders and saves it in their chosen calendar app.
 */
data class DeadlineCalendarEvent(
    val title: String,
    val beginMillis: Long,
    val endMillis: Long,
)

object DeadlineCalendarEventFactory {
    const val deadlineMarkerDurationMillis = 60_000L

    fun from(task: TaskItem): DeadlineCalendarEvent? {
        val beginMillis = StudyTime.epochMillis(task.dueAt) ?: return null
        val endMillis = runCatching { addExact(beginMillis, deadlineMarkerDurationMillis) }.getOrNull() ?: return null
        val taskName = task.name.trim().ifBlank { "学习任务截止" }
        val courseName = task.courseName?.trim()?.takeIf { it.isNotBlank() }
        val title = courseName?.let { "$it · $taskName" } ?: taskName

        // Calendar events need an end. One minute marks a point-in-time deadline without
        // turning estimated work time into a fabricated calendar duration.
        return DeadlineCalendarEvent(title, beginMillis, endMillis)
    }
}
