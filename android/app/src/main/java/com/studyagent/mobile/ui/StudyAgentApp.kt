package com.studyagent.mobile.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.studyagent.mobile.BuildConfig
import com.studyagent.mobile.data.AcademicOverview
import com.studyagent.mobile.data.ClassSession
import com.studyagent.mobile.data.Dashboard
import com.studyagent.mobile.data.ExamItem
import com.studyagent.mobile.data.TaskItem
import com.studyagent.mobile.data.UserProfile
import com.studyagent.mobile.ui.theme.CourseBlue
import com.studyagent.mobile.ui.theme.ExamCoral
import com.studyagent.mobile.ui.theme.Ink
import com.studyagent.mobile.ui.theme.StudyAgentTheme
import com.studyagent.mobile.ui.theme.StudyTeal
import com.studyagent.mobile.util.StudyTime
import com.studyagent.mobile.util.DeadlineCalendarEvent
import com.studyagent.mobile.util.DeadlineCalendarEventFactory
import com.studyagent.mobile.util.toCalendarInsertIntent
import java.time.format.DateTimeFormatter
import java.util.Locale

private val cardShape = RoundedCornerShape(20.dp)
private val smallShape = RoundedCornerShape(13.dp)
private val weekdays = listOf("一", "二", "三", "四", "五", "六", "日")
private val utilityText = TextStyle(
    fontFamily = FontFamily.Monospace,
    fontWeight = FontWeight.SemiBold,
    fontSize = 11.sp,
    lineHeight = 15.sp,
)

@Composable
fun StudyAgentApp(viewModel: AppViewModel) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.clearError()
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Scaffold(
            contentWindowInsets = WindowInsets.safeDrawing,
            snackbarHost = { SnackbarHost(snackbar) },
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                if (state.phase == SessionPhase.SIGNED_OUT) {
                    ConnectionScreen(
                        initialServer = state.serverUrl,
                        loading = state.loading,
                        onLogin = viewModel::login,
                    )
                } else {
                    AuthenticatedShell(
                        state = state,
                        onSelectTab = viewModel::selectTab,
                        onRefresh = viewModel::refresh,
                        onOpenSettings = { viewModel.setSettingsOpen(true) },
                        onCloseSettings = { viewModel.setSettingsOpen(false) },
                        onChangeWeek = viewModel::changeWeek,
                        onSelectWeekday = viewModel::selectWeekday,
                        onCompleteTask = viewModel::completeTask,
                        onLogout = viewModel::logout,
                    )
                }
                if (state.loading && state.phase == SessionPhase.SIGNED_IN) {
                    LinearProgressIndicator(Modifier.fillMaxWidth().align(Alignment.TopCenter))
                }
            }
        }
    }
}

@Composable
private fun ConnectionScreen(
    initialServer: String,
    loading: Boolean,
    onLogin: (String, String, String) -> Unit,
) {
    var server by remember(initialServer) { mutableStateOf(initialServer) }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    val canLogin = server.isNotBlank() && email.isNotBlank() && password.isNotBlank() && !loading

    Box(Modifier.fillMaxSize().imePadding(), contentAlignment = Alignment.TopCenter) {
        Column(
            modifier = Modifier
                .widthIn(max = 520.dp)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 22.dp, vertical = 28.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(42.dp).clip(RoundedCornerShape(14.dp)).background(Ink),
                    contentAlignment = Alignment.Center,
                ) {
                    RouteGlyph(color = Color.White)
                }
                Spacer(Modifier.width(13.dp))
                Column {
                    Text("学伴管家", style = MaterialTheme.typography.headlineSmall)
                    Text("你的学习行动导航", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            Spacer(Modifier.height(24.dp))
            LoginRouteBoard()
            Spacer(Modifier.height(24.dp))
            Text("连接你的学习空间", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(6.dp))
            Text(
                "登录后从今天出发，沿着课程、考试和 DDL 安排行动。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(20.dp))

            OutlinedTextField(
                value = server,
                onValueChange = { server = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("学习服务地址") },
                placeholder = { Text("https://study.example.com") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Next),
                keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(FocusDirection.Down) }),
                supportingText = {
                    Text(if (BuildConfig.DEBUG) "USB 调试可用 http://127.0.0.1:8000" else "正式版仅接受 HTTPS")
                },
            )
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("邮箱") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
                keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(FocusDirection.Down) }),
            )
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("密码") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = {
                    focusManager.clearFocus()
                    if (canLogin) {
                        val enteredPassword = password
                        password = ""
                        onLogin(server, email, enteredPassword)
                    }
                }),
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    val enteredPassword = password
                    password = ""
                    focusManager.clearFocus()
                    onLogin(server, email, enteredPassword)
                },
                enabled = canLogin,
                modifier = Modifier.fillMaxWidth().height(50.dp),
                shape = smallShape,
            ) {
                if (loading) {
                    CircularProgressIndicator(Modifier.size(19.dp), strokeWidth = 2.dp, color = Color.White)
                    Spacer(Modifier.width(9.dp))
                    Text("正在连接")
                } else {
                    Text("登录并读取今天")
                }
            }

            Spacer(Modifier.height(18.dp))
            PrivacyStrip()
        }
    }
}

