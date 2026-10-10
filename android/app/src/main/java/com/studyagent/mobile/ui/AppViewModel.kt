package com.studyagent.mobile.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.studyagent.mobile.BuildConfig
import com.studyagent.mobile.data.AcademicOverview
import com.studyagent.mobile.data.ApiException
import com.studyagent.mobile.data.Dashboard
import com.studyagent.mobile.data.StudyDataSource
import com.studyagent.mobile.data.TaskItem
import com.studyagent.mobile.data.UserProfile
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.IOException

enum class SessionPhase { SIGNED_OUT, SIGNED_IN }
enum class MainTab { TODAY, CALENDAR, TASKS }

data class AppUiState(
    val phase: SessionPhase = SessionPhase.SIGNED_OUT,
    val serverUrl: String = "",
    val profile: UserProfile? = null,
    val dashboard: Dashboard? = null,
    val academic: AcademicOverview? = null,
    val tasks: List<TaskItem> = emptyList(),
    val selectedWeek: Int = 1,
    val selectedWeekday: Int = 1,
    val tab: MainTab = MainTab.TODAY,
    val settingsOpen: Boolean = false,
    val loading: Boolean = false,
    val completingTaskId: Int? = null,
    val error: String? = null,
    val lastUpdatedEpochMillis: Long? = null,
)

class AppViewModel(private val repository: StudyDataSource) : ViewModel() {
    private val _state = MutableStateFlow(
        AppUiState(
            serverUrl = repository.savedServer,
            selectedWeek = repository.savedWeek,
            selectedWeekday = com.studyagent.mobile.util.StudyTime.weekday(),
        ),
    )
    val state: StateFlow<AppUiState> = _state.asStateFlow()
    private var sessionGeneration = 0L
    private var readGeneration = 0L
    private var readJob: Job? = null
    private var completionJob: Job? = null
    private var authJob: Job? = null

    fun login(serverUrl: String, email: String, password: String) {
        if (_state.value.loading || _state.value.phase != SessionPhase.SIGNED_OUT) return
        val session = ++sessionGeneration
        _state.update { it.copy(loading = true, error = null) }
        authJob = viewModelScope.launch {
            try {
                val normalized = repository.configureServer(serverUrl, BuildConfig.DEBUG)
                val profile = repository.login(email.trim(), password)
                if (session != sessionGeneration) return@launch
                _state.update {
                    it.copy(
                        phase = SessionPhase.SIGNED_IN,
                        serverUrl = normalized,
                        profile = profile,
                        loading = false,
                    )
                }
                refresh()
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (session != sessionGeneration) return@launch
                repository.clearSession()
                _state.update { it.copy(loading = false, error = readableMessage(error)) }
            }
        }
    }

    fun refresh() {
        if (_state.value.phase != SessionPhase.SIGNED_IN || _state.value.loading) return
        loadOverview()
    }

    private fun loadOverview() {
        readJob?.cancel()
        val request = ++readGeneration
        val session = sessionGeneration
        val week = _state.value.selectedWeek
        _state.update { it.copy(loading = true, error = null) }
        readJob = viewModelScope.launch {
            try {
                val result = coroutineScope {
                    val dashboard = async { repository.dashboard() }
                    val academic = async { repository.academicOverview(week) }
                    val tasks = async { repository.tasks() }
                    Triple(dashboard.await(), academic.await(), tasks.await())
                }
                if (!currentSession(session) || request != readGeneration) return@launch
                check(result.second.week == week) { "课表周次不匹配，请刷新后重试" }
                _state.update {
                    it.copy(
                        dashboard = result.first,
                        academic = result.second,
                        tasks = result.third,
                        loading = false,
                        lastUpdatedEpochMillis = System.currentTimeMillis(),
                    )
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (currentSession(session) && request == readGeneration) handleAuthenticatedError(error)
            }
        }
    }

    fun selectTab(tab: MainTab) {
        _state.update { it.copy(tab = tab, settingsOpen = false) }
    }

    fun setSettingsOpen(open: Boolean) {
        _state.update { it.copy(settingsOpen = open) }
    }

    fun selectWeekday(weekday: Int) {
        _state.update { it.copy(selectedWeekday = weekday.coerceIn(1, 7)) }
    }

    fun changeWeek(delta: Int) {
        if (_state.value.phase != SessionPhase.SIGNED_IN) return
        val next = (_state.value.selectedWeek + delta).coerceIn(1, 30)
        if (next == _state.value.selectedWeek) return
        repository.saveWeek(next)
        _state.update { it.copy(selectedWeek = next, academic = null) }
        loadOverview()
    }

    fun completeTask(task: TaskItem) {
        val currentTask = _state.value.tasks.firstOrNull {
            it.id == task.id && it.navigationKey == task.navigationKey
        } ?: return
        if (_state.value.phase != SessionPhase.SIGNED_IN || _state.value.completingTaskId != null
            || currentTask.status == "completed" || currentTask.status == "canceled") return
        val session = sessionGeneration
        // Acquire the action lock before launching, including rapid taps in
        // the same UI frame before the coroutine dispatcher resumes.
        _state.update { it.copy(completingTaskId = task.id, error = null) }
        completionJob = viewModelScope.launch {
            try {
                val completed = repository.completeTask(currentTask)
                if (!currentSession(session)) return@launch
                // Preserve the confirmed mutation even if a subsequent
                // dashboard/calendar read fails; stale UI taps must not
                // resubmit a task whose completion already succeeded.
                _state.update {
                    it.copy(
                        tasks = it.tasks.map { saved ->
                            if (saved.id == completed.id && saved.navigationKey == completed.navigationKey) completed else saved
                        },
                        dashboard = null,
                        completingTaskId = null,
                    )
                }
                loadOverview()
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (currentSession(session)) {
                    _state.update { it.copy(completingTaskId = null) }
                    handleAuthenticatedError(error)
                }
            }
        }
    }

    fun logout() {
        invalidateRequests()
        val session = sessionGeneration
        _state.value = signedOutState().copy(loading = true)
        authJob = viewModelScope.launch {
            try {
                repository.logout()
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                // Local logout remains available while the service is offline.
            } finally {
                if (session == sessionGeneration) {
                    repository.clearSession()
                    _state.value = signedOutState()
                }
            }
        }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }

    private fun currentSession(generation: Long) =
        generation == sessionGeneration && _state.value.phase == SessionPhase.SIGNED_IN

    private fun invalidateRequests() {
        sessionGeneration++
        readGeneration++
        readJob?.cancel()
        completionJob?.cancel()
        authJob?.cancel()
    }

    private fun signedOutState(error: String? = null) = AppUiState(
        serverUrl = repository.savedServer,
        selectedWeek = repository.savedWeek,
        selectedWeekday = com.studyagent.mobile.util.StudyTime.weekday(),
        error = error,
    )

    private fun handleAuthenticatedError(error: Exception) {
        if (error is ApiException && error.statusCode == 401) {
            invalidateRequests()
            repository.clearSession()
            _state.value = signedOutState("登录已失效，请重新登录")
        } else {
            _state.update { it.copy(loading = false, error = readableMessage(error)) }
        }
    }

    private fun readableMessage(error: Exception): String = when (error) {
        is ApiException -> error.message
        is IllegalArgumentException -> error.message ?: "连接配置不正确"
        is IOException -> "无法连接学习服务，请检查地址和后端状态"
        else -> error.message ?: "读取失败，请稍后重试"
    }

    class Factory(private val repository: StudyDataSource) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            require(modelClass.isAssignableFrom(AppViewModel::class.java))
            return AppViewModel(repository) as T
        }
    }
}
