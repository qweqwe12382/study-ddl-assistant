package com.studyagent.mobile.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StudyTimeTest {
    @Test
    fun `utc timestamps render in China time`() {
        assertEquals("9月3日 00:30", StudyTime.formatDateTime("2026-09-02T16:30:00Z"))
    }

    @Test
    fun `invalid deadline is handled without crashing`() {
        assertEquals("时间待补充", StudyTime.formatDateTime("not-a-date"))
        assertNull(StudyTime.dateOf(null))
    }
}