@Composable
private fun LoginRouteBoard() {
    val boardColor = if (isSystemInDarkTheme()) Color(0xFF173A4D) else Ink
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = cardShape,
        color = boardColor,
    ) {
        Column(Modifier.padding(horizontal = 18.dp, vertical = 17.dp)) {
            Text("今日学习航线", style = utilityText, color = Color(0xFFABC5D4))
            Spacer(Modifier.height(12.dp))
            Box(Modifier.fillMaxWidth().height(48.dp)) {
                Canvas(Modifier.fillMaxSize()) {
                    val y = 11.dp.toPx()
                    val start = 10.dp.toPx()
                    val end = size.width - 10.dp.toPx()
                    drawLine(Color.White.copy(alpha = .24f), start = androidx.compose.ui.geometry.Offset(start, y), end = androidx.compose.ui.geometry.Offset(end, y), strokeWidth = 2.dp.toPx())
                    listOf(start, size.width / 2f, end).forEachIndexed { index, x ->
                        drawCircle(
                            color = if (index == 1) Color(0xFF7EE0D2) else Color.White,
                            radius = if (index == 1) 6.dp.toPx() else 4.dp.toPx(),
                            center = androidx.compose.ui.geometry.Offset(x, y),
                        )
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top = 25.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("同步事实", style = utilityText, color = Color.White)
                    Text("决定下一步", style = utilityText, color = Color(0xFF7EE0D2))
                    Text("按时完成", style = utilityText, color = Color.White)
                }
            }
        }
    }
}

@Composable
private fun RouteGlyph(color: Color) {
    Canvas(Modifier.size(24.dp)) {
        val y = size.height / 2f
        drawLine(color.copy(alpha = .6f), androidx.compose.ui.geometry.Offset(3.dp.toPx(), y), androidx.compose.ui.geometry.Offset(size.width - 3.dp.toPx(), y), 2.dp.toPx())
        drawCircle(color, 3.dp.toPx(), androidx.compose.ui.geometry.Offset(4.dp.toPx(), y))
        drawCircle(color, 4.dp.toPx(), androidx.compose.ui.geometry.Offset(size.width / 2f, y))
        drawCircle(color, 3.dp.toPx(), androidx.compose.ui.geometry.Offset(size.width - 4.dp.toPx(), y))
    }
}

@Composable
private fun PrivacyStrip() {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, StudyTeal.copy(alpha = .18f), smallShape),
        shape = smallShape,
        color = MaterialTheme.colorScheme.secondaryContainer,
    ) {
        Row(Modifier.padding(13.dp), verticalAlignment = Alignment.Top) {
            Icon(Icons.Default.Lock, contentDescription = null, tint = MaterialTheme.colorScheme.secondary, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(9.dp))
            Column {
                Text("密码不留在手机里", style = MaterialTheme.typography.labelLarge)
                Text(
                    "Cookie 仅用于本次运行；手机只保存服务地址和所选教学周。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                )
            }
        }
    }
}

