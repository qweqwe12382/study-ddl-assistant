package com.studyagent.mobile.data

import android.content.Context
import androidx.core.content.edit
import com.studyagent.mobile.util.ServerAddressPolicy

class StudyRepository(context: Context) : StudyDataSource {
    private val preferences = context.getSharedPreferences("mobile_preferences", Context.MODE_PRIVATE)
    private val client = ApiClient()

    override val savedServer: String
        get() = preferences.getString(SERVER_KEY, DEFAULT_SERVER).orEmpty()

    override val savedWeek: Int
        get() = preferences.getInt(WEEK_KEY, 1).coerceIn(1, 30)

    override fun configureServer(input: String, allowPrivateHttp: Boolean): String {
        val normalized = ServerAddressPolicy.normalize(input, allowPrivateHttp)
        client.configure(normalized)
        preferences.edit { putString(SERVER_KEY, normalized) }
        return normalized
    }

    override fun saveWeek(week: Int) {
        preferences.edit { putInt(WEEK_KEY, week.coerceIn(1, 30)) }
    }

    override suspend fun login(email: String, password: String): UserProfile = client.login(email, password)
    suspend fun currentUser(): UserProfile = client.currentUser()
    override suspend fun dashboard(): Dashboard = client.dashboard()
    override suspend fun tasks(): List<TaskItem> = client.tasks()
    override suspend fun academicOverview(week: Int): AcademicOverview = client.academicOverview(week)
    override suspend fun completeTask(task: TaskItem): TaskItem = client.completeTask(task)
    override suspend fun logout() = client.logout()

    override fun clearSession() = client.clearSession()

    private companion object {
        const val SERVER_KEY = "server_url"
        const val WEEK_KEY = "academic_week"
        const val DEFAULT_SERVER = "http://127.0.0.1:8000"
    }
}
