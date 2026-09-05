package com.studyagent.mobile.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.studyagent.mobile.BuildConfig
import com.studyagent.mobile.data.AcademicOverview
import com.studyagent.mobile.data.ApiException
import com.studyagent.mobile.data.Dashboard
import com.studyagent.mobile.data.StudyRepository
import com.studyagent.mobile.data.TaskItem
import com.studyagent.mobile.data.UserProfile
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

class AppViewModel(private val repository: StudyRepository) : ViewModel() {
    private val _state = MutableStateFlow(
        AppUiState(
            serverUrl = repository.savedServer,
            selectedWeek = repository.savedWeek,
            selectedWeekday = com.studyagent.mobile.util.StudyTime.weekday(),
        ),
    )
    val state: StateFlow<AppUiState> = _state.asStateFlow()

    fun login(serverUrl: String, email: String, password: String) {
        if (_state.value.loading) return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val normalized = repository.configureServer(serverUrl, BuildConfig.DEBUG)
                val profile = repository.login(email.trim(), password)
                _state.update {
                    it.copy(
                        phase = SessionPhase.SIGNED_IN,
                        serverUrl = normalized,
                        profile = profile,
                        loading = false,
                    )
                }
                refresh()
            } catch (error: Exception) {
                repository.clearSession()
                _state.update { it.copy(loading = false, error = readableMessage(error)) }
            }
        }
    }

    fun refresh() {
        if (_state.value.phase != SessionPhase.SIGNED_IN || _state.value.loading) return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val week = _state.value.selectedWeek
                val result = coroutineScope {
                    val dashboard = async { repository.dashboard() }
                    val academic = async { repository.academicOverview(week) }
                    val tasks = async { repository.tasks() }
                    Triple(dashboard.await(), academic.await(), tasks.await())
                }
                _state.update {
                    it.copy(
                        dashboard = result.first,
                        academic = result.second,
                        tasks = result.third,
                        loading = false,
                        lastUpdatedEpochMillis = System.currentTimeMillis(),
                    )
                }
            } catch (error: Exception) {
                handleAuthenticatedError(error)
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
        val next = (_state.value.selectedWeek + delta).coerceIn(1, 30)
        if (next == _state.value.selectedWeek) return
        repository.saveWeek(next)
        _state.update { it.copy(selectedWeek = next) }
        loadAcademicWeek(next)
    }

    fun completeTask(task: TaskItem) {
        if (_state.value.completingTaskId != null || task.status == "completed") return
        viewModelScope.launch {
            _state.update { it.copy(completingTaskId = task.id, error = null) }
            try {
                repository.completeTask(task)
                val result = coroutineScope {
                    val dashboard = async { repository.dashboard() }
                    val tasks = async { repository.tasks() }
                    dashboard.await() to tasks.await()
                }
                _state.update {
                    it.copy(
                        dashboard = result.first,
                        tasks = result.second,
                        completingTaskId = null,
                        lastUpdatedEpochMillis = System.currentTimeMillis(),
                    )
                }
            } catch (error: Exception) {
                _state.update { it.copy(completingTaskId = null, error = readableMessage(error)) }
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            runCatching { repository.logout() }
            _state.update {
                AppUiState(
                    serverUrl = repository.savedServer,
                    selectedWeek = repository.savedWeek,
                    selectedWeekday = com.studyagent.mobile.util.StudyTime.weekday(),
                )
            }
        }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }

    private fun loadAcademicWeek(week: Int) {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val academic = repository.academicOverview(week)
                _state.update {
                    it.copy(
                        academic = academic,
                        loading = false,
                        lastUpdatedEpochMillis = System.currentTimeMillis(),
                    )
                }
            } catch (error: Exception) {
                handleAuthenticatedError(error)
            }
        }
    }

    private fun handleAuthenticatedError(error: Exception) {
        if (error is ApiException && error.statusCode == 401) {
            repository.clearSession()
            _state.update {
                AppUiState(
                    serverUrl = repository.savedServer,
                    selectedWeek = repository.savedWeek,
                    selectedWeekday = com.studyagent.mobile.util.StudyTime.weekday(),
                    error = "登录已失效，请重新登录",
                )
            }
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

    class Factory(private val repository: StudyRepository) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            require(modelClass.isAssignableFrom(AppViewModel::class.java))
            return AppViewModel(repository) as T
        }
    }
}
