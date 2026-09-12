package com.studyagent.mobile.util

import com.studyagent.mobile.data.TaskItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DeadlineCalendarEventTest {
    @Test
    fun `calendar marker uses the deadline instant and never estimated study duration`() {
        val task = task(
            dueAt = "2026-09-02T16:30:00Z",
            estimatedMinutes = 180,
            courseName = "高等数学",
        )

        val event = requireNotNull(DeadlineCalendarEventFactory.from(task))

        assertEquals("高等数学 · 完成第三章习题", event.title)
        assertEquals(1788366600000L, event.beginMillis)
        assertEquals(60_000L, event.endMillis - event.beginMillis)
    }

    @Test
    fun `missing blank and malformed deadlines do not create calendar events`() {
        listOf(null, "", "   ", "not-a-date", "2026-09-02").forEach { dueAt ->
            assertNull("dueAt=$dueAt", DeadlineCalendarEventFactory.from(task(dueAt = dueAt)))
        }
    }

    @Test
    fun `blank course and title fall back to a useful calendar title`() {
        val event = requireNotNull(
            DeadlineCalendarEventFactory.from(task(dueAt = "2026-09-02T16:30:00Z", name = "  ", courseName = " ")),
        )

        assertEquals("学习任务截止", event.title)
    }

    private fun task(
        dueAt: String?,
        estimatedMinutes: Int? = null,
        name: String = "完成第三章习题",
        courseName: String? = null,
    ) = TaskItem(
        id = 1,
        navigationKey = null,
        revision = 1,
        name = name,
        dueAt = dueAt,
        status = "not_started",
        priority = 3,
        estimatedMinutes = estimatedMinutes,
        courseName = courseName,
    )
}
