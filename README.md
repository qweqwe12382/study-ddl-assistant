# 学伴管家

学习 DDL 与资料管理智能体，面向大学生提供课程资料、DDL 任务和复习计划管理能力。

当前版本为 M7：稳定性、安全和本地可交付版本已完成。M6 的复习计划、进度统计、归档和 CSV/Markdown 导出已经完成。

## 环境

- Python 3.14.6（使用项目已有 `.venv`）
- Node.js 24.19.0
- SQLite（由 Python/SQLAlchemy 使用）

## 启动后端

PowerShell：

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

服务启动后访问：

- 健康检查：<http://127.0.0.1:8000/api/health>
- Swagger：<http://127.0.0.1:8000/docs>

首次启动会自动创建 `data/app.db` 和 `data/uploads/`。

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试使用 SQLite 内存数据库，不依赖 Windows 系统临时目录，也不会在项目中留下测试数据库文件。

## 基础 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET/POST | `/api/courses` | 查询/创建课程 |
| GET/PATCH/DELETE | `/api/courses/{id}` | 查询/修改/删除课程 |
| GET/POST | `/api/materials` | 查询/创建资料记录；支持 `q`、`course_id`、`material_type`、`processing_status`、`tag` 筛选 |
| GET | `/api/dashboard` | 首页待办统计、未来 7 天任务、逾期任务和最近资料 |
| GET | `/api/materials/upload-policy` | 查询上传大小、数量和格式限制 |
| GET/PATCH/DELETE | `/api/materials/{id}` | 查询/修改/删除资料记录 |
| POST | `/api/materials/upload` | 上传一个或多个资料并解析 |
| POST | `/api/materials/{id}/retry` | 重新解析失败资料 |
| GET | `/api/materials/{id}/file` | 下载原始文件 |
| GET/POST | `/api/tasks` | 查询/创建任务 |
| POST | `/api/tasks/{id}/complete` | 标记任务完成 |
| GET/PATCH/DELETE | `/api/tasks/{id}` | 查询/修改/删除任务 |
| GET | `/api/study-plans` | 查询复习计划 |
| POST | `/api/study-plans/generate` | 根据课程资料和任务生成复习计划 |
| GET/PATCH | `/api/study-plans/{id}` | 查询/修改复习计划明细 |
| POST | `/api/study-plans/{id}/archive` | 归档复习计划 |
| GET | `/api/exports/tasks.csv` | 导出 DDL CSV |
| GET | `/api/exports/materials.md` | 导出资料目录 Markdown |
| GET | `/api/exports/study-plans/{id}.md` | 导出复习计划 Markdown |

请求校验失败时统一返回 `error.code = VALIDATION_ERROR` 的 JSON 结构；未找到资源时返回对应资源的错误码。

## 目录结构

```text
backend/
├── app/
│   ├── api/          # FastAPI 路由与错误处理
│   ├── models/       # SQLAlchemy 数据模型
│   ├── schemas/      # Pydantic 请求/响应模型
│   ├── config.py
│   ├── database.py
│   └── main.py
└── tests/
frontend/             # Vue/Vite 前端，支持资料上传和手动管理
data/
├── demo/
└── uploads/
docs/
└── 开发进度.md
```

## 配置

复制 `.env.example` 为 `.env` 后按需修改。真实 API 密钥只放在 `.env`，不要提交到 Git。配置 `LLM_API_KEY`、`LLM_MODEL` 后启用 OpenAI-compatible Provider；`LLM_TIMEOUT_SECONDS` 默认 30 秒，`LLM_MAX_RETRIES` 默认 2 次；`LOG_LEVEL` 默认 `INFO`，可改为 `WARNING` 减少日志量。前端开发服务器地址可通过 `CORS_ORIGINS` 配置。

## 开发阶段

- M0：环境和项目基线，已具备依赖环境并补齐基础目录
- M1：后端骨架与数据库，当前完成
- M2：前端框架与手动管理，当前完成
- M3：文件上传与内容解析，当前完成
- M4：AI抽取与人工确认，当前完成
- M5：检索、首页和任务闭环，当前完成
- M6：复习计划与导出，当前完成
- M7：稳定性、部署与安全，当前完成
- M8：比赛材料与最终彩排，下一阶段

当前前端顶部会显示 API 连接状态；资料库支持拖拽上传、服务端关键词检索、多条件筛选、解析状态、失败原因、详情查看和重试；首页展示待办统计、未来 7 天任务、逾期任务和最近资料；任务列表查询时会自动同步已逾期任务状态。

## M4 AI 抽取与人工确认

M4 复用 M3 保存的 `extracted_text`，默认使用无需网络和密钥的本地规则 Provider；配置 `LLM_API_KEY` 与 `LLM_MODEL` 后可切换到 OpenAI-compatible Provider。所有 Provider 的输出都会经过 JSON/Pydantic 校验、日期和时间校验、相对日期解析、多日期冲突检查、来源原文回溯和置信度标记。

抽取结果不会直接写入正式任务。资料库中点击“AI抽取”后，用户可以修改任务名称、类型和截止时间，勾选需要保留的候选项，再点击“确认并创建任务”。对应接口为：

- `POST /api/materials/{id}/extract`：生成或更新抽取预览；
- `GET /api/materials/{id}/extraction`：读取最近一次抽取结果；
- `POST /api/materials/{id}/extraction/confirm`：人工确认后创建正式任务。

