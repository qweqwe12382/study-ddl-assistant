package com.studyagent.mobile.data

/** Operations needed by the UI, independently of Android preferences and HTTP. */
interface StudyDataSource {
    val savedServer: String
    val savedWeek: Int
    fun configureServer(input: String, allowPrivateHttp: Boolean): String
    fun saveWeek(week: Int)
    suspend fun login(email: String, password: String): UserProfile
    suspend fun dashboard(): Dashboard
    suspend fun tasks(): List<TaskItem>
    suspend fun academicOverview(week: Int): AcademicOverview
    suspend fun completeTask(task: TaskItem): TaskItem
    suspend fun logout()
    fun clearSession()
}
