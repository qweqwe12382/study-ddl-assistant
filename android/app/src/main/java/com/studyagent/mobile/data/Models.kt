package com.studyagent.mobile.data

import org.json.JSONArray
import org.json.JSONObject

data class UserProfile(
    val id: String,
    val email: String,
    val displayName: String,
)

data class TaskItem(
    val id: Int,
    val navigationKey: String?,
    val revision: Int,
    val name: String,
    val dueAt: String?,
    val status: String,
    val priority: Int,
    val estimatedMinutes: Int?,
    val courseName: String?,
)

data class ClassSession(
    val id: Int,
    val weekday: Int,
    val startTime: String,
    val endTime: String,
    val location: String?,
    val startWeek: Int,
    val endWeek: Int,
    val weekPattern: String,
    val courseName: String,
    val courseColor: String?,
    val teacher: String?,
)

data class ExamItem(
    val id: Int,
    val title: String,
    val examType: String,
    val startsAt: String,
    val endsAt: String?,
    val location: String?,
    val seatNumber: String?,
    val courseName: String,
)

data class AcademicOverview(
    val week: Int,
    val classSessions: List<ClassSession>,
    val exams: List<ExamItem>,
)

data class Dashboard(
    val activeTaskCount: Int,
    val dueSoonCount: Int,
    val overdueCount: Int,
    val completedTaskCount: Int,
    val materialsCount: Int,
    val nextAction: String?,
    val upcomingTasks: List<TaskItem>,
    val overdueTasks: List<TaskItem>,
)

internal fun JSONObject.stringOrNull(key: String): String? =
    if (isNull(key)) null else optString(key).takeIf { it.isNotBlank() }

internal fun JSONArray.objects(): List<JSONObject> = buildList {
    for (index in 0 until length()) {
        optJSONObject(index)?.let(::add)
    }
}

internal fun JSONObject.toUserProfile() = UserProfile(
    id = getString("id"),
    email = getString("email"),
    displayName = getString("display_name"),
)

internal fun JSONObject.toTaskItem() = TaskItem(
    id = getInt("id"),
    navigationKey = stringOrNull("navigation_key"),
    revision = optInt("revision", 1),
    name = getString("name"),
    dueAt = stringOrNull("due_at"),
    status = optString("status", "not_started"),
    priority = optInt("priority", 3),
    estimatedMinutes = if (isNull("estimated_minutes")) null else optInt("estimated_minutes"),
    courseName = stringOrNull("course_name"),
)

internal fun JSONObject.toClassSession() = ClassSession(
    id = getInt("id"),
    weekday = getInt("weekday"),
    startTime = getString("start_time"),
    endTime = getString("end_time"),
    location = stringOrNull("location"),
    startWeek = getInt("start_week"),
    endWeek = getInt("end_week"),
    weekPattern = optString("week_pattern", "all"),
    courseName = getString("course_name"),
    courseColor = stringOrNull("course_color"),
    teacher = stringOrNull("teacher"),
)

internal fun JSONObject.toExamItem() = ExamItem(
    id = getInt("id"),
    title = getString("title"),
    examType = optString("exam_type", "other"),
    startsAt = getString("starts_at"),
    endsAt = stringOrNull("ends_at"),
    location = stringOrNull("location"),
    seatNumber = stringOrNull("seat_number"),
    courseName = getString("course_name"),
)

internal fun JSONObject.toAcademicOverview() = AcademicOverview(
    week = getInt("week"),
    classSessions = getJSONArray("class_sessions").objects().map(JSONObject::toClassSession),
    exams = getJSONArray("exams").objects().map(JSONObject::toExamItem),
)

internal fun JSONObject.toDashboard() = Dashboard(
    activeTaskCount = optInt("active_task_count"),
    dueSoonCount = optInt("due_soon_count"),
    overdueCount = optInt("overdue_count"),
    completedTaskCount = optInt("completed_task_count"),
    materialsCount = optInt("materials_count"),
    nextAction = stringOrNull("next_action"),
    upcomingTasks = getJSONArray("upcoming_tasks").objects().map(JSONObject::toTaskItem),
    overdueTasks = getJSONArray("overdue_tasks").objects().map(JSONObject::toTaskItem),
)