低置信度、缺失日期、无效日期、日期冲突或来源片段无法回溯的候选项会进入“需复核”状态。模型调用失败或结果不是合法 JSON 时会保存失败原因，用户仍可手动补充正文或继续使用本地规则 Provider。

本轮优化已补充已确认状态保护、批次级幂等、防重复任务、人工修改快照、课程/标签落库和英文/相对日期解析。已验证：后端 `pytest -q` 通过 33 个测试，前端 `npm.cmd run lint` 和 `npm.cmd run build` 均通过。

## M5 检索、首页和任务闭环

资料列表支持文件名、摘要、正文和标签关键词检索，以及课程、资料类型、处理状态和标签筛选；关键词检索会返回命中字段和正文匹配片段。首页通过 `/api/dashboard` 展示未完成、未来 7 天、逾期和资料统计，并提供近期任务、逾期提醒、最近资料和下一步建议。任务会保留来源资料名称，删除资料后不会出现无法解释的空来源。

已验证：后端 `pytest -q` 通过 36 个测试，前端 `npm.cmd run lint` 和 `npm.cmd run build` 均通过。

## M6 复习计划与导出

复习计划页支持选择课程、设置考试日期和每日学习分钟数。系统会读取课程资料的标签、摘要/正文片段和未完成任务，生成按天分阶段的复习清单；当主题多于可用天数时会合并主题并提示覆盖压力。每项计划都保留来源资料/任务 ID，支持编辑日期、主题、内容、时长和完成状态，并实时显示完成天数和分钟数。考试日期不足或可用时间不足时会显示风险提示，计划日期不能超过考试日期；重新生成会创建新计划，不覆盖已有人工修改，旧计划可以归档。

支持导出带 UTF-8 BOM 的 DDL CSV、资料目录 Markdown 和带资料/任务名称的复习计划 Markdown。对应接口见上方 API 表。

已验证：后端 `pytest -q` 通过 40 个测试，前端 `npm.cmd run lint` 和 `npm.cmd run build` 均通过。

## M7 稳定性、部署与安全

已完成稳定性和本地交付建设：`/api/health` 会实际检查数据库连接；后端记录请求方法、路径、状态码、耗时和请求 ID，并通过 `X-Request-ID` 便于定位问题；日志级别可通过 `LOG_LEVEL` 配置；上传路径清理和大小限制增加了边界测试；模型网络失败、模型超时、OCR 失败、空课程和数据库不可用均有安全兜底测试。

开启 `DEMO_MODE=true` 后，服务启动会幂等创建不含私人信息的演示课程、资料和任务；默认关闭。设置页新增“重置测试数据”按钮，开发环境可调用 `POST /api/dev/reset` 清空课程、资料、DDL 任务、复习计划和上传文件；该接口在非开发/测试环境关闭。另新增 `scripts/start-dev.ps1` 一键启动脚本和 `scripts/verify-local.ps1` 本地验证脚本。

已验证：现有环境 `pip check`、后端 50 个测试、前端 lint/build 均通过；临时全新 Python 环境安装 `backend/requirements.txt` 后 48 个基线测试通过；临时全新前端目录执行 `npm ci`、lint 和 build 通过，并报告 0 个 npm 漏洞。

已知限制：当前部署方式为本地 PowerShell 启动；复杂自然语言知识点仍需人工复核；iCal 导出和云端部署暂未纳入本版本。

M7 已完成，下一阶段为 M8“比赛材料与最终彩排”。

## M3 上传说明

上传接口支持 PDF、DOCX、TXT、MD、PNG、JPG/JPEG、GIF、BMP 和 WEBP，扫描版 PDF 会自动尝试 OCR。默认单文件大小上限为 20 MB、单次最多 10 个文件，前端通过 `/api/materials/upload-policy` 动态读取限制。原始文件保存于 `data/uploads/`，资料记录会保存文件大小、SHA-256 哈希、解析文本、处理状态和失败原因。相同内容重复上传会被拒绝；解析失败的原始文件仍会保留，可通过资料库“重试”或手动补充文本处理。删除资料时会同步删除原文件。

## 启动前端

另开一个 PowerShell 终端：

```powershell
cd frontend
npm.cmd run dev
```

访问 <http://127.0.0.1:5173/>。前端默认调用 `http://127.0.0.1:8000/api`，请先启动后端服务；也可以在 `frontend/.env` 中设置 `VITE_API_BASE_URL`。

## 一键启动与本地验证

在项目根目录执行：

```powershell
.\scripts\start-dev.ps1
```

该脚本会在后台启动后端和前端。若要加载不含私人信息的演示课程、资料和任务，将 `.env` 中的 `DEMO_MODE` 改为 `true` 后重新运行脚本。默认 `DEMO_MODE=false`，不会自动写入演示数据。

执行完整本地验证：

```powershell
.\scripts\verify-local.ps1
```

## M8 交付文档

- [架构与技术路线](docs/架构与技术路线.md)
- [正式测试用例](docs/正式测试用例.md)
- [合规与隐私说明](docs/合规与隐私说明.md)
- [演示与彩排清单](docs/演示与彩排清单.md)

这些文档用于比赛提交和现场演示准备。当前版本仍采用本地 PowerShell 启动方式，复杂自然语言结果需要人工复核，iCal 导出和云端部署暂未纳入范围。
