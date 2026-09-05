package com.studyagent.mobile.data

import android.content.Context
import androidx.core.content.edit
import com.studyagent.mobile.util.ServerAddressPolicy

class StudyRepository(context: Context) {
    private val preferences = context.getSharedPreferences("mobile_preferences", Context.MODE_PRIVATE)
    private val client = ApiClient()

    val savedServer: String
        get() = preferences.getString(SERVER_KEY, DEFAULT_SERVER).orEmpty()

    val savedWeek: Int
        get() = preferences.getInt(WEEK_KEY, 1).coerceIn(1, 30)

    fun configureServer(input: String, allowPrivateHttp: Boolean): String {
        val normalized = ServerAddressPolicy.normalize(input, allowPrivateHttp)
        client.configure(normalized)
        preferences.edit { putString(SERVER_KEY, normalized) }
        return normalized
    }

    fun saveWeek(week: Int) {
        preferences.edit { putInt(WEEK_KEY, week.coerceIn(1, 30)) }
    }

    suspend fun login(email: String, password: String): UserProfile = client.login(email, password)
    suspend fun currentUser(): UserProfile = client.currentUser()
    suspend fun dashboard(): Dashboard = client.dashboard()
    suspend fun tasks(): List<TaskItem> = client.tasks()
    suspend fun academicOverview(week: Int): AcademicOverview = client.academicOverview(week)
    suspend fun completeTask(task: TaskItem): TaskItem = client.completeTask(task)
    suspend fun logout() = client.logout()

    fun clearSession() = client.clearSession()

    private companion object {
        const val SERVER_KEY = "server_url"
        const val WEEK_KEY = "academic_week"
        const val DEFAULT_SERVER = "http://127.0.0.1:8000"
    }
}
