# 学伴管家 Android

原生 Android 学习伴侣，当前开发版提供登录、今日学习轨道、按周课表、考试倒计时、DDL 队列和任务完成闭环。南理工教务凭据仍只在网页版的本机接入流程中使用；安卓端读取用户已经确认同步到个人工作区的数据。

## 当前能力

- Kotlin + Jetpack Compose 单 Activity 应用；
- “今天 / 课表 / DDL”三入口移动信息架构；
- 复用现有邮箱账号、Cookie 会话与 CSRF 写保护；
- 课程、考试、Dashboard 和任务数据来自现有 FastAPI；
- 完成任务时提交不可复用身份与版本 `If-Match`；
- 密码不进入 `ViewModel`、偏好或本地文件；Cookie 仅保存在进程内存；
- 只持久化用户填写的服务地址和当前教学周；
- Release 构建只允许 HTTPS；Debug 构建的 HTTP 地址仍被代码限制为本机和私有局域网。

## 视觉系统

- 设计母题为“学习航线”：登录页、今日时间轨道与底部导航共用站点和连线语言，对应事实同步、行动选择与完成闭环；
- 墨蓝用于结构，工科蓝用于当前状态，实验绿用于完成，朱红只用于考试和逾期；普通内容卡保持白底细描边；
- 主标题为 19—23sp，正文为 14—16sp；时间、周次和计数使用紧凑等宽字，避免大字挤占课表信息；
- 一屏展示完整七天，课程使用时间票据，考试使用倒计时票据，DDL 使用可识别状态和圆形完成动作；
- 亮色与深色模式分别校准前景色、描边和系统栏图标，不依赖只适合效果图的固定浅色背景。

## 开发环境

- Android Studio 2025.2.1 或兼容版本；
- JDK 17+，推荐直接使用 Android Studio 自带 JBR；
- Android SDK 36；
- Gradle Wrapper 8.13。

项目根目录执行：

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
cd android
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
```

APK 输出到 `android/app/build/outputs/apk/debug/app-debug.apk`。

## 连接本机后端

真机 USB 调试优先使用 ADB reverse，不需要把 FastAPI 暴露到局域网：

```powershell
.\scripts\start-android-dev.ps1
```

保持 USB 连接后，在应用中填写 `http://127.0.0.1:8000`。如果使用 Android Studio 模拟器但不使用 ADB reverse，可填写 `http://10.0.2.2:8000`。

Debug 构建允许本机或私有局域网 HTTP，仅用于受控开发。发布版本必须连接 HTTPS 后端；不要为了省事在 Release Manifest 中开启全局明文流量。

## 数据边界

| 数据 | 安卓端处理 |
| --- | --- |
| 登录密码 | 仅用于当前登录请求，提交后立即从表单状态移除 |
| 会话 Cookie / CSRF | 仅进程内存，不落盘；退出或进程结束后清除 |
| 服务地址 | 保存在应用私有 `SharedPreferences` |
| 当前教学周 | 保存在应用私有 `SharedPreferences` |
| 课表、考试、DDL | 本次运行内展示；事实仍由个人 FastAPI/SQLite 工作区维护 |
| 南理工教务凭据 | 安卓端不采集；继续使用网页版一次性本机接入 |

当前是开发版，不包含正式签名、应用商店发布、后台通知、离线数据库和生物识别解锁。