@Composable
private fun AuthenticatedShell(
    state: AppUiState,
    onSelectTab: (MainTab) -> Unit,
    onRefresh: () -> Unit,
    onOpenSettings: () -> Unit,
    onCloseSettings: () -> Unit,
    onChangeWeek: (Int) -> Unit,
    onSelectWeekday: (Int) -> Unit,
    onCompleteTask: (TaskItem) -> Unit,
    onLogout: () -> Unit,
) {
    BackHandler(enabled = state.settingsOpen, onBack = onCloseSettings)
    if (state.settingsOpen) {
        SettingsScreen(state, onCloseSettings, onLogout)
        return
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            MobileTopBar(
                state = state,
                onRefresh = onRefresh,
                onSettings = onOpenSettings,
            )
        },
        bottomBar = { MobileBottomBar(state.tab, onSelectTab) },
    ) { padding ->
        when (state.tab) {
            MainTab.TODAY -> TodayScreen(state, onCompleteTask, Modifier.padding(padding))
            MainTab.CALENDAR -> CalendarScreen(
                state = state,
                onChangeWeek = onChangeWeek,
                onSelectWeekday = onSelectWeekday,
                modifier = Modifier.padding(padding),
            )
            MainTab.TASKS -> TasksScreen(state, onCompleteTask, Modifier.padding(padding))
        }
    }
}

