# 学伴管家

面向大学生的本地学习智能体：把课程资料转成可确认的 DDL 任务、复习计划和下一步行动，覆盖 Web、FastAPI 后端与原生 Android 伴侣。

_当前阶段：M8.33「DDL 应变台」第一阶段 · 适用：本地开发、评审演示和功能验收_

---

## 📋 项目概览

核心链路：**资料 → 识别 → 人工确认 → DDL/计划 → 学习反馈**。

| 模块 | 能力 |
| --- | --- |
| 学习工作区 | 邮箱注册登录、账号隔离、首页 briefing、简洁/详细视图、任务与资料来源导航 |
| 资料与 DDL | PDF/DOCX/TXT/Markdown/图片上传、文本解析/OCR、检索、通知抽取、候选编辑和人工确认 |
| 智能体闭环 | 今日决策、容量建议、复习计划、完成反馈、计划差异、执行回执和可追溯历史 |
| DDL 应变台 | 预览通知中的改期/取消影响，比较未来 7 天压力；用户核对后才更新任务 |
| 课表与考试 | 手工维护、标准 iCalendar 导入、南京理工大学本机一次性预览/同步、考试倒计时 |
| 导出与移动端 | CSV、Markdown、iCal 导出；Android 提供今天、课表、DDL 三个入口 |

> ⚠️ 这是本地开发/评审版本，不是已完成生产部署的在线服务。复杂通知、外部 AI、学校教务和日历客户端操作仍需人工复核。

## 🚀 快速开始

### 环境要求

| 环境 | 要求 |
| --- | --- |
| Windows | PowerShell |
| Python | 3.14+ |
| Node.js | 24+ |
| Android（可选） | Android Studio、JDK 17+、Android SDK 36 |

### 安装

在项目根目录执行：

```powershell
# 创建并安装后端环境
py -3.14 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 创建本地配置
Copy-Item .env.example .env
Copy-Item frontend\.env.example frontend\.env

# 安装前端依赖
Push-Location frontend
npm.cmd ci
Pop-Location
```

已有 `.venv`、依赖或配置文件时，跳过对应步骤即可。

### 启动

一键启动前后端并执行健康检查：

```powershell
& .\scripts\start-dev.ps1
```

启动后访问：

- Web：<http://127.0.0.1:5173/>
- API 健康检查：<http://127.0.0.1:8000/api/health>
- Swagger：<http://127.0.0.1:8000/docs>

需要脱敏演示数据时，将根目录 `.env` 中的 `DEMO_MODE` 改为 `true` 后重启服务。默认关闭，不会自动写入演示数据。

## 📚 功能说明

### Web 工作区

公开主页和邮箱账号入口：`/`、`/register`、`/login`。登录后主要页面如下：

| 路径 | 用途 |
| --- | --- |
| `/app` | 学习总览、今日行动、容量与回执 |
| `/materials` | 资料上传、解析、检索、候选任务确认 |
| `/tasks` | DDL 任务管理、筛选、完成和反馈 |
| `/deadline-radar` | DDL 通知改期/取消预演与确认执行 |
| `/focus` | 专注计时和任务反馈 |
| `/schedule` | 课表、考试、iCalendar/教务接入 |
| `/study-plans` | 复习计划生成、编辑、归档和导出 |
| `/settings` | 学习偏好、外部 AI 和本地测试数据管理 |

### 资料、通知与任务

- 默认使用无需网络和密钥的本地规则 Provider；外部 AI 仅作为可选 Provider。
- 抽取结果先进入候选区，用户核对名称、时间、来源和警告后，才会创建正式任务。
- 任务支持课程关联、截止时间、预计/剩余用时、状态筛选、完成反馈和安全编辑。
- 资料单文件默认上限 20 MB，单次最多 10 个文件；重复内容会被拒绝，失败资料可以重试。
- DDL 应变台只对已有任务执行“预览 → 核对 → 应用”，不会静默改期、取消任务或重排复习计划。

### 课表、考试与 Android

- 课表支持第 1—30 周、单双周、教师、教室和备注；考试支持时间、考场、座位和倒计时。
- iCalendar 导入和南京理工大学教务接入均先预览，再由用户选择同步；学校凭据只在一次本机请求和短时验证码会话中使用，不保存到数据库。
- Android 是 Kotlin + Jetpack Compose 原生客户端，读取同一 FastAPI 工作区，详见 [`android/README.md`](android/README.md)。

## ⚙️ 配置

复制 `.env.example` 为 `.env`；前端 API 地址可在 `frontend/.env` 中通过 `VITE_API_BASE_URL` 覆盖。

| 配置 | 默认值 | 作用 |
| --- | --- | --- |
| `DATABASE_URL` / `AUTH_DATABASE_URL` | SQLite | 系统与账号数据库 |
| `USER_DATABASE_DIR` | `./data/users` | 每个账号的独立学习工作区 |
| `UPLOAD_DIR` | `./data/uploads` | 本地上传文件目录 |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 留空 | 可选 OpenAI-compatible Provider |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `30` / `2` | 外部模型超时与重试 |
| `OCR_MODE` | `local` | OCR 模式 |
| `MAX_UPLOAD_SIZE_MB` / `MAX_UPLOAD_FILES` | `20` / `10` | 上传限制 |
| `DEMO_MODE` | `false` | 是否加载脱敏演示数据 |
| `CORS_ORIGINS` | 本地前端地址 | 允许的前端来源 |

