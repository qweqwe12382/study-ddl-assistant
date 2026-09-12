package com.studyagent.mobile.util

import android.content.Intent
import android.provider.CalendarContract

fun DeadlineCalendarEvent.toCalendarInsertIntent(): Intent = Intent(Intent.ACTION_INSERT)
    .setData(CalendarContract.Events.CONTENT_URI)
    .putExtra(CalendarContract.Events.TITLE, title)
    .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, beginMillis)
    .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, endMillis)
    .putExtra(
        CalendarContract.Events.DESCRIPTION,
        "这是学习任务的截止时间。请检查提醒设置后，再由你保存到系统日历。",
    )