@Composable
private fun MobileTopBar(state: AppUiState, onRefresh: () -> Unit, onSettings: () -> Unit) {
    val activeCount = state.tasks.count { it.status != "completed" && it.status != "canceled" }
    val eyebrow = when (state.tab) {
        MainTab.TODAY -> StudyTime.today().format(DateTimeFormatter.ofPattern("M月d日 EEEE", Locale.CHINA))
        MainTab.CALENDAR -> "第 ${state.selectedWeek} 教学周"
        MainTab.TASKS -> "$activeCount 项等待完成"
    }
    val title = when (state.tab) {
        MainTab.TODAY -> "${state.profile?.displayName ?: "同学"}，今天怎么走"
        MainTab.CALENDAR -> "课表与考试"
        MainTab.TASKS -> "DDL 行动队列"
    }
    Surface(color = MaterialTheme.colorScheme.background) {
        Row(
            Modifier.fillMaxWidth().padding(start = 18.dp, end = 8.dp, top = 13.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier.size(34.dp).clip(RoundedCornerShape(11.dp)).background(MaterialTheme.colorScheme.primary),
                contentAlignment = Alignment.Center,
            ) { RouteGlyph(MaterialTheme.colorScheme.onPrimary) }
            Spacer(Modifier.width(11.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    eyebrow,
                    style = utilityText,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(title, style = MaterialTheme.typography.titleMedium)
            }
            HeaderAction(onClick = onRefresh, icon = Icons.Default.Refresh, label = "刷新")
            Spacer(Modifier.width(2.dp))
            HeaderAction(onClick = onSettings, icon = Icons.Default.Settings, label = "设置")
        }
    }
}

@Composable
private fun HeaderAction(onClick: () -> Unit, icon: ImageVector, label: String) {
    IconButton(onClick = onClick, modifier = Modifier.size(40.dp)) {
        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surface) {
            Box(Modifier.size(34.dp), contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = label, modifier = Modifier.size(19.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun MobileBottomBar(selected: MainTab, onSelect: (MainTab) -> Unit) {
    val routeLineColor = MaterialTheme.colorScheme.outline
    Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 10.dp) {
        Box(Modifier.fillMaxWidth().height(72.dp)) {
            Canvas(Modifier.fillMaxWidth().height(36.dp)) {
                val y = 18.dp.toPx()
                drawLine(
                    color = routeLineColor,
                    start = androidx.compose.ui.geometry.Offset(size.width / 6f, y),
                    end = androidx.compose.ui.geometry.Offset(size.width * 5f / 6f, y),
                    strokeWidth = 2.dp.toPx(),
                )
            }
            Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.SpaceEvenly) {
                BottomDestination(MainTab.TODAY, selected, "今天", Icons.Default.Home, onSelect)
                BottomDestination(MainTab.CALENDAR, selected, "课表", Icons.Default.DateRange, onSelect)
                BottomDestination(MainTab.TASKS, selected, "DDL", Icons.Default.CheckCircle, onSelect)
            }
        }
    }
}

@Composable
private fun BottomDestination(
    tab: MainTab,
    selected: MainTab,
    label: String,
    icon: ImageVector,
    onSelect: (MainTab) -> Unit,
) {
    val active = tab == selected
    Column(
        Modifier
            .width(96.dp)
            .height(72.dp)
            .selectable(selected = active, role = Role.Tab) { onSelect(tab) },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Top,
    ) {
        Surface(
            modifier = Modifier.size(36.dp),
            shape = CircleShape,
            color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
            border = BorderStroke(2.dp, if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(
                    icon,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                    tint = if (active) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.height(4.dp))
        Text(
            label,
            style = if (active) MaterialTheme.typography.labelLarge else MaterialTheme.typography.labelMedium,
            color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun TodayScreen(state: AppUiState, onCompleteTask: (TaskItem) -> Unit, modifier: Modifier = Modifier) {
    val today = StudyTime.today()
    val day = today.dayOfWeek.value
    val sessions = state.academic?.classSessions.orEmpty().filter { it.weekday == day }
    val activeTasks = state.tasks.filter { it.status != "completed" && it.status != "canceled" }
    val todayTasks = activeTasks.filter { StudyTime.dateOf(it.dueAt)?.let { date -> !date.isAfter(today) } == true }
    val nextExam = state.academic?.exams?.firstOrNull()

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            AgentDirection(state.dashboard)
        }
        item {
            CompactMetrics(state.dashboard)
        }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SectionHeading("今日安排", "时间轨道", Modifier.weight(1f))
                StatusPill("第 ${state.selectedWeek} 周", CourseBlue, CourseBlue.copy(alpha = .1f))
            }
        }
        if (sessions.isEmpty() && todayTasks.isEmpty()) {
            item { EmptyBlock("今天没有固定安排", "可以从未来 DDL 中挑一项，或留出一段自主学习时间。") }
        } else {
            items(sessions, key = { "class-${it.id}" }) { session ->
                TimelineClass(session)
            }
            items(todayTasks, key = { "task-${it.id}" }) { task ->
                TimelineTask(task, state.completingTaskId == task.id, onCompleteTask)
            }
        }
        item {
            SectionHeading("临近节点", "最近考试")
        }
        item {
            if (nextExam == null) EmptyBlock("还没有考试安排", "从网页版接入教务或手动添加考试后会显示在这里。")
            else ExamCard(nextExam)
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

@Composable
private fun AgentDirection(dashboard: Dashboard?) {
    val cardColor = if (isSystemInDarkTheme()) Color(0xFF173A4D) else Ink
    Surface(shape = cardShape, color = cardColor) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 17.dp, vertical = 16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusPill("智能体 · 下一步", Color(0xFF7EE0D2), Color.White.copy(alpha = .08f))
                Spacer(Modifier.weight(1f))
                Text("NOW", style = utilityText, color = Color(0xFF8DA8B8))
            }
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.Top) {
                Box(
                    Modifier.size(30.dp).clip(CircleShape).background(Color.White.copy(alpha = .1f)),
                    contentAlignment = Alignment.Center,
                ) { Text("→", color = Color.White, fontWeight = FontWeight.Bold) }
                Spacer(Modifier.width(11.dp))
                Text(
                    dashboard?.nextAction ?: "正在整理你的下一步学习行动。",
                    style = MaterialTheme.typography.bodyLarge,
                    color = Color.White,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun CompactMetrics(dashboard: Dashboard?) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = smallShape,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
            MetricChip("待完成", dashboard?.activeTaskCount?.toString() ?: "—", CourseBlue, Modifier.weight(1f))
            VerticalDivider(Modifier.fillMaxHeight().padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outline)
            MetricChip("七日内", dashboard?.dueSoonCount?.toString() ?: "—", StudyTeal, Modifier.weight(1f))
            VerticalDivider(Modifier.fillMaxHeight().padding(vertical = 12.dp), color = MaterialTheme.colorScheme.outline)
            MetricChip("已逾期", dashboard?.overdueCount?.toString() ?: "—", ExamCoral, Modifier.weight(1f))
        }
    }
}

@Composable
private fun MetricChip(label: String, value: String, accent: Color, modifier: Modifier = Modifier) {
    Column(modifier.padding(horizontal = 12.dp, vertical = 11.dp)) {
        Text(value, style = utilityText.copy(fontSize = 18.sp, lineHeight = 21.sp), color = accent)
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun StatusPill(label: String, contentColor: Color, containerColor: Color) {
    Surface(shape = CircleShape, color = containerColor) {
        Text(
            label,
            modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp),
            style = utilityText,
            color = contentColor,
        )
    }
}

@Composable
private fun CompletionButton(completing: Boolean, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .size(38.dp)
            .selectable(selected = false, enabled = !completing, role = Role.Checkbox, onClick = onClick),
        shape = CircleShape,
        color = if (completing) StudyTeal.copy(alpha = .12f) else Color.Transparent,
        border = BorderStroke(1.5.dp, StudyTeal),
    ) {
        Box(contentAlignment = Alignment.Center) {
            if (completing) {
                CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp, color = StudyTeal)
            } else {
                Icon(Icons.Default.CheckCircle, contentDescription = "标记完成", tint = StudyTeal, modifier = Modifier.size(20.dp))
            }
        }
    }
}

@Composable
private fun TimelineClass(session: ClassSession) {
    TimelineRow(
        time = session.startTime.take(5),
        accent = safeCourseColor(session.courseColor),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(session.courseName, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            StatusPill("课程", safeCourseColor(session.courseColor), safeCourseColor(session.courseColor).copy(alpha = .1f))
        }
        Text(
            "${session.startTime.take(5)}–${session.endTime.take(5)}  ·  ${session.location ?: "地点待补充"}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        session.teacher?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
private fun TimelineTask(task: TaskItem, completing: Boolean, onComplete: (TaskItem) -> Unit) {
    TimelineRow(time = "DDL", accent = if (task.status == "overdue") ExamCoral else StudyTeal) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(task.name, style = MaterialTheme.typography.titleMedium)
                Text(
                    "${StudyTime.formatDateTime(task.dueAt)}  ·  优先级 ${task.priority}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                DeadlineCalendarAction(task)
            }
            Spacer(Modifier.width(8.dp))
            CompletionButton(completing) { onComplete(task) }
        }
    }
}

@Composable
private fun TimelineRow(time: String, accent: Color, content: @Composable () -> Unit) {
    Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
        Column(Modifier.width(52.dp).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(time, style = utilityText, color = accent)
            Spacer(Modifier.height(5.dp))
            Canvas(Modifier.width(14.dp).weight(1f)) {
                drawCircle(accent, radius = 4.dp.toPx(), center = center.copy(y = 5.dp.toPx()))
                drawLine(
                    color = accent.copy(alpha = .35f),
                    start = center.copy(y = 13.dp.toPx()),
                    end = center.copy(y = size.height),
                    strokeWidth = 1.dp.toPx(),
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 4.dp.toPx())),
                )
            }
        }
        Surface(
            modifier = Modifier.weight(1f),
            shape = smallShape,
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Column(Modifier.fillMaxWidth().padding(14.dp), content = { content() })
        }
    }
}

@Composable
private fun CalendarScreen(
    state: AppUiState,
    onChangeWeek: (Int) -> Unit,
    onSelectWeekday: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val sessions = state.academic?.classSessions.orEmpty().filter { it.weekday == state.selectedWeekday }
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { WeekSwitcher(state.selectedWeek, onChangeWeek) }
        item { WeekdayPicker(state.selectedWeekday, state.academic?.classSessions.orEmpty(), onSelectWeekday) }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SectionHeading("星期${weekdays[state.selectedWeekday - 1]}", "当天课程", Modifier.weight(1f))
                StatusPill("${sessions.size} 节", CourseBlue, CourseBlue.copy(alpha = .1f))
            }
        }
        if (sessions.isEmpty()) {
            item { EmptyBlock("当天无课", "这一页留白，适合安排自主学习或休息。") }
        } else {
            items(sessions, key = { it.id }) { CourseCard(it) }
        }
        item {
            Spacer(Modifier.height(2.dp))
            SectionHeading("本学期", "考试节点")
        }
        if (state.academic?.exams.isNullOrEmpty()) {
            item { EmptyBlock("近期没有考试", "网页版新增或同步考试后，移动端会自动读取。") }
        } else {
            items(state.academic?.exams.orEmpty(), key = { "exam-${it.id}" }) { ExamCard(it) }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

@Composable
private fun WeekSwitcher(week: Int, onChange: (Int) -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = smallShape,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 5.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = { onChange(-1) }, enabled = week > 1) {
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "上一周")
            }
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("教学周", style = utilityText, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("第 $week 周", style = MaterialTheme.typography.titleMedium)
            }
            IconButton(onClick = { onChange(1) }, enabled = week < 30) {
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "下一周")
            }
        }
    }
}

