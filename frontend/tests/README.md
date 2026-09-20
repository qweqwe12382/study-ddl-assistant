# 前端检查目录

`contracts/` 保存不依赖浏览器的前端行为契约和构建预算检查；这些检查由 `npm run verify` 统一调用。当前包含 15 组行为契约，以及单独的构建预算检查。

`verify` 还会检查 JavaScript 和全部 Vue 单文件组件，包含脚本中的未定义变量与模板中的未定义属性，随后完成生产构建。浏览器中的真实交互与响应式布局需另行验收。

| 文件 | 检查内容 |
| --- | --- |
| `check-material-source-navigation.mjs` | 来源导航白名单和异常目标 |
| `check-api-base-url.mjs` | 本地 API 主机名、端口及地址归一化 |
| `check-edit-precondition.mjs` | 编辑身份、版本和实体删除前置条件 |
| `check-first-learning-loop-placement.mjs` | 首轮学习闭环入口挂载与优先级 |
| `check-plan-delta-display.mjs` | 计划差异的完整展示 |
| `check-focus-timer.mjs` | 专注计时、恢复与任务关联 |
| `check-quick-add.mjs` | 快速添加任务的输入与时间处理 |
| `check-task-filters.mjs` | 任务搜索、状态和课程筛选 |
| `check-paste-notice.mjs` | 粘贴通知的处理与来源 |
| `check-deadline-radar.mjs` | DDL 变更预览与确认条件 |
| `check-semester-week.mjs` | 学期周次计算与选择 |
| `check-workspace-commands.mjs` | 快捷入口搜索与路由白名单 |
| `check-daily-workflow.mjs` | 日常操作意图、默认安排与路由参数 |
| `check-downloads.mjs` | 共享 API 地址、携带会话的文件请求、文件名和下载失败反馈 |
| `check-motion.mjs` | 手账入场的可见性触发、减少动态效果、交互打断、页面隐藏和卸载清理 |
| `check-bundle-budget.mjs` | production 构建产物 gzip 预算 |

从 `frontend/` 目录执行：

```powershell
npm.cmd run verify
```

完整模块与浏览器验收记录见 [2026-09-20 全面功能测试与优化](../../docs/quality/全面功能测试与优化-2026-09-20.md)。
