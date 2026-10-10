package com.studyagent.mobile.ui

import com.studyagent.mobile.data.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.test.*
import kotlinx.coroutines.withContext
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class AppViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    @Test fun lateWeekResponseCannotOverwriteTheSelectedWeek() = runTest {
        val source = FakeSource()
        val model = AppViewModel(source)
        model.login("http://localhost:8000", "demo@example.com", "test-only")
        advanceUntilIdle()
        val second = CompletableDeferred<AcademicOverview>()
        val third = CompletableDeferred<AcademicOverview>()
        source.academicLoad = { week -> withContext(NonCancellable) { if (week == 2) second.await() else third.await() } }
        model.changeWeek(1)
        runCurrent()
        assertNull("do not show week 1 under the week 2 heading", model.state.value.academic)
        model.changeWeek(1)
        runCurrent()
        third.complete(AcademicOverview(3, emptyList(), emptyList()))
        runCurrent()
        assertEquals(3, model.state.value.academic?.week)
        second.complete(AcademicOverview(2, emptyList(), emptyList()))
        advanceUntilIdle()
        assertEquals(3, model.state.value.selectedWeek)
        assertEquals(3, model.state.value.academic?.week)
        assertNull(model.state.value.error)
        assertFalse(model.state.value.loading)
    }

    @Test fun failedWeekLoadDoesNotRetainTheOldWeeksClasses() = runTest {
        val source = FakeSource()
        val model = AppViewModel(source)
        model.login("http://localhost:8000", "demo@example.com", "test-only")
        advanceUntilIdle()
        source.academicLoad = { throw IOException("offline") }
        model.changeWeek(1)
        advanceUntilIdle()
        assertEquals(2, model.state.value.selectedWeek)
        assertNull(model.state.value.academic)
        assertNotNull(model.state.value.error)
        assertFalse(model.state.value.loading)
    }

    @Test fun completionExpiryClearsAllAuthenticatedContent() = runTest {
        val source = FakeSource()
        val model = AppViewModel(source)
        model.login("http://localhost:8000", "demo@example.com", "test-only")
        advanceUntilIdle()
        source.complete = { throw ApiException(401, "expired") }
        model.completeTask(source.task)
        advanceUntilIdle()
        assertEquals(SessionPhase.SIGNED_OUT, model.state.value.phase)
        assertNull(model.state.value.profile)
        assertNull(model.state.value.dashboard)
        assertNull(model.state.value.academic)
        assertTrue(model.state.value.tasks.isEmpty())
        assertNull(model.state.value.completingTaskId)
        assertTrue(source.cleared)
    }

    @Test fun lateRefreshCannotRestoreContentAfterLogout() = runTest {
        val source = FakeSource()
        val model = AppViewModel(source)
        model.login("http://localhost:8000", "demo@example.com", "test-only")
        advanceUntilIdle()
        val pending = CompletableDeferred<AcademicOverview>()
        source.academicLoad = { withContext(NonCancellable) { pending.await() } }
        model.refresh()
        runCurrent()
        model.logout()
        runCurrent()
        pending.complete(AcademicOverview(1, emptyList(), emptyList()))
        advanceUntilIdle()
        assertEquals(SessionPhase.SIGNED_OUT, model.state.value.phase)
        assertNull(model.state.value.dashboard)
        assertNull(model.state.value.academic)
        assertTrue(model.state.value.tasks.isEmpty())
        assertNull(model.state.value.error)
    }

    @Test fun rapidCompletionTapsIssueOnlyOneMutation() = runTest {
        val source = FakeSource()
        val model = AppViewModel(source)
        model.login("http://localhost:8000", "demo@example.com", "test-only")
        advanceUntilIdle()
        model.completeTask(source.task)
        model.completeTask(source.task)
        advanceUntilIdle()
        assertEquals(1, source.completeCalls)
        assertNull(model.state.value.completingTaskId)
        assertEquals("completed", model.state.value.tasks.single().status)
    }

    @Test fun successfulCompletionSurvivesAFailedRefreshAndStaleTap() = runTest {
        val source = FakeSource()
        val model = AppViewModel(source)
        model.login("http://localhost:8000", "demo@example.com", "test-only")
        advanceUntilIdle()
        val previousTask = source.task
        source.academicLoad = { throw IOException("calendar offline") }
        model.completeTask(previousTask)
        advanceUntilIdle()
        assertEquals("completed", model.state.value.tasks.single().status)
        assertNotNull(model.state.value.error)
        model.completeTask(previousTask)
        advanceUntilIdle()
        assertEquals(1, source.completeCalls)
    }

    @Test fun staleTapDuringPostCompletionReloadCannotRepeatTheWrite() = runTest {
        val source = FakeSource()
        val model = AppViewModel(source)
        model.login("http://localhost:8000", "demo@example.com", "test-only")
        advanceUntilIdle()
        val previousTask = source.task
        val pending = CompletableDeferred<AcademicOverview>()
        source.academicLoad = { pending.await() }
        model.completeTask(previousTask)
        runCurrent()
        assertTrue(model.state.value.loading)
        model.completeTask(previousTask)
        runCurrent()
        assertEquals(1, source.completeCalls)
        pending.complete(AcademicOverview(1, emptyList(), emptyList()))
        advanceUntilIdle()
    }

    private class FakeSource : StudyDataSource {
        override val savedServer = "http://localhost:8000"
        override var savedWeek = 1
        var task = TaskItem(1, "a".repeat(32), 1, "报告", null, "not_started", 3, 30, null)
        var cleared = false
        var completeCalls = 0
        var academicLoad: suspend (Int) -> AcademicOverview = { AcademicOverview(it, emptyList(), emptyList()) }
        var complete: suspend (TaskItem) -> TaskItem = { it.copy(status = "completed") }
        override fun configureServer(input: String, allowPrivateHttp: Boolean) = input
        override fun saveWeek(week: Int) { savedWeek = week }
        override suspend fun login(email: String, password: String) = UserProfile("user", email, "测试同学")
        override suspend fun dashboard() = Dashboard(1, 0, 0, 0, 0, null, listOf(task), emptyList())
        override suspend fun tasks() = listOf(task)
        override suspend fun academicOverview(week: Int) = academicLoad(week)
        override suspend fun completeTask(task: TaskItem): TaskItem {
            completeCalls++
            return complete(task).also { this.task = it }
        }
        override suspend fun logout() { clearSession() }
        override fun clearSession() { cleared = true }
    }
}