@Composable
private fun WeekdayPicker(selected: Int, sessions: List<ClassSession>, onSelect: (Int) -> Unit) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        weekdays.forEachIndexed { index, label ->
            val day = index + 1
            val count = sessions.count { it.weekday == day }
            val active = selected == day
            Column(
                Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(11.dp))
                    .background(if (active) MaterialTheme.colorScheme.primary else Color.Transparent)
                    .border(1.dp, if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline, RoundedCornerShape(11.dp))
                    .selectable(selected = active, role = Role.Tab) { onSelect(day) }
                    .padding(vertical = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(label, style = MaterialTheme.typography.labelLarge, color = if (active) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface)
                Spacer(Modifier.height(2.dp))
                Box(Modifier.size(5.dp).clip(CircleShape).background(if (count > 0) (if (active) MaterialTheme.colorScheme.onPrimary else CourseBlue) else Color.Transparent))
            }
        }
    }
}

@Composable
private fun CourseCard(session: ClassSession) {
    val accent = safeCourseColor(session.courseColor)
    Surface(
        shape = smallShape,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, accent.copy(alpha = .2f)),
    ) {
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
            Column(
                Modifier.width(76.dp).fillMaxHeight().background(accent.copy(alpha = .1f)).padding(12.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Text(session.startTime.take(5), style = utilityText.copy(fontSize = 15.sp), color = accent)
                Text(session.endTime.take(5), style = utilityText, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(Modifier.weight(1f).padding(horizontal = 14.dp, vertical = 12.dp)) {
                Text(session.courseName, style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(4.dp))
                Text(session.location ?: "地点待补充", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(7.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusPill("${weekPatternLabel(session.weekPattern)} ${session.startWeek}–${session.endWeek} 周", accent, accent.copy(alpha = .08f))
                    session.teacher?.let {
                        Spacer(Modifier.width(7.dp))
                        Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun ExamCard(exam: ExamItem) {
    Surface(
        shape = smallShape,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, ExamCoral.copy(alpha = .22f)),
    ) {
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), verticalAlignment = Alignment.CenterVertically) {
            Column(
                Modifier.width(78.dp).fillMaxHeight().background(ExamCoral.copy(alpha = .1f)).padding(12.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Text(StudyTime.countdown(exam.startsAt), style = MaterialTheme.typography.labelLarge, color = ExamCoral)
                Text(StudyTime.formatDate(exam.startsAt), style = utilityText, color = ExamCoral)
            }
            Column(Modifier.weight(1f).padding(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(exam.courseName, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    StatusPill("考试", ExamCoral, ExamCoral.copy(alpha = .1f))
                }
                Text(exam.title, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    "${StudyTime.formatDateTime(exam.startsAt)}  ·  ${exam.location ?: "地点待补充"}${exam.seatNumber?.let { "  ·  $it" } ?: ""}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun TasksScreen(state: AppUiState, onCompleteTask: (TaskItem) -> Unit, modifier: Modifier = Modifier) {
    val active = state.tasks.filter { it.status != "completed" && it.status != "canceled" }
    val completed = state.tasks.filter { it.status == "completed" }.takeLast(5).reversed()
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Row(verticalAlignment = Alignment.Bottom) {
                SectionHeading("按截止时间", "待完成", Modifier.weight(1f))
                StatusPill("${active.size} 项", CourseBlue, CourseBlue.copy(alpha = .1f))
            }
        }
        if (active.isEmpty()) {
            item { EmptyBlock("DDL 已清空", "新的课程任务会在同步后出现在这里。") }
        } else {
            items(active, key = { it.id }) { task ->
                TaskCard(task, state.completingTaskId == task.id, onCompleteTask)
            }
        }
        if (completed.isNotEmpty()) {
            item {
                Spacer(Modifier.height(6.dp))
                SectionHeading("近 5 项", "最近完成")
            }
            items(completed, key = { "done-${it.id}" }) { task -> CompletedTaskRow(task) }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

@Composable
private fun TaskCard(task: TaskItem, completing: Boolean, onComplete: (TaskItem) -> Unit) {
    val overdue = task.status == "overdue" || StudyTime.dateOf(task.dueAt)?.isBefore(StudyTime.today()) == true
    val accent = if (overdue) ExamCoral else if (task.priority >= 4) CourseBlue else StudyTeal
    Surface(
        shape = smallShape,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusPill(
                        if (overdue) "已逾期" else if (task.priority >= 4) "高优先" else "进行中",
                        accent,
                        accent.copy(alpha = .09f),
                    )
                    task.courseName?.let {
                        Spacer(Modifier.width(7.dp))
                        Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                Spacer(Modifier.height(7.dp))
                Text(task.name, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(
                    "${StudyTime.formatDateTime(task.dueAt)}${task.estimatedMinutes?.let { " · 预计 $it 分钟" } ?: ""}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                DeadlineCalendarAction(task)
            }
            Spacer(Modifier.width(10.dp))
            CompletionButton(completing) { onComplete(task) }
        }
    }
}

@Composable
private fun DeadlineCalendarAction(task: TaskItem) {
    val context = LocalContext.current
    val calendarEvent = remember(task.name, task.courseName, task.dueAt) {
        DeadlineCalendarEventFactory.from(task)
    }
    if (calendarEvent == null) return

    TextButton(
        onClick = { openCalendarEditor(context, calendarEvent) },
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 2.dp),
    ) {
        Text("加入系统日历", style = MaterialTheme.typography.labelLarge)
    }
    Text(
        "打开后请检查提醒并保存；结束时间为截止后 1 分钟，仅作截止标记。",
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

private fun openCalendarEditor(context: Context, calendarEvent: DeadlineCalendarEvent) {
    val intent = calendarEvent.toCalendarInsertIntent()
    try {
        context.startActivity(intent)
    } catch (_: ActivityNotFoundException) {
        Toast.makeText(context, "未找到可打开的系统日历应用", Toast.LENGTH_SHORT).show()
    } catch (_: SecurityException) {
        Toast.makeText(context, "系统日历暂时无法打开，请稍后重试", Toast.LENGTH_SHORT).show()
    }
}

@Composable
private fun CompletedTaskRow(task: TaskItem) {
    Surface(shape = smallShape, color = StudyTeal.copy(alpha = .06f)) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.CheckCircle, contentDescription = null, tint = StudyTeal, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(9.dp))
            Text(task.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("DONE", style = utilityText, color = StudyTeal)
        }
    }
}

@Composable
private fun SettingsScreen(state: AppUiState, onBack: () -> Unit, onLogout: () -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回") }
            Column {
                Text("手机端设置", style = utilityText, color = MaterialTheme.colorScheme.primary)
                Text("连接与隐私", style = MaterialTheme.typography.titleLarge)
            }
        }
        Column(
            Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 18.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            SectionHeading("账户", "当前学习空间")
            Surface(
                shape = cardShape,
                color = MaterialTheme.colorScheme.surface,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            ) {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(38.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) {
                            Text((state.profile?.displayName ?: "学").take(1), color = CourseBlue, fontWeight = FontWeight.Bold)
                        }
                        Spacer(Modifier.width(11.dp))
                        Column {
                            Text(state.profile?.displayName ?: "当前账号", style = MaterialTheme.typography.titleMedium)
                            Text(state.profile?.email.orEmpty(), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                    Spacer(Modifier.height(12.dp))
                    Text("服务地址", style = utilityText, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(state.serverUrl, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
            }
            SectionHeading("隐私", "手机端数据边界")
            PrivacyStrip()
            Surface(
                shape = smallShape,
                color = MaterialTheme.colorScheme.surface,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            ) {
                Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    BoundaryRow("不保存", "登录密码、教务密码、Cookie、原始资料")
                    BoundaryRow("仅保存", "服务地址、当前教学周")
                    BoundaryRow("服务端", "课表、考试、DDL 与资料索引")
                }
            }
            OutlinedButton(
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = smallShape,
                colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
            ) {
                Text("退出并清除本次会话")
            }
            Text(
                "南理工教务接入仍在网页版完成；安卓端只读取确认同步后的本地数据，避免在多个终端重复传递教务凭据。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun BoundaryRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Text(label, modifier = Modifier.width(66.dp), style = utilityText, color = MaterialTheme.colorScheme.primary)
        Text(value, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun SectionHeading(kicker: String, title: String, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.width(4.dp).height(30.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primary))
        Spacer(Modifier.width(9.dp))
        Column {
            Text(kicker, style = utilityText, color = MaterialTheme.colorScheme.primary)
            Text(title, style = MaterialTheme.typography.titleLarge)
        }
    }
}

@Composable
private fun EmptyBlock(title: String, detail: String) {
    Row(
        Modifier.fillMaxWidth().clip(smallShape).border(1.dp, MaterialTheme.colorScheme.outline, smallShape).padding(15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(32.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
            RouteGlyph(MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(11.dp))
        Column {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun weekPatternLabel(pattern: String): String = when (pattern) {
    "odd" -> "单周"
    "even" -> "双周"
    else -> "每周"
}

private fun safeCourseColor(value: String?): Color {
    val normalized = value?.takeIf { Regex("^#[0-9a-fA-F]{6}$").matches(it) } ?: return CourseBlue
    return Color(0xFF000000 or normalized.drop(1).toLong(16))
}

@Preview(showBackground = true, widthDp = 390, heightDp = 844)
@Composable
private fun TodayPreview() {
    StudyAgentTheme {
        val sample = AppUiState(
            phase = SessionPhase.SIGNED_IN,
            profile = UserProfile("1", "student@example.com", "林同学"),
            selectedWeek = 3,
            dashboard = Dashboard(5, 2, 1, 8, 12, "先完成今天 22:00 截止的高等数学作业。", emptyList(), emptyList()),
            academic = AcademicOverview(
                3,
                listOf(ClassSession(1, StudyTime.weekday(), "08:00", "09:35", "第四教学楼 201", 1, 16, "all", "高等数学", "#246BFD", "王老师")),
                emptyList(),
            ),
            tasks = listOf(TaskItem(1, null, 1, "完成第三章习题", null, "not_started", 5, 60, "高等数学")),
        )
        TodayScreen(sample, {})
    }
}