默认配置不需要外部 AI 密钥。设置页保存外部 AI 配置时只返回掩码信息；每次向外部 Provider 发送资料正文前仍需用户主动选择并确认。

## 📡 API 概览

所有业务接口位于 `/api` 下，登录后接口需要会话 Cookie 和 CSRF 保护；实体编辑使用身份与版本校验。

| 路由组 | 内容 |
| --- | --- |
| `/api/health` | 服务和数据库健康检查 |
| `/api/auth/*` | 注册、登录、当前会话和退出 |
| `/api/courses/*` | 课程管理 |
| `/api/materials/*` | 资料上传、解析、检索、候选确认和原件下载 |
| `/api/tasks/*` | DDL 任务、完成和反馈 |
| `/api/deadline-radar/*` | 通知变更预览与确认应用 |
| `/api/academic-calendar/*` | 课表、考试、iCalendar 和教务同步 |
| `/api/dashboard`、`/api/agent/*` | 学习总览、建议、容量、复盘和回执 |
| `/api/study-plans/*` | 复习计划与计划差异 |
| `/api/exports/*` | CSV、Markdown 和 iCal 导出 |
| `/api/settings/*`、`/api/study-preferences/*` | Provider 与学习偏好配置 |

接口参数和响应结构以启动后的 [Swagger 文档](http://127.0.0.1:8000/docs) 为准。

## 🧪 验证

完整本地验证：

```powershell
& .\scripts\verify-local.ps1
```

该脚本依次执行 Python 依赖检查、后端完整 pytest、前端 lint/契约检查/生产构建和 gzip 包体预算检查。单独运行：

```powershell
# 后端
& .\.venv\Scripts\python.exe -m pytest backend\tests -q --basetemp .pytest-tmp\local-check

# 前端
Push-Location frontend
npm.cmd run verify
Pop-Location

# Android
Push-Location android
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
Pop-Location
```

最近一次本地回归（2026-09-12）：后端 `286 passed`；前端完整 `verify` 通过；构建仅有依赖包的既有 `@vueuse` PURE annotation 警告。自动化通过不等于真实学校登录、真实外部 AI 质量、日历客户端去重/提醒、Android 真机或公网部署已验收。

## 🔐 数据与安全边界

- `.env`、数据库、上传文件和本地运行目录不应提交到 Git；仓库只保留示例配置和代码。
- 密码使用随机盐哈希保存；浏览器使用可撤销的 HttpOnly Cookie，并对写操作校验 CSRF。
- 学习数据按账号写入独立 SQLite 工作区；任务、资料、计划和回执使用服务端身份与版本保护。
- 南理工教务凭据不进入 Android；网页版一次性请求结束后立即清除，不做后台同步。
- `scripts/backup_data.py` 支持停服后的同版本隔离恢复；跨版本迁移、加密归档和生产运维方案尚未验证。

## ⚠️ 当前限制

- 本项目当前面向本地开发和比赛评审，不提供已验收的公网部署、账号运维、邮箱验证、找回密码或登录限流。
- 复杂、否定、条件、多任务或时间含糊的通知可能需要人工复核；DDL 应变台始终要求用户确认后才执行。
- 真实外部 AI、扫描件 OCR、南京理工教务页面变化、iCal 客户端更新/去重/提醒、Android 真机和辅助技术仍需单独验收。
- 具体缺陷、复现步骤和未验证项见[功能实现审查](docs/quality/功能实现审查-2026-09-12.md)；不要把合成数据或自动化测试结果当作真实用户准确率。

## 🗂️ 目录与文档

```text
backend/       FastAPI、业务服务、数据模型和测试
frontend/      Vue 3/Vite/Element Plus Web 客户端
android/       Kotlin/Jetpack Compose 移动客户端
scripts/       启动、验证、备份和评测脚本
data/          本地数据库、用户工作区和上传目录（不提交）
docs/product/  需求、架构和比赛方向
docs/quality/  开发进度、测试、合规和审查
docs/delivery/ 演示、复现、备份和文档治理
online/        待验证的部署配置
```

推荐文档：

- [架构与技术路线](docs/product/架构与技术路线.md)
- [比赛要求对照与提交状态](docs/product/比赛要求对照与提交状态.md)
- [开发进度](docs/quality/开发进度.md)
- [正式测试用例](docs/quality/正式测试用例.md)
- [合规与隐私说明](docs/quality/合规与隐私说明.md)
- [评审复现指南](docs/delivery/评审复现指南.md)
- [离线备份与隔离恢复](docs/delivery/离线备份与隔离恢复.md)

## 📄 许可

本项目使用 [MIT License](LICENSE)。
